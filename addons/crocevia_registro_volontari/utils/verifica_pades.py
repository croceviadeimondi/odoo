"""
Verifica crittografica di un PDF firmato PAdES + marca temporale RFC 3161,
tramite pyHanko. Isolato dal modello Odoo per essere testabile a parte.

Strategia (v2.0):
- integrita' (`intact`) e validita' crittografica (`valid`) della firma SONO
  obbligatorie: garantiscono che il documento non sia stato modificato dopo
  la firma (tamper-evidence reale);
- la firma deve coprire l'intero file (`coverage` ENTIRE_FILE);
- deve esserci una marca temporale (data certa);
- la validazione della catena contro le CA QUALIFICATE (trust list AgID/EU)
  e' best-effort: se passi `trust_roots` viene tentata e l'esito finisce in
  `qualificata`/`dettagli`, ma non e' richiesta per `valida` salvo `strict`.

Ritorna un dict semplice consumato dal modello vidimazione.
"""
import io
import logging

_logger = logging.getLogger(__name__)


def _nome_da_cert(cert):
    """Estrae nome e codice fiscale dal subject del certificato (best-effort).
    Le CA italiane mettono spesso il CF nel serialNumber come 'TINIT-<CF>'."""
    nome = cf = ''
    try:
        subj = cert.subject.native  # asn1crypto -> dict
        nome = (subj.get('common_name')
                or ' '.join(filter(None, [subj.get('given_name'),
                                          subj.get('surname')]))
                or '')
        sn = subj.get('serial_number') or ''
        if sn:
            cf = sn.split('-')[-1] if '-' in sn else sn
    except Exception as e:  # noqa: BLE001 - best-effort, non deve rompere
        _logger.warning("estrazione dati firmatario fallita: %s", e)
    return nome, cf


def verifica_pdf_firmato(pdf_bytes, trust_roots=None, strict=False):
    """Verifica la prima firma PAdES del PDF.

    :param pdf_bytes: bytes del PDF firmato.
    :param trust_roots: lista opzionale di certificati CA (asn1crypto) per la
        validazione della catena (firma qualificata).
    :param strict: se True, la firma e' valida solo se anche la catena verso
        le CA qualificate e' verificata.
    :return: dict con valida, qualificata, dettagli, firmatario_nome,
        firmatario_cf, marca_temporale (datetime|None), tsa.
    """
    from pyhanko.pdf_utils.reader import PdfFileReader
    from pyhanko.sign.validation import validate_pdf_signature
    from pyhanko_certvalidator import ValidationContext

    esito = {
        'valida': False, 'qualificata': False, 'dettagli': '',
        'firmatario_nome': '', 'firmatario_cf': '',
        'marca_temporale': None, 'tsa': '',
    }
    righe = []
    try:
        reader = PdfFileReader(io.BytesIO(pdf_bytes))
        firme = list(reader.embedded_signatures)
    except Exception as e:  # noqa: BLE001
        esito['dettagli'] = "Impossibile leggere il PDF o le firme: %s" % e
        return esito

    if not firme:
        esito['dettagli'] = "Nessuna firma digitale trovata nel PDF."
        return esito

    vc = None
    if trust_roots:
        try:
            vc = ValidationContext(trust_roots=list(trust_roots),
                                   allow_fetching=False)
        except Exception as e:  # noqa: BLE001
            righe.append("Trust list non caricata: %s" % e)

    sig = firme[0]
    try:
        status = validate_pdf_signature(sig, signer_validation_context=vc)
    except Exception as e:  # noqa: BLE001
        esito['dettagli'] = "Errore in fase di validazione firma: %s" % e
        return esito

    intatta = bool(getattr(status, 'intact', False))
    valida_cripto = bool(getattr(status, 'valid', False))
    copertura = getattr(status, 'coverage', None)
    copre_tutto = bool(copertura) and getattr(copertura, 'name', '') in (
        'ENTIRE_FILE', 'ENTIRE_REVISION')

    # Firmatario
    cert = getattr(status, 'signing_cert', None) or getattr(sig, 'signer_cert', None)
    if cert is not None:
        esito['firmatario_nome'], esito['firmatario_cf'] = _nome_da_cert(cert)

    # Marca temporale
    ts = getattr(status, 'timestamp_validity', None)
    if ts is not None:
        esito['marca_temporale'] = getattr(ts, 'timestamp', None)
        tsa_cert = getattr(ts, 'signing_cert', None)
        if tsa_cert is not None:
            esito['tsa'], _ = _nome_da_cert(tsa_cert)
    if esito['marca_temporale'] is None:
        esito['marca_temporale'] = getattr(sig, 'self_reported_timestamp', None)

    # Qualificazione (catena verso CA qualificate)
    catena_ok = bool(getattr(status, 'validation_path', None)) and \
        not getattr(status, 'trust_problem_indic', None)
    esito['qualificata'] = bool(vc) and catena_ok

    righe.append("Integrita': %s" % ("OK" if intatta else "FALLITA"))
    righe.append("Firma crittografica: %s" % ("valida" if valida_cripto else "non valida"))
    righe.append("Copertura documento: %s" % (getattr(copertura, 'name', '?')))
    righe.append("Marca temporale: %s" % (esito['marca_temporale'] or "ASSENTE"))
    if vc:
        righe.append("Catena CA qualificata: %s" % ("verificata" if esito['qualificata'] else "NON verificata"))
    else:
        righe.append("Catena CA qualificata: non controllata (trust list assente)")

    requisiti_base = intatta and valida_cripto and copre_tutto and bool(esito['marca_temporale'])
    esito['valida'] = requisiti_base and (esito['qualificata'] if strict else True)
    esito['dettagli'] = '\n'.join(righe)
    return esito
