"""
EPC QR Code (standard EPC069-12 versione 002) per bonifici SEPA precompilati.

Lo scansiona l'app banca del pagatore (Intesa Sanpaolo, UniCredit, Banco
BPM, Fineco, BPER, Hype, Tinaba, BBVA, ...) e si apre il form di bonifico
gia' compilato con beneficiario, IBAN, importo e causale: l'utente
conferma e parte un SEPA Credit Transfer a commissione 0 (e' un
bonifico normale, niente intermediari).

Spec ufficiale European Payments Council:
https://www.europeanpaymentscouncil.eu (cerca "EPC069-12")

Struttura del payload (11 righe ASCII separate da \\n, max ~331 byte):
  1  Service Tag        : "BCD"
  2  Version            : "002"
  3  Character set      : "1" (UTF-8)
  4  Identification     : "SCT" (SEPA Credit Transfer)
  5  BIC                : opzionale, vuoto per pagamenti EU
  6  Beneficiary name   : max 70 char
  7  IBAN beneficiario  : senza spazi
  8  Amount             : "EUR<int>.<2 cifre>", vuoto = importo libero
  9  Purpose            : codice ISO 20022 (4 char), raramente usato
 10  Structured ref     : max 35 char (raramente usato in Italia)
 11  Remittance info    : causale libera, max 140 char
"""

import base64
import io

import qrcode


def _normalizza_iban(iban):
    """Rimuove spazi e converte in upper case (gli IBAN nei QR EPC non
    possono contenere spazi)."""
    if not iban:
        return ''
    return ''.join(iban.split()).upper()


def _formatta_importo(amount):
    """Formato "EUR<int>.<2 cifre>". Importo non valido -> stringa vuota
    (significa "importo libero" per il pagatore)."""
    try:
        amount = float(amount or 0)
    except (TypeError, ValueError):
        return ''
    if amount <= 0:
        return ''
    return "EUR%.2f" % amount


def costruisci_payload_epc(beneficiario, iban, importo=None,
                           causale='', bic='', riferimento_strutturato=''):
    """Costruisce il payload EPC069-12 v002.

    Args:
        beneficiario: nome dell'intestatario IBAN (max 70 char)
        iban: IBAN del beneficiario (gli spazi vengono rimossi)
        importo: importo in EUR (float); None/0 -> importo libero
        causale: testo libero (max 140 char), comparira' nella
                 causale del bonifico precompilato
        bic: BIC opzionale (max 11 char). Vuoto per bonifico SEPA puro
        riferimento_strutturato: structured creditor reference ISO 11649
                 (raramente usato in Italia, max 35 char)

    Returns:
        stringa multi-riga ASCII pronta per essere encodata in QR.
    """
    righe = [
        'BCD',
        '002',
        '1',
        'SCT',
        (bic or '')[:11],
        (beneficiario or '')[:70],
        _normalizza_iban(iban),
        _formatta_importo(importo),
        '',  # purpose code, non lo usiamo
        (riferimento_strutturato or '')[:35],
        (causale or '')[:140],
    ]
    return '\n'.join(righe)


def genera_qr_png_base64(payload, box_size=10, border=4):
    """Genera l'immagine QR del payload e la ritorna come bytes base64.

    Adatta per essere salvata in un campo Binary di Odoo oppure inclusa
    in un template QWeb come `data:image/png;base64,...`.
    """
    qr = qrcode.QRCode(
        version=None,  # auto-fit
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color='black', back_color='white')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return base64.b64encode(buf.getvalue())
