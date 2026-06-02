#!/usr/bin/env python3
"""
PROTOTIPO - Notifica nella chat interna di Odoo (Discuss).

Posta un messaggio come OdooBot in un canale Discuss interno (lo crea se
non esiste e ci aggiunge gli utenti interni, cosi' i direttivi lo vedono).
Pensato come hook di notifica per deploy/backup.sh, ma usabile per
qualsiasi messaggio di sistema.

NON si esegue da solo: va dato in pasto a `odoo shell`, che fornisce la
variabile globale `env`. Parametri via ambiente:
    CHAT_CHANNEL   nome del canale (default "Sistema")
    CHAT_MSG       corpo del messaggio (HTML semplice ammesso)

Esempio (sul VPS):
    docker exec -i \\
        -e CHAT_CHANNEL=Sistema \\
        -e CHAT_MSG="<b>Backup</b> completato: 6.0M" \\
        crocevia-odoo odoo shell -d crocevia --no-http \\
        --shell-interface=python < deploy/notifica_chat_odoo.py
"""
import os

CHANNEL_NAME = os.environ.get("CHAT_CHANNEL", "Sistema")
BODY = os.environ.get("CHAT_MSG", "Notifica di sistema dal gestionale.")

Channel = env["discuss.channel"]  # noqa: F821 (env iniettato da odoo shell)
channel = Channel.search([("name", "=", CHANNEL_NAME)], limit=1)

if not channel:
    # Canale nuovo: tipo "channel" (non DM) e iscrive tutti gli utenti
    # interni cosi' la notifica e' visibile al direttivo.
    interni = env["res.users"].search(  # noqa: F821
        [("share", "=", False), ("active", "=", True)]
    )
    channel = Channel.create({
        "name": CHANNEL_NAME,
        "channel_type": "channel",
    })
    try:
        channel.add_members(partner_ids=interni.partner_id.ids)
    except Exception as e:  # API discuss puo' variare tra versioni
        print("WARN add_members:", e)

# Posta come OdooBot (partner radice), non come l'utente del shell.
odoobot = env.ref("base.partner_root")  # noqa: F821
channel.message_post(
    body=BODY,
    author_id=odoobot.id,
    message_type="comment",
    subtype_xmlid="mail.mt_comment",
)

env.cr.commit()  # noqa: F821
print("POSTED_OK canale=%s membri=%s" % (
    CHANNEL_NAME, len(channel.channel_member_ids)))
