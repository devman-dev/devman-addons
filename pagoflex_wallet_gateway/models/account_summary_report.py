from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class PfGatewayAccountSummaryWizard(models.TransientModel):
    _name = "pf.gateway.account.summary.wizard"
    _description = "Asistente de resumen de cuenta PagoFlex"

    bank_account_id = fields.Many2one(
        "pf.gateway.bank.account",
        string="Cuenta bancaria",
        required=True,
    )
    date_from = fields.Date(string="Desde")
    date_to = fields.Date(string="Hasta")
    status = fields.Char(string="Estado")
    include_commissions = fields.Boolean(string="Incluir comisiones", default=True)

    @api.constrains("date_from", "date_to")
    def _check_date_range(self):
        for wizard in self:
            if wizard.date_from and wizard.date_to and wizard.date_from > wizard.date_to:
                raise ValidationError(_("La fecha Desde no puede ser posterior a la fecha Hasta."))

    def _transfer_domain(self):
        self.ensure_one()
        domain = [
            "|",
            ("source_bank_account_id", "=", self.bank_account_id.id),
            ("destination_bank_account_id", "=", self.bank_account_id.id),
        ]
        if self.date_from:
            domain.append(("transaction_at", ">=", fields.Datetime.to_datetime(self.date_from)))
        if self.date_to:
            date_to = fields.Datetime.to_datetime(self.date_to).replace(hour=23, minute=59, second=59)
            domain.append(("transaction_at", "<=", date_to))
        if self.status:
            domain.append(("status", "=", self.status.strip()))
        if not self.include_commissions:
            domain.append(("movement_nature", "!=", "COMMISSION"))
        return domain

    def _period_transfer_domain(self):
        self.ensure_one()
        domain = []
        if self.date_from:
            domain.append(("transaction_at", ">=", fields.Datetime.to_datetime(self.date_from)))
        if self.date_to:
            date_to = fields.Datetime.to_datetime(self.date_to).replace(hour=23, minute=59, second=59)
            domain.append(("transaction_at", "<=", date_to))
        if self.status:
            domain.append(("status", "=", self.status.strip()))
        return domain

    def _commission_companies(self):
        self.ensure_one()
        company_model = self.env["pf.gateway.company"]
        membership_model = self.env["pf.gateway.company.membership"]

        memberships = membership_model.search(
            [
                ("active", "=", True),
                ("company_id", "!=", False),
                ("bank_account_id", "=", self.bank_account_id.id),
            ]
        )
        companies = memberships.mapped("company_id")

        primary_companies = company_model.search([("primary_bank_account_id", "=", self.bank_account_id.id)])
        companies |= primary_companies

        if self.bank_account_id.gateway_user_id:
            user_memberships = membership_model.search(
                [
                    ("active", "=", True),
                    ("company_id", "!=", False),
                    ("user_id", "=", self.bank_account_id.gateway_user_id.id),
                ]
            )
            companies |= user_memberships.mapped("company_id")

        return companies

    def _commission_summary_values(self):
        self.ensure_one()
        companies = self._commission_companies()
        rows = []
        totals = {
            "transaction_count": 0,
            "commission_base": 0.0,
            "commission_total": 0.0,
        }

        for company in companies:
            agent_lines = self.env["pf.gateway.company.commission.gateway.agent"].search(
                [
                    ("is_active", "=", True),
                    ("company_id", "=", company.id),
                ],
                order="id",
            )
            if not agent_lines:
                continue

            memberships = self.env["pf.gateway.company.membership"].search(
                [
                    ("active", "=", True),
                    ("company_id", "=", company.id),
                    ("user_id", "!=", False),
                ]
            )
            users = memberships.mapped("user_id")
            if not users:
                continue

            transfer_domain = [
                ("movement_nature", "=", "TRANSFER"),
                ("source_user_id", "in", users.ids),
            ] + self._period_transfer_domain()
            transfers = self.env["pf.gateway.transfer"].search(transfer_domain)
            commission_base = sum(transfers.mapped("amount"))
            transaction_count = len(transfers)
            if not commission_base:
                continue

            for line in agent_lines:
                percentage = line.commission_percentage or 0.0
                agent_partner = line.user_id.partner_id if line.user_id else self.env["res.partner"]
                commission_amount = commission_base * percentage / 100.0
                rows.append(
                    {
                        "company": company.name,
                        "agent": (
                            agent_partner.display_name
                            if agent_partner
                            else line.user_id.display_name if line.user_id else _("Sin comisionista")
                        ),
                        "agent_code": agent_partner.gateway_commission_agent_code if agent_partner else "",
                        "percentage": percentage,
                        "transaction_count": transaction_count,
                        "commission_base": commission_base,
                        "commission_amount": commission_amount,
                    }
                )
                totals["commission_total"] += commission_amount

            totals["transaction_count"] += transaction_count
            totals["commission_base"] += commission_base

        return {
            "companies": companies,
            "rows": rows,
            "totals": totals,
        }

    def _summary_values(self):
        self.ensure_one()
        transfers = self.env["pf.gateway.transfer"].search(self._transfer_domain(), order="transaction_at, id")
        incoming = 0.0
        outgoing = 0.0
        lines = []
        for transfer in transfers:
            is_incoming = transfer.destination_bank_account_id == self.bank_account_id
            is_outgoing = transfer.source_bank_account_id == self.bank_account_id
            signed_amount = 0.0
            direction = ""
            if is_incoming:
                incoming += transfer.amount
                signed_amount = transfer.amount
                direction = _("Entrada")
            elif is_outgoing:
                outgoing += transfer.amount
                signed_amount = -transfer.amount
                direction = _("Salida")

            lines.append(
                {
                    "date": transfer.transaction_at,
                    "name": transfer.name,
                    "origin_id": transfer.origin_id,
                    "payment_id": transfer.payment_id,
                    "movement_nature": transfer.movement_nature,
                    "status": transfer.status,
                    "direction": direction,
                    "counterparty": transfer.source_owner_name if is_incoming else transfer.destination_owner_name,
                    "amount": transfer.amount,
                    "signed_amount": signed_amount,
                    "currency": transfer.currency or self.bank_account_id.currency,
                }
            )

        return {
            "wizard": self,
            "bank_account": self.bank_account_id,
            "lines": lines,
            "incoming_total": incoming,
            "outgoing_total": outgoing,
            "net_total": incoming - outgoing,
            "line_count": len(lines),
            "commission_summary": self._commission_summary_values(),
        }

    def action_print_report(self):
        self.ensure_one()
        return self.env.ref("pagoflex_wallet_gateway.action_report_pf_gateway_account_summary").report_action(self)


class ReportPfGatewayAccountSummary(models.AbstractModel):
    _name = "report.pagoflex_wallet_gateway.report_account_summary"
    _description = "Reporte de resumen de cuenta PagoFlex"

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env["pf.gateway.account.summary.wizard"].browse(docids)
        if not docs:
            raise UserError(_("No se encontró el asistente de resumen de cuenta."))
        return {
            "doc_ids": docids,
            "doc_model": "pf.gateway.account.summary.wizard",
            "docs": docs,
            "summaries": {wizard.id: wizard._summary_values() for wizard in docs},
        }
