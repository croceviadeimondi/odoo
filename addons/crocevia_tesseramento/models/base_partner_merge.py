"""
Guardrail CDM sul wizard nativo di merge contatti
(`base.partner.merge.automatic.wizard`).

Il wizard di Odoo gia' riassegna automaticamente tutte le foreign key
(cariche, ricevute, prestiti, beni, ore di volontariato, ...) dai contatti
sorgente al contatto di destinazione prima di eliminarli. Qui aggiungiamo
solo i controlli specifici dell'associazione e consolidiamo i campi del
libro soci sul contatto sopravvissuto.
"""

from odoo import models, _
from odoo.exceptions import UserError


class BasePartnerMergeAutomaticWizard(models.TransientModel):
    _inherit = 'base.partner.merge.automatic.wizard'

    def _merge(self, partner_ids, dst_partner=None, extra_checks=True):
        Partner = self.env['res.partner']
        partners = Partner.browse(partner_ids).exists()

        # Sotto i 2 contatti non c'e' nulla da fondere: lascia fare al base.
        if len(partners) < 2:
            return super()._merge(
                partner_ids, dst_partner=dst_partner, extra_checks=extra_checks)

        # Determina destinazione e sorgenti con la stessa logica del base
        # (manuale: dst passato; automatico: ultimo dell'ordinamento).
        if dst_partner and dst_partner in partners:
            srcs = partners - dst_partner
        else:
            ordered = self._get_ordered_partner(partners.ids)
            srcs = ordered[:-1]

        # Guardrail 1: codici fiscali diversi => non sono lo stesso socio.
        cf_set = {
            p.codice_fiscale.strip().upper()
            for p in partners if p.codice_fiscale
        }
        if len(cf_set) > 1:
            raise UserError(_(
                "I contatti selezionati hanno codici fiscali diversi (%s): "
                "non sono lo stesso socio e non vanno uniti."
            ) % ", ".join(sorted(cf_set)))

        # Guardrail 2: registro volontari vidimato (immutabile per legge,
        # DM 6 ottobre 2021 / art. 2215-bis cc). Se un contatto SORGENTE
        # (che verrebbe eliminato, con il suo partner_id riassegnato via SQL)
        # e' citato in un'iscrizione vidimata, blocca il merge.
        if 'crocevia.registro.iscrizione' in self.env:
            vincolate = self.env['crocevia.registro.iscrizione'].sudo().search([
                ('partner_id', 'in', srcs.ids),
                ('stato_inalterabilita', '=', 'vidimato'),
            ])
            if vincolate:
                nomi = ", ".join(sorted(set(
                    vincolate.mapped('partner_id.display_name'))))
                raise UserError(_(
                    "Impossibile unire: il contatto \"%s\" e' citato in "
                    "iscrizioni VIDIMATE del registro volontari, immutabili "
                    "per legge (DM 6 ottobre 2021, art. 2215-bis cc). "
                    "Scegli quel contatto come destinazione da MANTENERE, "
                    "oppure non unirlo."
                ) % nomi)

        # Snapshot pre-merge per consolidare i campi del libro soci sul
        # contatto sopravvissuto (i sorgenti vengono eliminati dal base).
        nums = [
            int(p.numero_socio) for p in partners
            if p.numero_socio and p.numero_socio.isdigit()
        ]
        date_isc = [p.data_iscrizione for p in partners if p.data_iscrizione]
        any_socio = any(p.is_socio for p in partners)
        any_attivo = any(p.stato_socio == 'attivo' for p in partners)
        has_vol = 'is_volontario' in Partner._fields
        any_vol = has_vol and any(p.is_volontario for p in partners)
        date_vol = [
            p.data_inizio_volontariato for p in partners
            if has_vol and p.data_inizio_volontariato
        ]

        res = super()._merge(
            partner_ids, dst_partner=dst_partner, extra_checks=extra_checks)

        # Il sopravvissuto e' l'unico dei `partners` ancora esistente.
        survivor = partners.exists()
        vals = {}
        if any_socio:
            vals['is_socio'] = True
        if any_attivo:
            vals['stato_socio'] = 'attivo'
        if nums:
            # Numero socio piu' basso (la sequenza non e' reversibile).
            vals['numero_socio'] = str(min(nums))
        if date_isc:
            vals['data_iscrizione'] = min(date_isc)
        if has_vol and any_vol:
            vals['is_volontario'] = True
        if date_vol:
            vals['data_inizio_volontariato'] = min(date_vol)
        if vals and survivor:
            survivor.write(vals)
        return res
