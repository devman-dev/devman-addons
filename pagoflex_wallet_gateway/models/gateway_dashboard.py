from collections import defaultdict
from datetime import datetime, time

from markupsafe import escape

from odoo import _, api, fields, models


class PfGatewayDashboard(models.TransientModel):
    _name = "pf.gateway.dashboard"
    _description = "Centro de Control PagoFlex"

    date_from = fields.Date(string="Desde", default=lambda self: self._default_date_from(), required=True)
    date_to = fields.Date(string="Hasta", default=lambda self: fields.Date.context_today(self), required=True)

    kpi_transfers_today = fields.Integer(string="Transferencias hoy", compute="_compute_dashboard")
    kpi_amount_today = fields.Float(string="Volumen hoy", compute="_compute_dashboard", digits=(16, 2))
    kpi_period_volume = fields.Float(string="Volumen del periodo", compute="_compute_dashboard", digits=(16, 2))
    kpi_average_ticket = fields.Float(string="Ticket promedio", compute="_compute_dashboard", digits=(16, 2))
    kpi_failed_jobs = fields.Integer(string="Alertas de sync", compute="_compute_dashboard")
    kpi_active_companies = fields.Integer(string="Empresas activas", compute="_compute_dashboard")
    kpi_synced_users = fields.Integer(string="Usuarios activos", compute="_compute_dashboard")
    kpi_success_rate = fields.Float(string="Disponibilidad sync", compute="_compute_dashboard", digits=(16, 2))
    kpi_estimated_commission = fields.Float(string="Ingresos por comisión", compute="_compute_dashboard", digits=(16, 2))
    kpi_open_exceptions = fields.Integer(string="Excepciones abiertas", compute="_compute_dashboard")

    executive_summary_html = fields.Html(string="Resumen ejecutivo", compute="_compute_dashboard", sanitize=False)
    sync_summary_html = fields.Html(string="Control operativo", compute="_compute_dashboard", sanitize=False)
    exceptions_summary_html = fields.Html(string="Detalle de excepciones", compute="_compute_dashboard", sanitize=False)
    financial_summary_html = fields.Html(string="Finanzas", compute="_compute_dashboard", sanitize=False)

    @api.model
    def _default_date_from(self):
        today = fields.Date.context_today(self)
        return today.replace(day=1)

    @api.depends("date_from", "date_to")
    def _compute_dashboard(self):
        for record in self:
            record._compute_dashboard_values()

    def _compute_dashboard_values(self):
        self.ensure_one()

        transfer_model = self.env["pf.gateway.transfer"]
        job_model = self.env["pf.gateway.sync.job"]
        log_model = self.env["pf.gateway.sync.log"]
        user_model = self.env["pf.gateway.user"]
        company_model = self.env["pf.gateway.company"]
        membership_model = self.env["pf.gateway.company.membership"]

        today_from, today_to = self._day_bounds(fields.Date.context_today(self))
        today_transfers = transfer_model.search([
            ("active", "=", True),
            ("movement_nature", "=", "TRANSFER"),
            ("transaction_at", ">=", today_from),
            ("transaction_at", "<=", today_to),
        ])
        self.kpi_transfers_today = len(today_transfers)
        self.kpi_amount_today = sum(today_transfers.mapped("amount"))

        self.kpi_failed_jobs = job_model.search_count([("last_status", "=", "failed"), ("active", "=", True)])
        self.kpi_active_companies = company_model.search_count([("active", "=", True)])
        self.kpi_synced_users = user_model.search_count([("active", "=", True)])

        log_domain = []
        start_dt, end_dt = self._period_bounds()
        if start_dt:
            log_domain.append(("started_at", ">=", start_dt))
        if end_dt:
            log_domain.append(("started_at", "<=", end_dt))
        period_logs = log_model.search(log_domain)
        finished_logs = period_logs.filtered(lambda log: log.status in ("success", "failed"))
        success_logs = finished_logs.filtered(lambda log: log.status == "success")
        self.kpi_success_rate = (len(success_logs) / len(finished_logs) * 100.0) if finished_logs else 100.0

        exception_values = self._exception_values()
        self.kpi_open_exceptions = sum(item["count"] for item in exception_values)

        period_transfers = transfer_model.search(self._period_transfer_domain())
        analytics = self._commission_analytics(period_transfers, membership_model)
        self.kpi_period_volume = analytics["total_amount"]
        self.kpi_average_ticket = analytics["average_ticket"]
        self.kpi_estimated_commission = analytics["commission_total"]

        self.executive_summary_html = self._build_executive_summary_html(period_transfers, analytics)
        self.sync_summary_html = self._build_sync_summary_html(job_model.search([], order="sequence, id"), period_logs)
        self.exceptions_summary_html = self._build_exceptions_html(exception_values)
        self.financial_summary_html = self._build_financial_html(analytics)

    def _period_bounds(self):
        start_dt = False
        end_dt = False
        if self.date_from:
            start_dt = datetime.combine(self.date_from, time.min)
        if self.date_to:
            end_dt = datetime.combine(self.date_to, time.max)
        return start_dt, end_dt

    def _day_bounds(self, day):
        return datetime.combine(day, time.min), datetime.combine(day, time.max)

    def _period_transfer_domain(self):
        domain = [
            ("active", "=", True),
            ("movement_nature", "=", "TRANSFER"),
        ]
        start_dt, end_dt = self._period_bounds()
        if start_dt:
            domain.append(("transaction_at", ">=", start_dt))
        if end_dt:
            domain.append(("transaction_at", "<=", end_dt))
        return domain

    def _exception_values(self):
        return [
            {
                "label": _("Usuarios sin contacto vinculado"),
                "count": self.env["pf.gateway.user"].search_count([("partner_id", "=", False), ("active", "=", True)]),
            },
            {
                "label": _("Empresas sin usuario creador asociado"),
                "count": self.env["pf.gateway.company"].search_count([
                    ("created_by_user_id", "=", False),
                    ("active", "=", True),
                ]),
            },
            {
                "label": _("Membresias activas sin empresa resuelta"),
                "count": self.env["pf.gateway.company.membership"].search_count([
                    ("active", "=", True),
                    ("company_id", "=", False),
                ]),
            },
            {
                "label": _("Transferencias con vinculacion incompleta"),
                "count": self.env["pf.gateway.transfer"].search_count([
                    ("active", "=", True),
                    "|",
                    ("source_bank_account_id", "=", False),
                    ("destination_bank_account_id", "=", False),
                ]),
            },
            {
                "label": _("Usuarios sin verificacion KYC"),
                "count": self.env["pf.gateway.user"].search_count([("active", "=", True), ("is_kyc_verified", "=", False)]),
            },
        ]

    def _commission_analytics(self, transfers, membership_model):
        memberships = membership_model.search([
            ("active", "=", True),
            ("company_id", "!=", False),
            ("user_id", "!=", False),
        ], order="source_updated_at desc, id desc")
        company_by_user_id = {}
        for membership in memberships:
            company_by_user_id.setdefault(membership.user_id.id, membership.company_id)

        commission_gateway_model = self.env["pf.gateway.company.commission.gateway.agent"]
        company_ids = list({company.id for company in company_by_user_id.values() if company})
        commission_lines_by_company = defaultdict(lambda: commission_gateway_model.browse())
        if company_ids:
            commission_lines = commission_gateway_model.search([
                ("is_active", "=", True),
                ("company_id", "in", company_ids),
            ])
            for line in commission_lines:
                commission_lines_by_company[line.company_id.id] |= line

        company_totals = defaultdict(lambda: {"name": "", "amount": 0.0, "count": 0, "commission": 0.0})
        agent_totals = defaultdict(lambda: {"name": "", "code": "", "amount": 0.0, "count": 0})
        status_totals = defaultdict(int)
        total_amount = 0.0
        commission_total = 0.0

        for transfer in transfers:
            total_amount += transfer.amount
            status_totals[transfer.status or _("Sin estado")] += 1
            company = company_by_user_id.get(transfer.source_user_id.id)
            if not company:
                continue
            company_bucket = company_totals[company.id]
            company_bucket["name"] = company.name
            company_bucket["amount"] += transfer.amount
            company_bucket["count"] += 1

            commission_lines = commission_lines_by_company.get(company.id, commission_gateway_model.browse())
            for line in commission_lines:
                commission_amount = transfer.amount * line.commission_percentage / 100.0
                commission_total += commission_amount
                company_bucket["commission"] += commission_amount
                agent_partner = line.user_id.partner_id if line.user_id else self.env["res.partner"]
                agent_key = line.user_id.id or line.id
                agent_bucket = agent_totals[agent_key]
                agent_bucket["name"] = (
                    agent_partner.display_name
                    if agent_partner
                    else line.user_id.display_name if line.user_id else _("Sin comisionista")
                )
                agent_bucket["code"] = agent_partner.gateway_commission_agent_code if agent_partner else ""
                agent_bucket["amount"] += commission_amount
                agent_bucket["count"] += 1

        return {
            "total_amount": total_amount,
            "transfer_count": len(transfers),
            "average_ticket": (total_amount / len(transfers)) if transfers else 0.0,
            "commission_total": commission_total,
            "status_totals": sorted(status_totals.items(), key=lambda item: (-item[1], item[0])),
            "top_companies": sorted(company_totals.values(), key=lambda item: item["amount"], reverse=True)[:5],
            "top_agents": sorted(agent_totals.values(), key=lambda item: item["amount"], reverse=True)[:5],
        }

    def _build_executive_summary_html(self, transfers, analytics):
        period_label = "%s - %s" % (self.date_from or "-", self.date_to or "-")
        status_rows = "".join(
            "<tr><td>%s</td><td class='text-end'>%s</td></tr>" % (escape(status), count)
            for status, count in analytics["status_totals"]
        ) or "<tr><td colspan='2'>Sin movimientos en el periodo.</td></tr>"
        return (
            "<div class='o_form_label'>"
            "<h3>Resumen del periodo</h3>"
            "<p><strong>Rango analizado:</strong> %s</p>"
            "<p><strong>Transferencias analizadas:</strong> %s | <strong>Volumen:</strong> %s | <strong>Ticket promedio:</strong> %s</p>"
            "<table class='table table-sm table-striped'>"
            "<thead><tr><th>Estado</th><th class='text-end'>Cantidad</th></tr></thead>"
            "<tbody>%s</tbody>"
            "</table>"
            "</div>"
        ) % (
            escape(period_label),
            len(transfers),
            escape(self._format_amount(analytics["total_amount"])),
            escape(self._format_amount(analytics["average_ticket"])),
            status_rows,
        )

    def _build_sync_summary_html(self, jobs, logs):
        recent_logs = logs.sorted(key=lambda log: (log.started_at or fields.Datetime.now()), reverse=True)[:5]
        job_rows = "".join(
            "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
                escape(job.name),
                escape(dict(job._fields["resource"].selection).get(job.resource, job.resource or "")),
                escape(dict(job._fields["sync_mode"].selection).get(job.sync_mode, job.sync_mode or "")),
                escape(dict(job._fields["last_status"].selection).get(job.last_status, job.last_status or "")),
                escape(job.last_run_at or "-"),
            )
            for job in jobs
        ) or "<tr><td colspan='5'>No hay trabajos configurados.</td></tr>"
        log_rows = "".join(
            "<li><strong>%s</strong> | %s | %s</li>" % (
                escape(log.name),
                escape(dict(log._fields["status"].selection).get(log.status, log.status or "")),
                escape(log.message or "Sin detalle"),
            )
            for log in recent_logs
        ) or "<li>No hay ejecuciones recientes dentro del rango seleccionado.</li>"
        return (
            "<div class='o_form_label'>"
            "<h3>Control operativo</h3>"
            "<table class='table table-sm table-striped'>"
            "<thead><tr><th>Job</th><th>Recurso</th><th>Modo</th><th>Estado</th><th>Ultima ejecucion</th></tr></thead>"
            "<tbody>%s</tbody>"
            "</table>"
            "<h4>Ultimas ejecuciones relevantes</h4>"
            "<ul>%s</ul>"
            "</div>"
        ) % (job_rows, log_rows)

    def _build_exceptions_html(self, exception_values):
        rows = "".join(
            "<tr><td>%s</td><td class='text-end'>%s</td></tr>" % (escape(item["label"]), item["count"])
            for item in exception_values
        )
        return (
            "<div class='o_form_label'>"
            "<h3>Gestion de excepciones</h3>"
            "<p>Este bloque prioriza registros que requieren correccion para mantener la integridad operativa.</p>"
            "<table class='table table-sm table-striped'>"
            "<thead><tr><th>Excepcion</th><th class='text-end'>Cantidad</th></tr></thead>"
            "<tbody>%s</tbody>"
            "</table>"
            "</div>"
        ) % (rows or "<tr><td colspan='2'>No se detectaron excepciones.</td></tr>")

    def _build_financial_html(self, analytics):
        company_rows = "".join(
            "<tr><td>%s</td><td class='text-end'>%s</td><td class='text-end'>%s</td><td class='text-end'>%s</td></tr>" % (
                escape(item["name"]),
                item["count"],
                escape(self._format_amount(item["amount"])),
                escape(self._format_amount(item["commission"])),
            )
            for item in analytics["top_companies"]
        ) or "<tr><td colspan='4'>Sin datos para el periodo.</td></tr>"
        agent_rows = "".join(
            "<tr><td>%s</td><td>%s</td><td class='text-end'>%s</td><td class='text-end'>%s</td></tr>" % (
                escape(item["name"]),
                escape(item["code"]),
                item["count"],
                escape(self._format_amount(item["amount"])),
            )
            for item in analytics["top_agents"]
        ) or "<tr><td colspan='4'>Sin comisiones estimadas para el periodo.</td></tr>"
        return (
            "<div class='o_form_label'>"
            "<h3>Vision financiera</h3>"
            "<p><strong>Base operada:</strong> %s | <strong>Comision estimada:</strong> %s</p>"
            "<h4>Empresas con mayor volumen</h4>"
            "<table class='table table-sm table-striped'>"
            "<thead><tr><th>Empresa</th><th class='text-end'>Transf.</th><th class='text-end'>Volumen</th><th class='text-end'>Comision</th></tr></thead>"
            "<tbody>%s</tbody>"
            "</table>"
            "<h4>Comisionistas destacados</h4>"
            "<table class='table table-sm table-striped'>"
            "<thead><tr><th>Comisionista</th><th>Codigo</th><th class='text-end'>Interv.</th><th class='text-end'>Comision</th></tr></thead>"
            "<tbody>%s</tbody>"
            "</table>"
            "</div>"
        ) % (
            escape(self._format_amount(analytics["total_amount"])),
            escape(self._format_amount(analytics["commission_total"])),
            company_rows,
            agent_rows,
        )

    def _format_amount(self, amount):
        return "{:,.2f}".format(amount or 0.0)

    def _open_action(self, xmlid, domain=None, context=None):
        action = self.env.ref(xmlid).read()[0]
        if domain is not None:
            action["domain"] = domain
        if context is not None:
            action["context"] = context
        return action

    def action_refresh_dashboard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Centro de Control PagoFlex"),
            "res_model": "pf.gateway.dashboard",
            "view_mode": "form",
            "res_id": self.id,
            "target": "current",
        }

    def action_open_period_transfers(self):
        self.ensure_one()
        return self._open_action("pagoflex_wallet_gateway.action_pf_gateway_transfer", domain=self._period_transfer_domain())

    def action_open_today_transfers(self):
        self.ensure_one()
        today_from, today_to = self._day_bounds(fields.Date.context_today(self))
        return self._open_action(
            "pagoflex_wallet_gateway.action_pf_gateway_transfer",
            domain=[
                ("active", "=", True),
                ("movement_nature", "=", "TRANSFER"),
                ("transaction_at", ">=", today_from),
                ("transaction_at", "<=", today_to),
            ],
        )

    def action_open_failed_sync_jobs(self):
        self.ensure_one()
        return self._open_action(
            "pagoflex_wallet_gateway.action_pf_gateway_sync_job",
            domain=[("active", "=", True), ("last_status", "=", "failed")],
        )

    def action_open_active_companies(self):
        self.ensure_one()
        return self._open_action(
            "pagoflex_wallet_gateway.action_pf_gateway_company",
            domain=[("active", "=", True)],
        )

    def action_open_active_users(self):
        self.ensure_one()
        return self._open_action(
            "pagoflex_wallet_gateway.action_pf_gateway_user",
            domain=[("active", "=", True)],
        )

    def action_open_sync_logs(self):
        self.ensure_one()
        domain = []
        start_dt, end_dt = self._period_bounds()
        if start_dt:
            domain.append(("started_at", ">=", start_dt))
        if end_dt:
            domain.append(("started_at", "<=", end_dt))
        return self._open_action("pagoflex_wallet_gateway.action_pf_gateway_sync_log", domain=domain)

    def action_open_users_without_partner(self):
        self.ensure_one()
        return self._open_action(
            "pagoflex_wallet_gateway.action_pf_gateway_user",
            domain=[("active", "=", True), ("partner_id", "=", False)],
        )

    def action_open_companies_without_partner(self):
        self.ensure_one()
        return self._open_action(
            "pagoflex_wallet_gateway.action_pf_gateway_company",
            domain=[("active", "=", True), ("created_by_user_id", "=", False)],
        )

    def action_open_memberships_without_company(self):
        self.ensure_one()
        return self._open_action(
            "pagoflex_wallet_gateway.action_pf_gateway_company_membership",
            domain=[("active", "=", True), ("company_id", "=", False)],
        )

    def action_open_incomplete_transfers(self):
        self.ensure_one()
        return self._open_action(
            "pagoflex_wallet_gateway.action_pf_gateway_transfer",
            domain=[
                ("active", "=", True),
                "|",
                ("source_bank_account_id", "=", False),
                ("destination_bank_account_id", "=", False),
            ],
        )

    def action_open_unverified_users(self):
        self.ensure_one()
        return self._open_action(
            "pagoflex_wallet_gateway.action_pf_gateway_user",
            domain=[("active", "=", True), ("is_kyc_verified", "=", False)],
        )

    def action_open_commission_report(self):
        self.ensure_one()
        return self._open_action("pagoflex_wallet_gateway.action_pf_gateway_commission_payable_report")
