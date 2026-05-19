"""
API HTTP per ricevere richieste di tesseramento dal sito esterno
(croceviadeimondi.org, Astro statico).

Il form HTML vive nell'app Astro del sito; qui esponiamo solo l'endpoint
POST che riceve i dati, valida e crea un record `crocevia.richiesta.iscrizione`
in stato `nuova`. Il direttivo trova le richieste in Odoo (Tesseramento -
Richieste iscrizione) e le approva da lì.

Origine consentita per CORS: parametro di sistema
`crocevia_tesseramento.cors_origin` (default `https://croceviadeimondi.org`).
Modificabile da: Impostazioni - Tecnico - Parametri di sistema.
"""

import json
import logging
import re

from odoo import http, _
from odoo.http import request, Response

_logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
CATEGORIE_AMMESSE = ('volontario', 'amministrativo')
DEFAULT_CORS_ORIGIN = 'https://croceviadeimondi.org'


class CroceviaIscrizioneApi(http.Controller):

    @http.route(
        '/api/iscrizione',
        type='http',
        auth='public',
        methods=['POST', 'OPTIONS'],
        csrf=False,
    )
    def iscrizione_post(self, **post):
        cors_headers = self._cors_headers()

        # Preflight CORS per fetch JSON dal sito.
        if request.httprequest.method == 'OPTIONS':
            return Response(status=204, headers=cors_headers)

        # Accetta sia form-urlencoded sia JSON body.
        if self._is_json_request():
            data, parse_err = self._parse_json_body()
            if parse_err:
                return self._json(400, {'success': False, 'error': parse_err}, cors_headers)
            post = {**post, **data}

        # Honeypot anti-spam: campo `website` nascosto nel form.
        # I bot lo compilano, gli umani no. Fingiamo successo silenziosamente.
        if (post.get('website') or '').strip():
            _logger.info("api/iscrizione: honeypot riempito, scarto silenziosamente")
            return self._json(200, {'success': True}, cors_headers)

        errore = self._valida(post)
        if errore:
            return self._json(400, {'success': False, 'error': errore}, cors_headers)

        vals = self._post_to_vals(post)
        try:
            richiesta = request.env['crocevia.richiesta.iscrizione'].sudo().create(vals)
        except Exception:
            _logger.exception("api/iscrizione: errore creazione richiesta")
            return self._json(
                500,
                {'success': False, 'error': _("Errore interno. Riprova piu tardi.")},
                cors_headers,
            )

        _logger.info("api/iscrizione: creata richiesta id=%s", richiesta.id)
        return self._json(
            200,
            {'success': True, 'message': _("Richiesta ricevuta. Ti risponderemo via email.")},
            cors_headers,
        )

    # ---------- helpers ----------

    def _cors_headers(self):
        allowed = request.env['ir.config_parameter'].sudo().get_param(
            'crocevia_tesseramento.cors_origin',
            default=DEFAULT_CORS_ORIGIN,
        )
        origin = request.httprequest.headers.get('Origin', '')
        # Echo dell'origine solo se autorizzata (o se il parametro e' "*").
        if allowed == '*' or origin == allowed:
            allow = origin or allowed
        else:
            allow = allowed
        return {
            'Access-Control-Allow-Origin': allow,
            'Access-Control-Allow-Methods': 'POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Accept',
            'Access-Control-Max-Age': '3600',
            'Vary': 'Origin',
        }

    def _is_json_request(self):
        ctype = (request.httprequest.content_type or '').lower()
        return 'application/json' in ctype

    def _parse_json_body(self):
        try:
            raw = request.httprequest.get_data(as_text=True) or '{}'
            data = json.loads(raw)
            if not isinstance(data, dict):
                return None, _("Il body JSON deve essere un oggetto.")
            return data, None
        except json.JSONDecodeError:
            return None, _("Body JSON non valido.")

    def _valida(self, post):
        obbligatori = [('nome', "Nome"), ('cognome', "Cognome"), ('email', "Email")]
        mancanti = [label for key, label in obbligatori
                    if not (post.get(key) or '').strip()]
        if not post.get('consenso_privacy'):
            mancanti.append("Consenso privacy")
        if mancanti:
            return _("Campi obbligatori mancanti: %s") % ", ".join(mancanti)

        email = (post.get('email') or '').strip()
        if not EMAIL_RE.match(email):
            return _("L'indirizzo email non sembra valido.")

        categoria = post.get('categoria_richiesta') or 'volontario'
        if categoria not in CATEGORIE_AMMESSE:
            return _("Categoria richiesta non valida.")

        return None

    def _post_to_vals(self, post):
        def _g(key, upper=False, maxlen=None):
            val = (post.get(key) or '').strip()
            if upper:
                val = val.upper()
            if maxlen:
                val = val[:maxlen]
            return val

        return {
            'nome': _g('nome'),
            'cognome': _g('cognome'),
            'email': _g('email'),
            'telefono': _g('telefono'),
            'data_nascita': post.get('data_nascita') or False,
            'luogo_nascita': _g('luogo_nascita'),
            'codice_fiscale': _g('codice_fiscale', upper=True, maxlen=16),
            'indirizzo': _g('indirizzo'),
            'cap': _g('cap', maxlen=5),
            'citta': _g('citta'),
            'provincia': _g('provincia', upper=True, maxlen=2),
            'categoria_richiesta': post.get('categoria_richiesta') or 'volontario',
            'messaggio': _g('messaggio'),
            'consenso_privacy': bool(post.get('consenso_privacy')),
        }

    def _json(self, status, payload, headers=None):
        all_headers = {'Content-Type': 'application/json; charset=utf-8'}
        if headers:
            all_headers.update(headers)
        return Response(
            json.dumps(payload, ensure_ascii=False),
            status=status,
            headers=all_headers,
        )
