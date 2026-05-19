import logging
import re

from odoo import http, _
from odoo.http import request

_logger = logging.getLogger(__name__)


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
CATEGORIE_AMMESSE = ('volontario', 'amministrativo')


class CroceviaIscrizioneController(http.Controller):
    """Form pubblico di richiesta tesseramento sul sito.

    La rotta GET mostra il form; la POST valida e crea un record
    `crocevia.richiesta.iscrizione` in `sudo()` (il visitatore è anonimo,
    non ha permessi diretti sul modello). Il direttivo trova le richieste
    nel menu Tesseramento → Richieste iscrizione e le approva da lì.
    """

    @http.route('/iscrizione', type='http', auth='public', website=True,
                sitemap=True)
    def iscrizione_form(self, **kw):
        return request.render(
            'crocevia_tesseramento.iscrizione_form_template',
            {'error': None, 'values': kw},
        )

    @http.route('/iscrizione/invia', type='http', auth='public', website=True,
                methods=['POST'], csrf=True)
    def iscrizione_invia(self, **post):
        # Honeypot: campo "website" nascosto agli umani. Se è valorizzato
        # è quasi certamente un bot — fingiamo successo e non creiamo nulla.
        if (post.get('website') or '').strip():
            _logger.info("Iscrizione Crocevia: honeypot riempito, scarto silenziosamente.")
            return request.render(
                'crocevia_tesseramento.iscrizione_conferma_template', {})

        error = self._valida(post)
        if error:
            return request.render(
                'crocevia_tesseramento.iscrizione_form_template',
                {'error': error, 'values': post},
            )

        vals = self._post_to_vals(post)
        try:
            request.env['crocevia.richiesta.iscrizione'].sudo().create(vals)
        except Exception:
            _logger.exception("Errore creazione richiesta iscrizione Crocevia")
            return request.render(
                'crocevia_tesseramento.iscrizione_form_template',
                {
                    'error': _("Si è verificato un errore tecnico. "
                               "Riprova più tardi o scrivici via email."),
                    'values': post,
                },
            )

        return request.render(
            'crocevia_tesseramento.iscrizione_conferma_template', {})

    # ---------- helpers ----------

    def _valida(self, post):
        required = [('nome', "Nome"), ('cognome', "Cognome"), ('email', "Email")]
        mancanti = [label for key, label in required
                    if not (post.get(key) or '').strip()]
        if not post.get('consenso_privacy'):
            mancanti.append(_("Consenso privacy"))
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
        def _get(key, upper=False, maxlen=None):
            val = (post.get(key) or '').strip()
            if upper:
                val = val.upper()
            if maxlen:
                val = val[:maxlen]
            return val

        return {
            'nome': _get('nome'),
            'cognome': _get('cognome'),
            'email': _get('email'),
            'telefono': _get('telefono'),
            'data_nascita': post.get('data_nascita') or False,
            'luogo_nascita': _get('luogo_nascita'),
            'codice_fiscale': _get('codice_fiscale', upper=True, maxlen=16),
            'indirizzo': _get('indirizzo'),
            'cap': _get('cap', maxlen=5),
            'citta': _get('citta'),
            'provincia': _get('provincia', upper=True, maxlen=2),
            'categoria_richiesta': post.get('categoria_richiesta') or 'volontario',
            'messaggio': _get('messaggio'),
            'consenso_privacy': True,
        }
