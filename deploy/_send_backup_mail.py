#!/usr/bin/env python3
"""
Helper di deploy/backup.sh: invia per email l'esito del backup, con
l'archivio in allegato se la variabile d'ambiente ATTACH e' valorizzata
(e l'archivio non e' troppo grande - il controllo soglia lo fa backup.sh).

Legge la configurazione SMTP dall'ambiente (impostata da backup.sh che a
sua volta la prende da deploy/backup.env):
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS
    BACKUP_EMAIL_TO, BACKUP_EMAIL_FROM
    ATTACH           (path archivio o vuoto = solo notifica)

Argomenti: <path_archivio> <size_human>
Non e' pensato per uso diretto: lo invoca backup.sh.
"""
import os
import smtplib
import ssl
import sys
from email.message import EmailMessage


def main():
    archivio = sys.argv[1] if len(sys.argv) > 1 else "(sconosciuto)"
    size_h = sys.argv[2] if len(sys.argv) > 2 else "?"

    host = os.environ.get("SMTP_HOST", "smtp.ionos.it")
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ["SMTP_USER"]
    password = os.environ["SMTP_PASS"]
    to_addr = os.environ["BACKUP_EMAIL_TO"]
    from_addr = os.environ.get("BACKUP_EMAIL_FROM", user)
    attach = os.environ.get("ATTACH", "").strip()

    msg = EmailMessage()
    msg["Subject"] = f"Backup Odoo Crocevia - {os.path.basename(archivio)} ({size_h})"
    msg["From"] = from_addr
    msg["To"] = to_addr
    corpo = [
        "Backup del gestionale Odoo del Crocevia dei Mondi APS.",
        "",
        f"Archivio: {os.path.basename(archivio)}",
        f"Dimensione: {size_h}",
    ]
    if attach and os.path.isfile(attach):
        with open(attach, "rb") as f:
            msg.add_attachment(
                f.read(),
                maintype="application",
                subtype="gzip",
                filename=os.path.basename(attach),
            )
        corpo.append("Archivio in allegato.")
    else:
        corpo.append(
            "Archivio NON allegato (troppo grande o non disponibile): "
            "recuperalo sul VPS o da Google Drive."
        )
    msg.set_content("\n".join(corpo))

    ctx = ssl.create_default_context()
    with smtplib.SMTP(host, port, timeout=60) as s:
        s.starttls(context=ctx)
        s.login(user, password)
        s.send_message(msg)


if __name__ == "__main__":
    sys.exit(main())
