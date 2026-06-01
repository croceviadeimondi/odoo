# Immagine Odoo 18 derivata che include le librerie Python necessarie
# ai moduli custom del Crocevia. In particolare:
#
# - weasyprint  -> generazione PDF deterministica (snapshot registro
#                  volontari, eventuali report futuri)
# - pyhanko     -> verifica firma digitale PAdES + marca temporale RFC 3161
#                  (vidimazione registro volontari, art. 2215-bis cc)
# - pyhanko-certvalidator -> validazione catena PKI (AgID / EU LOTL)
# - qpdf        -> post-processing PDF per renderlo deterministico
#                  (rimozione metadati timestamp, normalizzazione ID)
#
# Si usa con `docker compose build` invece di `pull`. Il docker-compose.yml
# punta a questo Dockerfile tramite `build: .`.

FROM odoo:18.0

USER root

# Dipendenze di sistema:
# - qpdf: post-processing PDF (snapshot deterministico registro volontari)
# - libpango / libcairo / libharfbuzz: librerie di rendering richieste
#   da WeasyPrint (vedi https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#installation)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        qpdf \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libharfbuzz0b \
        libfontconfig1 \
        libcairo2 \
    && rm -rf /var/lib/apt/lists/*

# Python deps. Note tecniche:
# - `--break-system-packages`: Debian 12 / Python 3.12 protegge il
#   system site-packages, va bene in container isolato.
# - `--ignore-installed`: la `cryptography` installata via apt non ha
#   RECORD file, quindi pip non riesce a disinstallarla per aggiornarla.
#   Forziamo l'install affianco (l'eventuale duplicato e' innocuo nel
#   resolution Python).
RUN pip3 install --break-system-packages --no-cache-dir \
        --ignore-installed \
        weasyprint \
        pyhanko \
        pyhanko-certvalidator

USER odoo
