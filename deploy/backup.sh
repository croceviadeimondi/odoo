#!/usr/bin/env bash
#
# Backup del gestionale Odoo del Crocevia dei Mondi APS.
#
# Produce un singolo archivio `crocevia-backup_<data>.tar.gz` contenente:
#   - dump del database (pg_dump custom format, .pgdump)
#   - filestore (allegati/immagini dal volume Docker)
# Poi ruota i backup locali e, se configurato, li manda offsite
# (Google Drive via rclone, oppure email).
#
# Uso (cron giornaliero, vedi deploy/README.md sezione 10):
#   0 3 * * * /opt/crocevia/gestionale/deploy/backup.sh >> /var/log/crocevia-backup.log 2>&1
#
# Configurazione: copia deploy/backup.env.example in deploy/backup.env
# (gitignored) e personalizza. Senza backup.env il backup gira comunque
# in locale con i default qui sotto; l'offsite (drive/email) resta spento
# finche' non valorizzi le chiavi.

set -euo pipefail

# Cartella dello script -> root del repo (deploy/ sta dentro il repo).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"

# Carica config opzionale (secret/impostazioni). Non versionata.
if [[ -f "$SCRIPT_DIR/backup.env" ]]; then
    # shellcheck disable=SC1090
    source "$SCRIPT_DIR/backup.env"
fi

# ---- Default (sovrascrivibili da backup.env) ----
BACKUP_DIR="${BACKUP_DIR:-/opt/crocevia/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
DB_CONTAINER="${DB_CONTAINER:-crocevia-odoo-db}"
DB_USER="${DB_USER:-odoo}"
DB_NAME="${DB_NAME:-crocevia}"
FILESTORE_VOLUME="${FILESTORE_VOLUME:-crocevia-odoo_odoo-data}"

# Offsite (vuoti = disattivato). Vedi backup.env.example.
RCLONE_REMOTE="${RCLONE_REMOTE:-}"            # es. gdrive:crocevia-odoo-backup
BACKUP_EMAIL_TO="${BACKUP_EMAIL_TO:-}"        # es. info@croceviadeimondi.org
BACKUP_EMAIL_FROM="${BACKUP_EMAIL_FROM:-info@croceviadeimondi.org}"
SMTP_HOST="${SMTP_HOST:-smtp.ionos.it}"
SMTP_PORT="${SMTP_PORT:-587}"
SMTP_USER="${SMTP_USER:-}"
SMTP_PASS="${SMTP_PASS:-}"
EMAIL_MAX_MB="${EMAIL_MAX_MB:-20}"            # oltre questa soglia non allega

log() { echo "[$(date '+%F %T')] $*"; }
fail() { log "ERRORE: $*"; exit 1; }

TS="$(date +%F_%H%M)"
ARCHIVE="$BACKUP_DIR/crocevia-backup_${TS}.tar.gz"

mkdir -p "$BACKUP_DIR"

# Verifica che il container DB sia attivo.
docker ps --format '{{.Names}}' | grep -qx "$DB_CONTAINER" \
    || fail "container DB '$DB_CONTAINER' non in esecuzione"

log "Avvio backup -> $ARCHIVE"

# Staging temporaneo, ripulito sempre (anche su errore).
WORK="$(mktemp -d)"
cleanup() { rm -rf "$WORK"; }
trap cleanup EXIT

# 1. Dump DB (custom format, comprimibile e selettivo in restore).
log "Dump database '$DB_NAME'..."
docker exec "$DB_CONTAINER" pg_dump -U "$DB_USER" -Fc "$DB_NAME" > "$WORK/db.pgdump" \
    || fail "pg_dump fallito"

# 2. Filestore dal volume Docker.
log "Archiviazione filestore (volume $FILESTORE_VOLUME)..."
docker run --rm -v "${FILESTORE_VOLUME}:/data:ro" alpine \
    tar czf - -C /data . > "$WORK/filestore.tar.gz" \
    || fail "archiviazione filestore fallita"

# 3. Archivio unico.
tar czf "$ARCHIVE" -C "$WORK" db.pgdump filestore.tar.gz || fail "tar finale fallito"
SIZE_H="$(du -h "$ARCHIVE" | cut -f1)"
log "Backup creato: $ARCHIVE ($SIZE_H)"

# 4. Rotazione locale.
DELETED="$(find "$BACKUP_DIR" -maxdepth 1 -name 'crocevia-backup_*.tar.gz' \
    -mtime +"$RETENTION_DAYS" -print -delete | wc -l)"
log "Rotazione: rimossi $DELETED backup piu' vecchi di $RETENTION_DAYS giorni"

# 5a. Offsite: Google Drive (o altro) via rclone.
if [[ -n "$RCLONE_REMOTE" ]]; then
    if command -v rclone >/dev/null 2>&1; then
        log "Upload su rclone remote '$RCLONE_REMOTE'..."
        rclone copy "$ARCHIVE" "$RCLONE_REMOTE/" \
            && log "Upload rclone ok" \
            || log "ATTENZIONE: upload rclone fallito (backup locale comunque salvo)"
        # Pruning remoto coerente con la retention locale.
        rclone delete --min-age "${RETENTION_DAYS}d" "$RCLONE_REMOTE/" \
            --include 'crocevia-backup_*.tar.gz' 2>/dev/null \
            && log "Pruning remoto ok" || true
    else
        log "ATTENZIONE: RCLONE_REMOTE impostato ma 'rclone' non installato. Salto upload."
    fi
fi

# 5b. Offsite: email con allegato (alternativa a rclone).
if [[ -n "$BACKUP_EMAIL_TO" ]]; then
    SIZE_MB=$(( $(stat -c%s "$ARCHIVE") / 1024 / 1024 ))
    if [[ -z "$SMTP_USER" || -z "$SMTP_PASS" ]]; then
        log "ATTENZIONE: BACKUP_EMAIL_TO impostato ma SMTP_USER/SMTP_PASS mancanti. Salto email."
    elif (( SIZE_MB > EMAIL_MAX_MB )); then
        log "ATTENZIONE: backup ${SIZE_MB}MB > soglia ${EMAIL_MAX_MB}MB: invio solo notifica, niente allegato."
        ATTACH="" python3 "$SCRIPT_DIR/_send_backup_mail.py" "$ARCHIVE" "$SIZE_H" \
            || log "ATTENZIONE: invio notifica email fallito"
    else
        log "Invio backup via email a $BACKUP_EMAIL_TO..."
        ATTACH="$ARCHIVE" python3 "$SCRIPT_DIR/_send_backup_mail.py" "$ARCHIVE" "$SIZE_H" \
            && log "Email inviata" || log "ATTENZIONE: invio email fallito"
    fi
fi

log "Backup completato."
