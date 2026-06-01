# Deploy gestionale Odoo del Crocevia dei Mondi APS

Procedura per portare in produzione il gestionale su VPS IONOS
(`82.165.47.57`) sul sottodominio `odoo.croceviadeimondi.org`.

Prerequisiti:

- accesso SSH al VPS con utente che puo' usare Docker;
- Docker Engine + plugin `compose` gia' installati;
- nginx host gia' attivo sul VPS con cert wildcard
  `*.croceviadeimondi.org` (gia' presente per il sito Astro);
- record DNS A `odoo.croceviadeimondi.org` → `82.165.47.57`
  pubblicato (si gestisce dal pannello IONOS).

---

## 1. DNS

Dal pannello IONOS aggiungi un record A:

```
odoo.croceviadeimondi.org   A   82.165.47.57   TTL 1h
```

Verifica:

```bash
dig +short odoo.croceviadeimondi.org
# deve restituire 82.165.47.57
```

Il cert wildcard copre gia' tutti i sottodomini: niente da rinnovare.

---

## 2. Clone del repo sul VPS

```bash
ssh <utente>@82.165.47.57
sudo mkdir -p /opt/crocevia
sudo chown $USER:$USER /opt/crocevia
cd /opt/crocevia
git clone https://github.com/<repo-owner>/odoo.git gestionale
cd gestionale
```

---

## 3. Configurazione di produzione

### `.env`

```bash
cp .env.example .env
```

Imposta in `.env`:

```dotenv
DB_USER=odoo
DB_PASSWORD=<password lunga e casuale, 32+ char>
ODOO_PORT=8069
ODOO_BIND=127.0.0.1     # IMPORTANTE: solo nginx parla con Odoo
```

### `config/odoo.conf`

```bash
cp config/odoo.conf.example config/odoo.conf
```

Imposta in `config/odoo.conf`:

```ini
admin_passwd = <password lunga e casuale, 32+ char, diversa da DB>
dbfilter     = ^crocevia$
list_db      = False
proxy_mode   = True
logfile      = /var/log/odoo/odoo.log     ; per fail2ban
; workers    = 2                          ; abilita se il VPS regge
```

Per generare password robuste: `openssl rand -base64 32`.

---

## 4. Build immagine custom e primo avvio

```bash
docker compose build odoo
docker compose up -d db
sleep 5
docker compose run --rm odoo odoo \
    -d crocevia -i base \
    --stop-after-init --no-http
```

Questo crea il database `crocevia` con i moduli base. Poi installa i
custom in ordine di dipendenza:

```bash
for mod in crocevia_inventario \
           crocevia_tesseramento \
           crocevia_volontariato \
           crocevia_registro_volontari \
           crocevia_assemblee \
           crocevia_navigazione \
           crocevia_ruoli; do
    docker compose run --rm odoo odoo \
        -d crocevia -i $mod \
        --stop-after-init --no-http
done

docker compose up -d odoo
```

Verifica che Odoo risponda solo su localhost:

```bash
curl -sI http://127.0.0.1:8069/web/login | head -1
# HTTP/1.1 303 SEE OTHER

curl --max-time 3 -sI http://82.165.47.57:8069/ || echo "OK: porta non raggiungibile dall'esterno"
```

---

## 5. nginx reverse proxy

```bash
sudo cp deploy/nginx/odoo.croceviadeimondi.org.conf \
    /etc/nginx/sites-available/
sudo ln -s /etc/nginx/sites-available/odoo.croceviadeimondi.org.conf \
    /etc/nginx/sites-enabled/

sudo nginx -t
sudo systemctl reload nginx
```

Apri il browser su `https://odoo.croceviadeimondi.org/web/login`
e verifica che compaia la login Odoo dietro HTTPS.

---

## 6. Primo login admin e creazione utenti

- Login: `admin` (utente di default, password = quella scelta in fase
  di creazione DB dal pannello — se non l'hai impostata, vedi sotto).
- Cambia subito la password dell'utente `admin`.
- Importa la copia degli utenti dei direttivi:
  ```bash
  # Dal tuo PC
  scp tools/importa_registro_soci.py <utente>@82.165.47.57:/tmp/
  ```
  In realta' i 4 direttivi esistono gia' nel db `crocevia` se l'hai
  esportato dal locale. Vedi punto 7 (migrazione).

Se non hai l'admin password, recuperala con:

```bash
docker exec -it crocevia-odoo-db psql -U odoo -d crocevia -c \
    "UPDATE res_users SET password='<nuova-pwd>' WHERE login='admin';"
# Odoo hasha al primo login con la nuova password
```

---

## 7. Migrazione del DB dal locale al VPS (alternativa allo step 4)

Se vuoi portare TUTTO il lavoro fatto in locale (4 direttivi gia'
configurati, sedi, dati di test) anziche' partire vuoto:

```bash
# Sul PC locale: dump
docker exec crocevia-odoo-db pg_dump -U odoo -F c -d crocevia \
    > /tmp/crocevia.pgdump
docker run --rm -v crocevia-odoo_odoo-data:/data alpine \
    tar czf - -C /data . > /tmp/crocevia-filestore.tar.gz

# Trasferisci sul VPS
scp /tmp/crocevia.pgdump /tmp/crocevia-filestore.tar.gz \
    <utente>@82.165.47.57:/tmp/

# Sul VPS: ripristina
cd /opt/crocevia/gestionale
docker compose up -d db
sleep 5
docker exec -i crocevia-odoo-db psql -U odoo -d postgres -c \
    "CREATE DATABASE crocevia OWNER odoo;"
docker exec -i crocevia-odoo-db pg_restore -U odoo -d crocevia \
    --no-owner --role=odoo < /tmp/crocevia.pgdump
docker run --rm \
    -v crocevia-odoo_odoo-data:/data \
    -v /tmp/crocevia-filestore.tar.gz:/backup.tar.gz \
    alpine sh -c "cd /data && tar xzf /backup.tar.gz"

docker compose up -d odoo

# Pulizia
rm /tmp/crocevia.pgdump /tmp/crocevia-filestore.tar.gz
ssh <utente>@82.165.47.57 "rm /tmp/crocevia.pgdump /tmp/crocevia-filestore.tar.gz"
```

Poi forza un upgrade dei moduli custom (in caso di drift tra ambienti):

```bash
docker compose stop odoo
docker compose run --rm odoo odoo -d crocevia -u all \
    --stop-after-init --no-http
docker compose start odoo
```

---

## 8. SMTP IONOS

Da Odoo (modalita' sviluppatore attiva):

- Impostazioni > Tecnico > Email > **Server di posta in uscita**
- Nuovo:
  - Nome: `IONOS info@`
  - Priorita': `10`
  - Connessione: **TLS (STARTTLS)**
  - Server SMTP: `smtp.ionos.it`
  - Porta: `587`
  - Username: `info@croceviadeimondi.org`
  - Password: la password della casella IONOS (non l'admin del pannello)
- Bottone **Prova la connessione** → verde.

Poi in Impostazioni > Generali > Email:

- Alias dominio: `croceviadeimondi.org`
- Email aziendale: `info@croceviadeimondi.org`

Limiti IONOS: ~1000 mail/giorno per casella. Sufficiente per chatter
+ ricevute. Per volumi piu' alti, secondo server SMTP a priorita' 20
(Brevo, Mailgun).

---

## 9. fail2ban (consigliato)

```bash
sudo cp deploy/fail2ban/filter.d/odoo.conf  /etc/fail2ban/filter.d/
sudo cp deploy/fail2ban/jail.d/odoo.conf    /etc/fail2ban/jail.d/
sudo systemctl restart fail2ban
sudo fail2ban-client status odoo
```

Banna IP dopo 5 fallimenti login in 10 minuti, per 1 ora.

Per testarlo dal tuo PC (NON dal VPS, ti banneresti):

```bash
for i in $(seq 1 6); do
    curl -s -d 'login=admin&password=sbagliata' \
        https://odoo.croceviadeimondi.org/web/login > /dev/null
done
# Sul VPS:
sudo fail2ban-client status odoo
# deve mostrare il tuo IP nella lista banned
```

---

## 10. Backup quotidiano

Cron giornaliero alle 03:00 (DB + filestore):

```bash
sudo crontab -e
```

```cron
0 3 * * * cd /opt/crocevia/gestionale && /opt/crocevia/gestionale/deploy/backup.sh >> /var/log/crocevia-backup.log 2>&1
```

(Lo script `deploy/backup.sh` non e' ancora scritto: TODO post-deploy.)

---

## 11. Upgrade futuri

Quando il repo cambia:

```bash
cd /opt/crocevia/gestionale
git pull
docker compose build odoo                  # solo se cambia il Dockerfile
docker compose stop odoo
docker compose run --rm odoo odoo \
    -d crocevia -u <modulo-cambiato> \
    --stop-after-init --no-http
docker compose start odoo
```

Per upgrade di TUTTI i custom in un colpo:

```bash
docker compose run --rm odoo odoo -d crocevia \
    -u crocevia_inventario,crocevia_tesseramento,crocevia_volontariato,crocevia_registro_volontari,crocevia_assemblee,crocevia_navigazione,crocevia_ruoli \
    --stop-after-init --no-http
```

---

## Troubleshooting

| Sintomo | Causa probabile | Soluzione |
|---|---|---|
| 502 Bad Gateway | container Odoo non attivo | `docker compose logs --tail=50 odoo` |
| Login va in loop / sessione persa | manca `proxy_mode=True` in odoo.conf | Aggiungilo, restart odoo |
| WebSocket non funziona (notifiche, chatter live) | nginx non passa `Upgrade` | Verifica blocco `location /websocket` |
| 413 Request Entity Too Large | upload allegato troppo grosso | Aumenta `client_max_body_size` in nginx |
| fail2ban non banna | logfile mancante in odoo.conf | Decommenta `logfile = /var/log/odoo/odoo.log` |
