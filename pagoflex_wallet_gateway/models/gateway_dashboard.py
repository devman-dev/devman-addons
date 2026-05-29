from datetime import datetime, time

from markupsafe import escape

from odoo import _, api, fields, models


class PfGatewayDashboard(models.TransientModel):
    _name = "pf.gateway.dashboard"
    _description = "Centro de Control PagoFlex"

    date_from = fields.Date(string="Desde", default=lambda self: self._default_date_from(), required=True)
    date_to = fields.Date(string="Hasta", default=lambda self: fields.Date.context_today(self), required=True)
    filter_app = fields.Selection(
        selection="_selection_filter_app",
        string="App",
    )
    filter_external_incoming = fields.Boolean(string="Entrantes externas")
    filter_commission_accounts = fields.Boolean(string="Cuentas de comisión")

    kpi_bank_balance = fields.Float(string="Saldo en banco", compute="_compute_dashboard", digits=(16, 2))
    kpi_incoming_volume = fields.Float(string="Volumen entrante", compute="_compute_dashboard", digits=(16, 2))
    kpi_generated_commissions = fields.Float(string="Comisiones generadas", compute="_compute_dashboard", digits=(16, 2))
    kpi_total_transfers = fields.Integer(string="Transferencias totales", compute="_compute_dashboard")
    kpi_active_bank_accounts = fields.Integer(string="Cuentas activas", compute="_compute_dashboard")
    kpi_active_users = fields.Integer(string="Usuarios activos", compute="_compute_dashboard")
    kpi_failed_jobs = fields.Integer(string="Alertas de sync", compute="_compute_dashboard")
    kpi_success_rate = fields.Float(string="Disponibilidad sync", compute="_compute_dashboard", digits=(16, 2))
    kpi_open_exceptions = fields.Integer(string="Excepciones abiertas", compute="_compute_dashboard")
    kpi_transfers_today = fields.Integer(string="Transferencias hoy", compute="_compute_dashboard")
    kpi_amount_today = fields.Float(string="Volumen hoy", compute="_compute_dashboard", digits=(16, 2))
    kpi_period_volume = fields.Float(string="Volumen del periodo", compute="_compute_dashboard", digits=(16, 2))
    kpi_average_ticket = fields.Float(string="Ticket promedio", compute="_compute_dashboard", digits=(16, 2))
    kpi_active_companies = fields.Integer(string="Empresas activas", compute="_compute_dashboard")
    kpi_synced_users = fields.Integer(string="Usuarios activos", compute="_compute_dashboard")
    kpi_estimated_commission = fields.Float(string="Ingresos por comision", compute="_compute_dashboard", digits=(16, 2))

    global_summary_html = fields.Html(string="Resumen global", compute="_compute_dashboard", sanitize=False)
    wallet_summary_html = fields.Html(string="Billeteras", compute="_compute_dashboard", sanitize=False)
    charts_summary_html = fields.Html(string="Analisis del periodo", compute="_compute_dashboard", sanitize=False)
    sync_summary_html = fields.Html(string="Control operativo", compute="_compute_dashboard", sanitize=False)
    exceptions_summary_html = fields.Html(string="Riesgos y excepciones", compute="_compute_dashboard", sanitize=False)
    executive_summary_html = fields.Html(string="Resumen ejecutivo", compute="_compute_dashboard", sanitize=False)
    financial_summary_html = fields.Html(string="Finanzas", compute="_compute_dashboard", sanitize=False)

    @api.model
    def _default_date_from(self):
        today = fields.Date.context_today(self)
        return today.replace(day=1)

    @api.model
    def _selection_filter_app(self):
        app_values = set(
            self.env["pf.gateway.bank.account"].search([("app", "!=", False)]).mapped("app")
        )
        app_values.update(
            self.env["pf.gateway.dashboard.app.config"].search([("app_name", "!=", False)]).mapped("app_name")
        )
        options_by_key = {}
        app_config_model = self.env["pf.gateway.dashboard.app.config"]
        for app_name in app_values:
            app_key = self._app_key(app_name)
            if app_key and app_key not in options_by_key:
                options_by_key[app_key] = app_config_model._display_app_name(app_name)
        return sorted(options_by_key.items(), key=lambda item: item[0])

    @api.depends("date_from", "date_to", "filter_app", "filter_external_incoming", "filter_commission_accounts")
    def _compute_dashboard(self):
        for record in self:
            record._compute_dashboard_values()

    def _compute_dashboard_values(self):
        self.ensure_one()
        bank_account_model = self.env["pf.gateway.bank.account"]
        transfer_model = self.env["pf.gateway.transfer"]
        user_model = self.env["pf.gateway.user"]
        job_model = self.env["pf.gateway.sync.job"]
        log_model = self.env["pf.gateway.sync.log"]

        bank_accounts = bank_account_model.search([])
        active_accounts = bank_accounts.filtered(lambda account: account.status == "active")
        period_transfers = transfer_model.search(self._period_transfer_domain())
        app_configs = self.env["pf.gateway.dashboard.app.config"].search([("active", "=", True)])
        wallet_rows = self._wallet_rows(active_accounts, period_transfers, app_configs)
        filtered_transfers = self._filtered_transfer_records(period_transfers, active_accounts, app_configs)
        visible_accounts = self._visible_active_accounts(active_accounts)
        totals = self._global_totals(wallet_rows, filtered_transfers, visible_accounts, user_model)

        self.kpi_bank_balance = totals["bank_balance"]
        self.kpi_incoming_volume = totals["incoming_volume"]
        self.kpi_generated_commissions = totals["generated_commissions"]
        self.kpi_total_transfers = totals["transfer_count"]
        self.kpi_active_bank_accounts = totals["active_accounts"]
        self.kpi_active_users = totals["active_users"]
        self.kpi_failed_jobs = job_model.search_count([("last_status", "=", "failed"), ("active", "=", True)])
        today_from, today_to = self._day_bounds(fields.Date.context_today(self))
        today_transfers = transfer_model.search(
            [
                ("active", "=", True),
                ("movement_nature", "=", "TRANSFER"),
                ("transaction_at", ">=", today_from),
                ("transaction_at", "<=", today_to),
            ]
        )
        self.kpi_transfers_today = len(today_transfers)
        self.kpi_amount_today = sum(today_transfers.mapped("amount"))
        self.kpi_period_volume = totals["incoming_volume"]
        self.kpi_average_ticket = totals["incoming_volume"] / totals["transfer_count"] if totals["transfer_count"] else 0.0
        self.kpi_active_companies = 0
        self.kpi_synced_users = totals["active_users"]
        self.kpi_estimated_commission = totals["generated_commissions"]

        start_dt, end_dt = self._period_bounds()
        log_domain = []
        if start_dt:
            log_domain.append(("started_at", ">=", start_dt))
        if end_dt:
            log_domain.append(("started_at", "<=", end_dt))
        period_logs = log_model.search(log_domain)
        finished_logs = period_logs.filtered(lambda log: log.status in ("success", "failed"))
        success_logs = finished_logs.filtered(lambda log: log.status == "success")
        self.kpi_success_rate = (len(success_logs) / len(finished_logs) * 100.0) if finished_logs else 100.0

        exception_values = self._exception_values(app_configs)
        self.kpi_open_exceptions = sum(item["count"] for item in exception_values)

        self.global_summary_html = self._build_global_summary_html(totals)
        self.wallet_summary_html = self._build_wallet_summary_html(wallet_rows)
        self.charts_summary_html = self._build_charts_summary_html(wallet_rows)
        self.sync_summary_html = self._build_sync_summary_html(job_model.search([], order="sequence, id"), period_logs)
        self.exceptions_summary_html = self._build_exceptions_html(exception_values)
        self.executive_summary_html = self.global_summary_html + self.wallet_summary_html + self.charts_summary_html
        self.financial_summary_html = self.charts_summary_html

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
        domain = [("active", "=", True)]
        start_dt, end_dt = self._period_bounds()
        if start_dt:
            domain.append(("transaction_at", ">=", start_dt))
        if end_dt:
            domain.append(("transaction_at", "<=", end_dt))
        return domain

    def _wallet_rows(self, active_accounts, period_transfers, app_configs):
        app_keys = {self._app_key(app_name) for app_name in active_accounts.mapped("app")}
        app_keys.update(self._app_key(app_name) for app_name in app_configs.mapped("app_name"))
        app_keys = sorted(app_key for app_key in app_keys if app_key)
        if self.filter_app:
            app_keys = [app_key for app_key in app_keys if app_key == self.filter_app]
        rows = []
        config_by_app = {self._app_key(config.app_name): config for config in app_configs}
        all_account_ids = set(active_accounts.ids)

        for index, app_key in enumerate(app_keys):
            config = config_by_app.get(app_key)
            display_app_name = config.app_name if config else app_key
            app_accounts = active_accounts.filtered(lambda account, key=app_key: self._app_key(account.app) == key)
            app_account_ids = set(app_accounts.ids)
            incoming_transfers = period_transfers.filtered(
                lambda transfer, account_ids=app_account_ids: self._is_external_incoming_transfer(
                    transfer,
                    account_ids,
                    all_account_ids,
                )
            )
            commission_account = config.commission_bank_account_id if config else self.env["pf.gateway.bank.account"]
            commission_transfers = period_transfers.filtered(
                lambda transfer, account=commission_account: self._is_commission_transfer_for_account(transfer, account)
            )
            visible_app_transfers = period_transfers.filtered(
                lambda transfer, account_ids=app_account_ids, account=commission_account: self._matches_transfer_filters(
                    transfer,
                    account_ids,
                    all_account_ids,
                    account,
                )
            )
            balance = 0.0
            incoming_volume = sum(incoming_transfers.mapped("amount"))
            generated_commissions = sum(commission_transfers.mapped("amount"))
            user_count = len(set(app_accounts.mapped("gateway_user_id").ids))
            last_sync_values = [
                value
                for value in app_accounts.mapped("balance_last_check_at")
                + app_accounts.mapped("last_sync_at")
                if value
            ]
            rows.append(
                {
                    "app_name": app_key,
                    "display_name": self._display_app_name(display_app_name),
                    "color": "blue" if index % 2 == 0 else "green",
                    "bank_balance": balance,
                    "incoming_volume": incoming_volume,
                    "generated_commissions": generated_commissions,
                    "transfer_count": len(visible_app_transfers),
                    "active_accounts": len(app_accounts),
                    "active_users": user_count,
                    "sync_label": _("Sincronizado") if app_accounts else _("Sin cuentas"),
                    "last_sync": max(last_sync_values) if last_sync_values else False,
                    "commission_account": commission_account,
                }
            )
        return rows

    def _global_totals(self, wallet_rows, period_transfers, active_accounts, user_model):
        active_user_domain = [("active", "=", True)]
        if self.filter_app:
            user_ids = active_accounts.mapped("gateway_user_id").ids
            active_user_domain.append(("id", "in", user_ids or [0]))
        return {
            "bank_balance": 0.0,
            "incoming_volume": sum(row["incoming_volume"] for row in wallet_rows),
            "generated_commissions": sum(row["generated_commissions"] for row in wallet_rows),
            "transfer_count": len(period_transfers),
            "active_accounts": len(active_accounts),
            "active_users": user_model.search_count(active_user_domain),
        }

    def _visible_active_accounts(self, active_accounts):
        if not self.filter_app:
            return active_accounts
        return active_accounts.filtered(lambda account: self._app_key(account.app) == self.filter_app)

    def _filtered_transfer_records(self, period_transfers, active_accounts, app_configs):
        visible_accounts = self._visible_active_accounts(active_accounts)
        visible_account_ids = set(visible_accounts.ids)
        all_account_ids = set(active_accounts.ids)
        commission_accounts = app_configs.filtered(
            lambda config: (
                config.commission_bank_account_id
                and (not self.filter_app or self._app_key(config.app_name) == self.filter_app)
            )
        ).mapped("commission_bank_account_id")

        return period_transfers.filtered(
            lambda transfer: self._matches_global_transfer_filters(
                transfer,
                visible_account_ids,
                all_account_ids,
                commission_accounts,
            )
        )

    def _matches_global_transfer_filters(self, transfer, visible_account_ids, all_account_ids, commission_accounts):
        if self.filter_app and not (
            transfer.source_bank_account_id.id in visible_account_ids
            or transfer.destination_bank_account_id.id in visible_account_ids
        ):
            return False

        use_scope_filters = self.filter_external_incoming or self.filter_commission_accounts
        if not use_scope_filters:
            return transfer.movement_nature == "TRANSFER"

        matches_external = (
            self.filter_external_incoming
            and self._is_external_incoming_transfer(transfer, visible_account_ids, all_account_ids)
        )
        matches_commission = (
            self.filter_commission_accounts
            and self._is_any_commission_account_transfer(transfer, commission_accounts)
        )
        return bool(matches_external or matches_commission)

    def _matches_transfer_filters(self, transfer, app_account_ids, all_account_ids, commission_account):
        use_scope_filters = self.filter_external_incoming or self.filter_commission_accounts
        if not use_scope_filters:
            return (
                transfer.movement_nature == "TRANSFER"
                and (
                    transfer.source_bank_account_id.id in app_account_ids
                    or transfer.destination_bank_account_id.id in app_account_ids
                )
            )

        matches_external = (
            self.filter_external_incoming
            and self._is_external_incoming_transfer(transfer, app_account_ids, all_account_ids)
        )
        matches_commission = (
            self.filter_commission_accounts
            and self._is_commission_account_transfer(transfer, commission_account)
        )
        return bool(matches_external or matches_commission)

    def _is_external_incoming_transfer(self, transfer, app_account_ids, all_account_ids):
        if transfer.movement_nature != "TRANSFER":
            return False
        if (transfer.status or "").upper() != "COMPLETED":
            return False
        if transfer.destination_bank_account_id.id not in app_account_ids:
            return False
        return transfer.source_bank_account_id.id not in all_account_ids

    def _is_commission_transfer_for_account(self, transfer, commission_account):
        if not commission_account:
            return False
        if transfer.movement_nature != "COMMISSION":
            return False
        return self._is_commission_account_transfer(transfer, commission_account)

    def _is_commission_account_transfer(self, transfer, commission_account):
        if not commission_account:
            return False
        return (
            transfer.source_bank_account_id == commission_account
            or transfer.destination_bank_account_id == commission_account
        )

    def _is_any_commission_account_transfer(self, transfer, commission_accounts):
        if not commission_accounts:
            return False
        return (
            transfer.source_bank_account_id in commission_accounts
            or transfer.destination_bank_account_id in commission_accounts
        )

    def _exception_values(self, app_configs):
        configured_apps = {self._app_key(config.app_name) for config in app_configs if config.commission_bank_account_id}
        account_apps = set(
            self._app_key(app_name)
            for app_name in self.env["pf.gateway.bank.account"].search(
                [("status", "=", "active"), ("app", "!=", False)]
            ).mapped("app")
        )
        missing_commission_apps = account_apps - configured_apps
        return [
            {
                "label": _("Apps sin cuenta de comisiones configurada"),
                "count": len(missing_commission_apps),
                "priority": _("Alta"),
            },
            {
                "label": _("Transferencias con vinculacion incompleta"),
                "count": self.env["pf.gateway.transfer"].search_count(
                    [
                        ("active", "=", True),
                        "|",
                        ("source_bank_account_id", "=", False),
                        ("destination_bank_account_id", "=", False),
                    ]
                ),
                "priority": _("Media"),
            },
            {
                "label": _("Cuentas activas sin saldo actualizado"),
                "count": self.env["pf.gateway.bank.account"].search_count(
                    [("status", "=", "active"), ("balance_sync_status", "in", ["never", "error", "no_balance", "not_found"])]
                ),
                "priority": _("Media"),
            },
            {
                "label": _("Usuarios sin verificacion KYC"),
                "count": self.env["pf.gateway.user"].search_count([("active", "=", True), ("is_kyc_verified", "=", False)]),
                "priority": _("Baja"),
            },
        ]

    def _build_global_summary_html(self, totals):
        cards = [
            ("bank", _("Saldo total en banco"), _("No disponible"), _("Pendiente de nueva fuente"), "blue"),
            ("arrow-circle-down", _("Volumen entrante del periodo"), self._format_money(totals["incoming_volume"]), _("Solo ingresos externos"), "green"),
            ("money", _("Comisiones generadas"), self._format_money(totals["generated_commissions"]), _("Acumulado del periodo"), "purple"),
            ("exchange", _("Transferencias totales"), self._format_int(totals["transfer_count"]), _("Todas las billeteras"), "blue"),
            ("credit-card", _("Cuentas activas"), self._format_int(totals["active_accounts"]), _("Cuentas operativas"), "green"),
            ("user", _("Usuarios activos"), self._format_int(totals["active_users"]), _("Usuarios registrados"), "purple"),
        ]
        return (
            "<section class='pf_dashboard_panel pf_dashboard_global'>"
            "<div class='pf_dashboard_panel_header'><h2>%s</h2></div>"
            "<div class='pf_dashboard_metric_strip'>%s</div>"
            "</section>"
        ) % (
            escape(_("Resumen global (todas las billeteras)")),
            "".join(self._metric_card_html(icon, label, value, helper, color) for icon, label, value, helper, color in cards),
        )

    def _build_wallet_summary_html(self, rows):
        if not rows:
            return (
                "<section class='pf_dashboard_wallets'>"
                "<div class='pf_dashboard_section_heading'><h2>%s</h2><span>%s</span></div>"
                "<div class='pf_dashboard_empty'>%s</div>"
                "</section>"
            ) % (
                escape(_("Billeteras")),
                escape(_("Informacion separada por billetera")),
                escape(_("No hay cuentas activas con app para mostrar.")),
            )
        return (
            "<section class='pf_dashboard_wallets'>"
            "<div class='pf_dashboard_section_heading'><h2>%s</h2><span>%s</span></div>"
            "<div class='pf_dashboard_wallet_grid'>%s</div>"
            "</section>"
        ) % (
            escape(_("Billeteras")),
            escape(_("Informacion separada por billetera")),
            "".join(self._wallet_card_html(row) for row in rows),
        )

    def _wallet_card_html(self, row):
        return (
            "<article class='pf_dashboard_wallet_card pf_dashboard_wallet_%s'>"
            "<div class='pf_dashboard_wallet_title'><i class='fa fa-credit-card'></i><h3>%s</h3></div>"
            "<div class='pf_dashboard_wallet_metrics'>"
            "%s%s%s%s%s%s%s"
            "</div>"
            "</article>"
        ) % (
            escape(row["color"]),
            escape(row["display_name"]),
            self._compact_metric_html(_("Saldo en banco"), _("No disponible"), _("Pendiente de nueva fuente")),
            self._compact_metric_html(_("Volumen entrante"), self._format_money(row["incoming_volume"]), _("Solo ingresos externos")),
            self._compact_metric_html(_("Comisiones generadas"), self._format_money(row["generated_commissions"]), _("Acumulado del periodo")),
            self._compact_metric_html(_("Transferencias"), self._format_int(row["transfer_count"]), _("Total periodo")),
            self._compact_metric_html(_("Cuentas activas"), self._format_int(row["active_accounts"]), ""),
            self._compact_metric_html(_("Usuarios activos"), self._format_int(row["active_users"]), ""),
            self._compact_metric_html(_("Estado de sync"), escape(row["sync_label"]), self._last_sync_label(row["last_sync"])),
        )

    def _build_charts_summary_html(self, rows):
        if not rows:
            return ""
        max_incoming = max([row["incoming_volume"] for row in rows] or [0.0]) or 1.0
        max_commission = max([row["generated_commissions"] for row in rows] or [0.0]) or 1.0
        transfer_total = sum(row["transfer_count"] for row in rows) or 1
        incoming_rows = "".join(
            self._bar_row_html(row["display_name"], row["incoming_volume"], max_incoming, row["color"])
            for row in rows
        )
        commission_rows = "".join(
            self._bar_row_html(row["display_name"], row["generated_commissions"], max_commission, row["color"])
            for row in rows
        )
        transfer_rows = "".join(
            "<div class='pf_dashboard_distribution_row'><span>%s</span><strong>%s</strong><small>%s%%</small></div>"
            % (
                escape(row["display_name"]),
                escape(self._format_int(row["transfer_count"])),
                escape(self._format_percent(row["transfer_count"] / transfer_total * 100.0)),
            )
            for row in rows
        )
        return (
            "<section class='pf_dashboard_analysis_grid'>"
            "<article class='pf_dashboard_panel'><div class='pf_dashboard_panel_header'><h2>%s</h2><strong>%s</strong></div>%s</article>"
            "<article class='pf_dashboard_panel'><div class='pf_dashboard_panel_header'><h2>%s</h2><strong>%s</strong></div>%s</article>"
            "<article class='pf_dashboard_panel'><div class='pf_dashboard_panel_header'><h2>%s</h2><strong>%s</strong></div>%s</article>"
            "</section>"
        ) % (
            escape(_("Volumen entrante")),
            escape(self._format_money(sum(row["incoming_volume"] for row in rows))),
            incoming_rows,
            escape(_("Comisiones generadas")),
            escape(self._format_money(sum(row["generated_commissions"] for row in rows))),
            commission_rows,
            escape(_("Transferencias del periodo")),
            escape(self._format_int(sum(row["transfer_count"] for row in rows))),
            transfer_rows,
        )

    def _build_sync_summary_html(self, jobs, logs):
        finished_logs = logs.filtered(lambda log: log.status in ("success", "failed"))
        last_update = max([log.finished_at for log in finished_logs if log.finished_at] or [False])
        return (
            "<article class='pf_dashboard_panel'><div class='pf_dashboard_panel_header'><h2>%s</h2></div>"
            "<div class='pf_dashboard_ops_grid'>%s%s%s</div></article>"
        ) % (
            escape(_("Control operativo")),
            self._ops_tile_html("refresh", _("Disponibilidad sync"), "%s %%" % self._format_percent(self.kpi_success_rate), _("Estado operativo")),
            self._ops_tile_html("warning", _("Alertas de sync"), self._format_int(self.kpi_failed_jobs), _("Jobs con error")),
            self._ops_tile_html("clock-o", _("Ultima actualizacion"), escape(self._last_sync_label(last_update)), _("Logs del periodo")),
        )

    def _build_exceptions_html(self, exception_values):
        rows = "".join(
            "<div class='pf_dashboard_exception_row'><span>%s</span><strong>%s</strong><small>%s</small></div>"
            % (escape(item["label"]), escape(self._format_int(item["count"])), escape(item["priority"]))
            for item in exception_values
        )
        return (
            "<article class='pf_dashboard_panel'><div class='pf_dashboard_panel_header'><h2>%s</h2></div>"
            "<div class='pf_dashboard_exception_total'><i class='fa fa-shield'></i><strong>%s</strong><span>%s</span></div>"
            "<div class='pf_dashboard_exception_list'>%s</div></article>"
        ) % (
            escape(_("Riesgos y excepciones")),
            escape(self._format_int(self.kpi_open_exceptions)),
            escape(_("Excepciones abiertas")),
            rows,
        )

    def _metric_card_html(self, icon, label, value, helper, color):
        return (
            "<div class='pf_dashboard_metric pf_dashboard_metric_%s'>"
            "<i class='fa fa-%s'></i><div><span>%s</span><strong>%s</strong><small>%s</small></div>"
            "</div>"
        ) % (escape(color), escape(icon), escape(label), escape(value), escape(helper))

    def _compact_metric_html(self, label, value, helper):
        return (
            "<div class='pf_dashboard_compact_metric'><span>%s</span><strong>%s</strong><small>%s</small></div>"
        ) % (escape(label), value, escape(helper))

    def _bar_row_html(self, label, value, max_value, color):
        width = min(100.0, max(2.0, value / max_value * 100.0)) if value else 2.0
        return (
            "<div class='pf_dashboard_bar_row'><div><span>%s</span><strong>%s</strong></div>"
            "<div class='pf_dashboard_bar'><span class='pf_dashboard_bar_%s' style='width: %.2f%%'></span></div></div>"
        ) % (escape(label), escape(self._format_money(value)), escape(color), width)

    def _ops_tile_html(self, icon, label, value, helper):
        return (
            "<div class='pf_dashboard_ops_tile'><i class='fa fa-%s'></i><strong>%s</strong><span>%s</span><small>%s</small></div>"
        ) % (escape(icon), value, escape(label), escape(helper))

    def _display_app_name(self, app_name):
        return self.env["pf.gateway.dashboard.app.config"]._display_app_name(app_name)

    def _app_key(self, app_name):
        return (app_name or "").strip().lower()

    def _format_money(self, amount):
        return "$ %s" % self._format_number(amount or 0.0, decimals=2)

    def _format_int(self, value):
        return self._format_number(value or 0, decimals=0)

    def _format_percent(self, value):
        return self._format_number(value or 0.0, decimals=2)

    def _format_number(self, value, decimals=2):
        formatted = f"{value:,.{decimals}f}"
        return formatted.replace(",", "X").replace(".", ",").replace("X", ".")

    def _last_sync_label(self, value):
        if not value:
            return _("Sin datos")
        return _("Hoy %s") % fields.Datetime.context_timestamp(self, value).strftime("%H:%M")

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

    def action_open_sync_logs(self):
        self.ensure_one()
        domain = []
        start_dt, end_dt = self._period_bounds()
        if start_dt:
            domain.append(("started_at", ">=", start_dt))
        if end_dt:
            domain.append(("started_at", "<=", end_dt))
        return self._open_action("pagoflex_wallet_gateway.action_pf_gateway_sync_log", domain=domain)

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

    def action_open_active_users(self):
        self.ensure_one()
        return self._open_action("pagoflex_wallet_gateway.action_pf_gateway_user", domain=[("active", "=", True)])

    def action_open_active_companies(self):
        self.ensure_one()
        return self.action_open_active_users()

    def action_open_active_bank_accounts(self):
        self.ensure_one()
        return self._open_action("pagoflex_wallet_gateway.action_pf_gateway_bank_account", domain=[("status", "=", "active")])

    def action_open_dashboard_app_config(self):
        self.ensure_one()
        return self._open_action("pagoflex_wallet_gateway.action_pf_gateway_dashboard_app_config")

    def action_open_users_without_partner(self):
        self.ensure_one()
        return self._open_action(
            "pagoflex_wallet_gateway.action_pf_gateway_user",
            domain=[("active", "=", True), ("partner_id", "=", False)],
        )

    def action_open_companies_without_partner(self):
        self.ensure_one()
        return self.action_open_users_without_partner()

    def action_open_memberships_without_company(self):
        self.ensure_one()
        return self.action_open_dashboard_app_config()

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
        return self.action_open_dashboard_app_config()
