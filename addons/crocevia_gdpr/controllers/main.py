"""
Blocco GDPR al primo accesso (lato server).

Override del web client (/web, /odoo): se l'utente interno non ha ancora
accettato l'informativa, viene rediretto alla pagina di accettazione.
La pagina mostra il testo (parametro `crocevia_gdpr.informativa_html`) e
un bottone "Accetto" che registra l'accettazione e riporta al gestionale.
"""

from markupsafe import Markup

from odoo import fields, http
from odoo.http import request
from odoo.addons.web.controllers.home import Home, is_user_internal

PARAM_TESTO = 'crocevia_gdpr.informativa_html'


class HomeGdpr(Home):

    @http.route()
    def web_client(self, s_action=None, **kw):
        # Intercetta solo utenti interni autenticati che non hanno ancora
        # accettato; tutto il resto (login, redirect, ecc.) va al super.
        if (request.session.uid
                and is_user_internal(request.session.uid)
                and not kw.get('redirect')):
            request.update_env(user=request.session.uid)
            if not request.env.user.gdpr_accettata:
                return request.redirect('/crocevia/gdpr', code=303)
        return super().web_client(s_action=s_action, **kw)


class GdprController(http.Controller):

    @http.route('/crocevia/gdpr', type='http', auth='user', sitemap=False)
    def pagina_gdpr(self, **kw):
        if request.env.user.gdpr_accettata:
            return request.redirect('/odoo', code=303)
        testo = request.env['ir.config_parameter'].sudo().get_param(
            PARAM_TESTO, default='')
        return request.render('crocevia_gdpr.pagina_accettazione', {
            'informativa': Markup(testo or ''),
            'csrf_token': request.csrf_token(),
        })

    @http.route('/crocevia/gdpr/accetta', type='http', auth='user',
                methods=['POST'], csrf=True)
    def accetta_gdpr(self, **kw):
        request.env.user.sudo().write({
            'gdpr_accettata': True,
            'gdpr_accettata_il': fields.Datetime.now(),
        })
        return request.redirect('/odoo', code=303)
