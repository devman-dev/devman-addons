from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.osv import expression
import logging


_logger = logging.getLogger(__name__)


class AccountCheckbook(models.Model):
    _name = "account.checkbook"
    _description = "account.checkbook"

    name = fields.Char("Nombre")
    journal_id = fields.Many2one("account.journal", string="Diario")
    sequence_id = fields.Many2one("ir.sequence", string="Secuencia")
    checkbook_type = fields.Selection(
        selection=[("physical", "Fisico"), ("electronic", "Electronico")],
        string="Tipo chequera",
        default="physical",
    )
    state = fields.Selection(
        selection=[("active", "Activo"), ("inactive", "Inactivo")], default="active"
    )
    next_number = fields.Integer("Siguiente numero", default=0)
    end_number = fields.Integer("Ultimo Numero")
    checks_cancelled = fields.Boolean("Cheques cancelados", default=False)

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        required=True,
    )

    def _check_domain(self):
        self.ensure_one()
        return [
            ("state", "in", ["posted", "cancel"]),
            ("checkbook_id", "=", self.id),
            ("journal_id", "=", self.journal_id.id),
            ("alpha_check_number", "ilike", f"{self.name}%"),
        ]

    def is_checkbook_sequence_wrong(self):
        self.ensure_one()
        last_check_number = self.get_last_check()
        return int(last_check_number) >= self.next_number + 1

    def get_next_check(self):
        self.ensure_one()
        if self.is_checkbook_sequence_wrong():
            last_check = self.get_last_check()
            return int(last_check) + 1
        return self.next_number + 1

    @api.model
    def get_check_number(self, sequence_number, checkbook_id=None):
        self.ensure_one()
        if not checkbook_id:
            checkbook_id = self

        domain = checkbook_id._check_domain()
        domain = expression.AND(
            [
                domain,
                [
                    ("alpha_check_number", "ilike", f"%{sequence_number}"),
                    ("check_number", "=", sequence_number),
                ],
            ]
        )
        return self.env["account.payment"].search(domain, limit=1)

    @api.model
    def get_last_check(self, checkbook_id=None):
        self.ensure_one()
        if not checkbook_id:
            checkbook_id = self

        domain = checkbook_id._check_domain()
        last_check = self.env["account.payment"].search(
            domain,
            order="alpha_check_number desc",
            limit=1,
        )

        return last_check.check_number if last_check else str(checkbook_id.next_number)

    def unlink(self):
        raise ValidationError(
            "No se puede borrar la chequera, márquela como inactiva por favor"
        )

    @api.constrains("next_number")
    def check_next_number(self):
        for checkbook in self:
            if checkbook.next_number:
                last_check = checkbook.get_last_check()
                if int(last_check) > checkbook.next_number:
                    raise ValidationError(
                        _(
                            "There are checks with a higher number than %s",
                            checkbook.next_number,
                        )
                    )

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            if "next_number" in vals and rec.checks_cancelled:
                rec.checks_cancelled = False
        return res

    @api.model
    def number_is_above_range(self, sequence_number, next_sequence=0):
        self.ensure_one()
        # next_sequence = next_sequence or self.next_number + 1
        next_sequence |= self.next_number + 1
        return (
            int(sequence_number) > next_sequence
            and int(sequence_number) > self.end_number
            and self.checkbook_type == "physical"
        )
