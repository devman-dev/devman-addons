from odoo import _, fields, models


class AccountJournal(models.Model):
    _inherit = "account.journal"

    checkbook_ids = fields.One2many(
        comodel_name="account.checkbook",
        inverse_name="journal_id",
        string="Chequeras",
    )

    def _auto_init(self):
        super()._auto_init()
        sql = """
            UPDATE account_journal
            SET check_manual_sequencing = 'false'
            WHERE check_manual_sequencing = 'true'
            AND type = 'bank';
        """
        self.env.cr.execute(sql)
