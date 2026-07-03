from datetime import datetime, time

from markupsafe import escape

from odoo import _, api, fields, models
from odoo.osv import expression
from odoo.tools import format_date

import time as std_time

_DASHBOARD_CACHE = {}
_DASHBOARD_CACHE_TTL = 30  # segundos de caché para evitar sobrecarga


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
    kpi_outgoing_volume = fields.Float(string="Volumen saliente", compute="_compute_dashboard", digits=(16, 2))
    kpi_generated_commissions = fields.Float(string="Comisiones generadas", compute="_compute_dashboard", digits=(16, 2))
    kpi_net_period_flow = fields.Float(string="Flujo neto del periodo", compute="_compute_dashboard", digits=(16, 2))
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
    reconciliation_summary_html = fields.Html(string="Conciliacion operativa", compute="_compute_dashboard", sanitize=False)
    temporal_reconciliation_html = fields.Html(string="Evolucion temporal", compute="_compute_dashboard", sanitize=False)
    transaction_count_summary_html = fields.Html(string="Conteo operativo", compute="_compute_dashboard", sanitize=False)
    sync_summary_html = fields.Html(string="Control operativo", compute="_compute_dashboard", sanitize=False)
    exceptions_summary_html = fields.Html(string="Riesgos y excepciones", compute="_compute_dashboard", sanitize=False)
    top_users_summary_html = fields.Html(string="Usuarios destacados", compute="_compute_dashboard", sanitize=False)
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
        wallet_rows = self._wallet_rows(bank_accounts, active_accounts, period_transfers, app_configs)
        filtered_transfers = self._filtered_transfer_records(period_transfers, bank_accounts, app_configs)
        visible_accounts = self._visible_active_accounts(active_accounts)
        totals = self._global_totals(wallet_rows, filtered_transfers, visible_accounts, user_model)
        period_bank_movements = self._period_bank_movements(bank_accounts)
        reconciliation_rows = self._reconciliation_rows(totals, period_bank_movements, period_transfers, bank_accounts)
        transaction_count_rows = self._transaction_count_rows(period_transfers, bank_accounts, period_bank_movements)
        temporal_rows = self._temporal_reconciliation_rows(period_transfers, bank_accounts, period_bank_movements)

        self.kpi_bank_balance = totals["bank_balance"]
        self.kpi_incoming_volume = totals["incoming_volume"]
        self.kpi_outgoing_volume = totals["outgoing_volume"]
        self.kpi_generated_commissions = totals["generated_commissions"]
        self.kpi_net_period_flow = totals["net_period_flow"]
        self.kpi_total_transfers = totals["transfer_count"]
        self.kpi_active_bank_accounts = totals["active_accounts"]
        self.kpi_active_users = totals["active_users"]
        self.kpi_failed_jobs = job_model.search_count([("last_status", "=", "failed"), ("active", "=", True)])
        today = fields.Date.context_today(self)
        today_transfers = transfer_model.search(
            expression.AND(
                [
                    [("active", "=", True), ("movement_nature", "=", "TRANSFER")],
                    self._transfer_business_period_domain(today, today),
                ]
            )
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
        self.reconciliation_summary_html = self._build_reconciliation_summary_html(reconciliation_rows)
        self.temporal_reconciliation_html = self._build_temporal_reconciliation_html(temporal_rows)
        self.transaction_count_summary_html = self._build_transaction_count_summary_html(transaction_count_rows)
        self.sync_summary_html = self._build_sync_summary_html(job_model.search([], order="sequence, id"), period_logs)
        self.exceptions_summary_html = self._build_exceptions_html(exception_values)
        self.top_users_summary_html = self._build_top_users_summary_html(period_transfers, bank_accounts)
        self.executive_summary_html = (
            self.global_summary_html
            + self.wallet_summary_html
            + self.top_users_summary_html
            + self.charts_summary_html
            + self.reconciliation_summary_html
            + self.temporal_reconciliation_html
            + self.transaction_count_summary_html
        )
        self.financial_summary_html = (
            self.charts_summary_html
            + self.reconciliation_summary_html
            + self.temporal_reconciliation_html
            + self.transaction_count_summary_html
        )

    @api.model
    def get_realtime_charts_data(self, date_from_str, date_to_str, periodicity='daily', filter_app=False, date_basis='business'):
        """
        Endpoint optimizado para Chart.js.
        Retorna datos agrupados por app y fecha.
        Incluye caché temporal para evitar consultas pesadas continuas.
        """
        date_basis = date_basis if date_basis in ("business", "transaction") else "business"
        cache_key = f"{date_from_str}_{date_to_str}_{periodicity}_{filter_app}_{date_basis}"
        now = std_time.time()
        
        # Retornar de caché si es válido
        if cache_key in _DASHBOARD_CACHE:
            cached_data, timestamp = _DASHBOARD_CACHE[cache_key]
            if now - timestamp < _DASHBOARD_CACHE_TTL:
                return cached_data

        date_from = fields.Date.from_string(date_from_str) if date_from_str else False
        date_to = fields.Date.from_string(date_to_str) if date_to_str else False
        
        domain_base = [('active', '=', True)]
        period_domain = self._transfer_chart_period_domain(date_from, date_to, date_basis)
        if period_domain:
            domain_base = expression.AND([domain_base, period_domain])
            
        transfer_model = self.env["pf.gateway.transfer"]
        
        # Buscar todas las transferencias del periodo para procesar en memoria
        # Es más eficiente que múltiples queries SQL complejas
        period_transfers = transfer_model.search(domain_base)
        
        app_configs = self.env["pf.gateway.dashboard.app.config"].search([("active", "=", True)])
        bank_accounts = self.env["pf.gateway.bank.account"].search([])
        active_accounts = bank_accounts.filtered(lambda a: a.status == "active")
        
        app_keys = {self._app_key(app_name) for app_name in bank_accounts.mapped("app")}
        app_keys.update(self._app_key(app_name) for app_name in app_configs.mapped("app_name"))
        app_keys = sorted(app_key for app_key in app_keys if app_key)
        
        if filter_app:
            app_keys = [app_key for app_key in app_keys if app_key == filter_app]
            
        config_by_app = {self._app_key(config.app_name): config for config in app_configs}
        all_account_ids = set(bank_accounts.ids)
        
        # Generar etiquetas de tiempo
        labels_dict = self._generate_time_labels(date_from, date_to, periodicity)
        labels = list(labels_dict.keys())
        
        result = {
            'last_update': fields.Datetime.now().isoformat() + 'Z',
            'volumen_entrante': {
                'labels': list(labels_dict.values()),
                'datasets': []
            },
            'comisiones': {
                'labels': list(labels_dict.values()),
                'datasets': []
            },
            'transferencias': {
                'labels': [],
                'datasets': [{'data': [], 'backgroundColor': []}],
                'total': 0
            }
        }
        
        colors = ['#4e73df', '#1cc88a', '#36b9cc', '#f6c23e', '#e74a3b', '#6f42c1', '#fd7e14']
        
        transfer_total = 0
        
        for index, app_key in enumerate(app_keys):
            config = config_by_app.get(app_key)
            display_app_name = config.app_name if config else app_key
            display_app_name = self._display_app_name(display_app_name)
            color = colors[index % len(colors)]
            
            app_all_accounts = bank_accounts.filtered(lambda account, key=app_key: self._app_key(account.app) == key)
            app_account_ids = set(app_all_accounts.ids)
            
            # Filtros por app
            incoming_transfers = period_transfers.filtered(
                lambda t, account_ids=app_account_ids: self._is_external_incoming_transfer(t, account_ids, all_account_ids)
            )
            
            commission_account = config.commission_bank_account_id if config else self.env["pf.gateway.bank.account"]
            commission_transfers = period_transfers.filtered(
                lambda t, account=commission_account: self._is_commission_transfer_for_account(t, account)
            )
            
            visible_app_transfers = period_transfers.filtered(
                lambda t, account_ids=app_account_ids, account=commission_account: self._matches_transfer_filters(
                    t, account_ids, all_account_ids, account
                )
            )
            
            # Agrupar volumen entrante
            vol_data = {label: 0.0 for label in labels}
            for t in incoming_transfers:
                key = self._get_time_key(self._transfer_chart_day(t, date_basis), periodicity)
                if key in vol_data:
                    vol_data[key] += t.amount or 0.0
                    
            volumen_total = sum(vol_data.values())
            result['volumen_entrante']['datasets'].append({
                'label': display_app_name,
                'data': list(vol_data.values()),
                'total': volumen_total,
                'borderColor': color,
                'backgroundColor': color,
                'fill': False,
                'tension': 0.4
            })
            
            # Agrupar comisiones
            com_data = {label: 0.0 for label in labels}
            for t in commission_transfers:
                key = self._get_time_key(self._transfer_chart_day(t, date_basis), periodicity)
                if key in com_data:
                    com_data[key] += t.amount or 0.0
                    
            comisiones_total = sum(com_data.values())
            result['comisiones']['datasets'].append({
                'label': display_app_name,
                'data': list(com_data.values()),
                'total': comisiones_total,
                'borderColor': color,
                'backgroundColor': color,
                'fill': False,
                'tension': 0.4
            })
            
            # Transferencias (Dona)
            app_transfer_count = len(visible_app_transfers)
            if app_transfer_count > 0:
                result['transferencias']['labels'].append(display_app_name)
                result['transferencias']['datasets'][0]['data'].append(app_transfer_count)
                result['transferencias']['datasets'][0]['backgroundColor'].append(color)
                transfer_total += app_transfer_count
                
        result['transferencias']['total'] = transfer_total
        
        # Guardar en caché
        _DASHBOARD_CACHE[cache_key] = (result, now)
        
        return result

    def _generate_time_labels(self, date_from, date_to, periodicity):
        from datetime import timedelta
        labels_dict = {}
        if not date_from or not date_to:
            return labels_dict
            
        current = date_from
        while current <= date_to:
            key = self._get_time_key(current, periodicity)
            if key not in labels_dict:
                if periodicity == 'daily':
                    labels_dict[key] = current.strftime('%d/%m')
                elif periodicity == 'weekly':
                    labels_dict[key] = f"Semana {current.isocalendar()[1]}"
                elif periodicity == 'monthly':
                    labels_dict[key] = current.strftime('%m/%Y')
            current += timedelta(days=1)
        return labels_dict

    def _get_time_key(self, date_obj, periodicity):
        if not date_obj:
            return 'unknown'
        if periodicity == 'daily':
            return date_obj.strftime('%Y-%m-%d')
        elif periodicity == 'weekly':
            return f"{date_obj.isocalendar()[0]}-W{date_obj.isocalendar()[1]}"
        elif periodicity == 'monthly':
            return date_obj.strftime('%Y-%m')
        return date_obj.strftime('%Y-%m-%d')

    def _transfer_chart_period_domain(self, date_from=False, date_to=False, date_basis="business"):
        if date_basis == "transaction":
            domain = []
            if date_from:
                domain.append(("transaction_at", ">=", datetime.combine(date_from, time.min)))
            if date_to:
                domain.append(("transaction_at", "<=", datetime.combine(date_to, time.max)))
            return domain
        return self._transfer_business_period_domain(date_from, date_to)

    def _transfer_chart_day(self, transfer, date_basis="business"):
        if date_basis == "transaction":
            return transfer.transaction_at.date() if transfer.transaction_at else False
        return self._transfer_period_day(transfer)

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
        period_domain = self._transfer_business_period_domain(self.date_from, self.date_to)
        if period_domain:
            domain = expression.AND([domain, period_domain])
        return domain

    def _transfer_business_period_domain(self, date_from=False, date_to=False):
        business_domain = []
        fallback_domain = [("fecha_negocio", "=", False)]
        if date_from:
            business_domain.append(("fecha_negocio", ">=", date_from))
        if date_to:
            business_domain.append(("fecha_negocio", "<=", date_to))
        start_dt = datetime.combine(date_from, time.min) if date_from else False
        end_dt = datetime.combine(date_to, time.max) if date_to else False
        if start_dt:
            fallback_domain.append(("transaction_at", ">=", start_dt))
        if end_dt:
            fallback_domain.append(("transaction_at", "<=", end_dt))
        if not business_domain:
            return []
        return expression.OR([business_domain, fallback_domain])

    def _period_bank_movement_domain(self):
        domain = [("active", "=", True)]
        if self.date_from:
            domain.append(("movement_date", ">=", self.date_from))
        if self.date_to:
            domain.append(("movement_date", "<=", self.date_to))
        return domain

    def _period_bank_movement_amount(self):
        result = self.env["pf.gateway.bank.movement"].read_group(
            self._period_bank_movement_domain(),
            ["amount:sum"],
            [],
        )
        return result[0]["amount"] if result else 0.0

    def _period_bank_movements(self, bank_accounts):
        movements = self.env["pf.gateway.bank.movement"].search(self._period_bank_movement_domain())
        if not self.filter_app:
            return movements
        visible_account_ids = set(self._visible_bank_accounts(bank_accounts).ids)
        return movements.filtered(
            lambda movement: not movement.bank_account_id or movement.bank_account_id.id in visible_account_ids
        )

    def _reconciliation_rows(self, totals, bank_movements, period_transfers=None, bank_accounts=None):
        period_transfers = period_transfers or self.env["pf.gateway.transfer"]
        bank_accounts = bank_accounts or self.env["pf.gateway.bank.account"]
        visible_account_ids = set(self._visible_bank_accounts(bank_accounts).ids)
        all_account_ids = set(bank_accounts.ids)
        external_incoming_transfers = period_transfers.filtered(
            lambda transfer: self._is_external_incoming_transfer(transfer, visible_account_ids, all_account_ids)
        )
        external_outgoing_transfers = period_transfers.filtered(
            lambda transfer: self._is_external_outgoing_transfer(transfer, visible_account_ids, all_account_ids)
        )
        external_incoming_ids = set(external_incoming_transfers.ids)
        external_outgoing_ids = set(external_outgoing_transfers.ids)
        bank_incoming_movements = bank_movements.filtered(
            lambda movement: self._is_bank_incoming_movement(movement)
        )
        bank_incoming_matched = bank_incoming_movements.filtered(
            lambda movement: movement.matched_transfer_id.id in external_incoming_ids
        )
        bank_incoming_unmatched = bank_incoming_movements.filtered(lambda movement: not movement.matched_transfer_id)
        bank_incoming_not_comparable = bank_incoming_movements - bank_incoming_matched - bank_incoming_unmatched
        bank_incoming = sum(abs(movement.amount or 0.0) for movement in bank_incoming_movements)
        bank_incoming_unmatched_amount = sum(abs(movement.amount or 0.0) for movement in bank_incoming_unmatched)
        bank_incoming_not_comparable_amount = sum(
            abs(movement.amount or 0.0) for movement in bank_incoming_not_comparable
        )
        bank_outgoing_movements = bank_movements.filtered(lambda movement: self._is_bank_outgoing_movement(movement))
        bank_outgoing_matched = bank_outgoing_movements.filtered(
            lambda movement: movement.matched_transfer_id.id in external_outgoing_ids
        )
        bank_outgoing_unmatched = bank_outgoing_movements.filtered(lambda movement: not movement.matched_transfer_id)
        bank_outgoing_not_comparable = bank_outgoing_movements - bank_outgoing_matched - bank_outgoing_unmatched
        bank_outgoing = sum(abs(movement.amount or 0.0) for movement in bank_outgoing_movements)
        bank_outgoing_unmatched_amount = sum(abs(movement.amount or 0.0) for movement in bank_outgoing_unmatched)
        bank_outgoing_not_comparable_amount = sum(
            abs(movement.amount or 0.0) for movement in bank_outgoing_not_comparable
        )
        bank_net_flow = sum(movement.amount or 0.0 for movement in bank_movements)
        wallet_net_flow = totals["net_period_flow"]
        return [
            self._reconciliation_row(
                _("Importes entrantes"),
                totals["incoming_volume"],
                bank_incoming,
            ),
            self._reconciliation_row(
                _("Importes salientes"),
                totals["outgoing_volume"],
                bank_outgoing,
            ),
            self._reconciliation_row(
                _("Comisiones"),
                totals["generated_commissions"],
                0.0,
            ),
            self._reconciliation_row(
                _("Flujo neto del periodo"),
                wallet_net_flow,
                bank_net_flow,
            ),
            self._reconciliation_row(
                _("Banco creditos sin transferencia vinculada"),
                0.0,
                bank_incoming_unmatched_amount,
            ),
            self._reconciliation_row(
                _("Banco debitos sin transferencia vinculada"),
                0.0,
                bank_outgoing_unmatched_amount,
            ),
            self._reconciliation_row(
                _("Banco creditos no comparables"),
                0.0,
                bank_incoming_not_comparable_amount,
            ),
            self._reconciliation_row(
                _("Banco debitos no comparables"),
                0.0,
                bank_outgoing_not_comparable_amount,
            ),
        ]

    def _transaction_count_rows(self, period_transfers, bank_accounts, bank_movements):
        visible_account_ids = set(self._visible_bank_accounts(bank_accounts).ids)
        all_account_ids = set(bank_accounts.ids)
        external_incoming_transfers = period_transfers.filtered(
            lambda transfer: self._is_external_incoming_transfer(transfer, visible_account_ids, all_account_ids)
        )
        external_outgoing_transfers = period_transfers.filtered(
            lambda transfer: self._is_external_outgoing_transfer(transfer, visible_account_ids, all_account_ids)
        )
        commission_transfers = period_transfers.filtered(
            lambda transfer: transfer.movement_nature == "COMMISSION" and (transfer.status or "").upper() != "FAILED"
        )
        bank_incoming_movements = bank_movements.filtered(
            lambda movement: self._is_bank_incoming_movement(movement)
        )
        external_incoming_ids = set(external_incoming_transfers.ids)
        external_outgoing_ids = set(external_outgoing_transfers.ids)
        bank_incoming_matched = bank_incoming_movements.filtered(
            lambda movement: movement.matched_transfer_id.id in external_incoming_ids
        )
        bank_incoming_unmatched = bank_incoming_movements.filtered(lambda movement: not movement.matched_transfer_id)
        bank_incoming_not_comparable = bank_incoming_movements - bank_incoming_matched - bank_incoming_unmatched
        bank_outgoing_movements = bank_movements.filtered(
            lambda movement: self._is_bank_outgoing_movement(movement)
        )
        bank_outgoing_matched = bank_outgoing_movements.filtered(
            lambda movement: movement.matched_transfer_id.id in external_outgoing_ids
        )
        bank_outgoing_unmatched = bank_outgoing_movements.filtered(lambda movement: not movement.matched_transfer_id)
        bank_outgoing_not_comparable = bank_outgoing_movements - bank_outgoing_matched - bank_outgoing_unmatched
        wallet_total = len(external_incoming_transfers) + len(external_outgoing_transfers) + len(commission_transfers)
        bank_total = len(bank_incoming_movements) + len(bank_outgoing_movements)
        return [
            self._transaction_count_row(
                _("Entrantes externas"),
                len(external_incoming_transfers),
                len(bank_incoming_movements),
            ),
            self._transaction_count_row(
                _("Salientes externas"),
                len(external_outgoing_transfers),
                len(bank_outgoing_movements),
            ),
            self._transaction_count_row(
                _("Comisiones"),
                len(commission_transfers),
                0,
            ),
            self._transaction_count_row(
                _("Total controlado"),
                wallet_total,
                bank_total,
            ),
            self._transaction_count_row(
                _("Banco creditos sin transferencia vinculada"),
                0,
                len(bank_incoming_unmatched),
            ),
            self._transaction_count_row(
                _("Banco debitos sin transferencia vinculada"),
                0,
                len(bank_outgoing_unmatched),
            ),
            self._transaction_count_row(
                _("Banco creditos no comparables"),
                0,
                len(bank_incoming_not_comparable),
            ),
            self._transaction_count_row(
                _("Banco debitos no comparables"),
                0,
                len(bank_outgoing_not_comparable),
            ),
        ]

    def _temporal_reconciliation_rows(self, period_transfers, bank_accounts, bank_movements):
        visible_account_ids = set(self._visible_bank_accounts(bank_accounts).ids)
        all_account_ids = set(bank_accounts.ids)
        rows_by_key = {}

        def ensure_row(concept_key, concept_label, day):
            key = (concept_key, day)
            if key not in rows_by_key:
                rows_by_key[key] = {
                    "concept_key": concept_key,
                    "concept": concept_label,
                    "date": day,
                    "wallet_count": 0,
                    "wallet_amount": 0.0,
                    "bank_count": 0,
                    "bank_amount": 0.0,
                }
            return rows_by_key[key]

        for transfer in period_transfers:
            day = self._transfer_period_day(transfer)
            if not day:
                continue
            if self._is_external_incoming_transfer(transfer, visible_account_ids, all_account_ids):
                row = ensure_row("incoming", _("Importes entrantes"), day)
            elif self._is_external_outgoing_transfer(transfer, visible_account_ids, all_account_ids):
                row = ensure_row("outgoing", _("Importes salientes"), day)
            else:
                continue
            row["wallet_count"] += 1
            row["wallet_amount"] += transfer.amount or 0.0

        for movement in bank_movements:
            day = movement.movement_date
            if not day:
                continue
            if self._is_bank_incoming_movement(movement):
                row = ensure_row("incoming", _("Importes entrantes"), day)
            elif self._is_bank_outgoing_movement(movement):
                row = ensure_row("outgoing", _("Importes salientes"), day)
            else:
                continue
            row["bank_count"] += 1
            row["bank_amount"] += abs(movement.amount or 0.0)

        concept_order = {"incoming": 0, "outgoing": 1}
        cumulative = {"incoming": 0.0, "outgoing": 0.0}
        rows = []
        for row in sorted(rows_by_key.values(), key=lambda item: (item["date"], concept_order.get(item["concept_key"], 99))):
            row["difference"] = (row["wallet_amount"] or 0.0) - (row["bank_amount"] or 0.0)
            cumulative[row["concept_key"]] += row["difference"]
            row["cumulative_difference"] = cumulative[row["concept_key"]]
            rows.append(row)
        return rows

    def _transfer_period_day(self, transfer):
        if transfer.fecha_negocio:
            return transfer.fecha_negocio
        if transfer.transaction_at:
            return transfer.transaction_at.date()
        return False

    def _transaction_count_row(self, concept, wallet_count, bank_count, partial=False):
        difference = None if bank_count is None else (wallet_count or 0) - (bank_count or 0)
        if bank_count is None:
            status = "nodata"
            status_label = _("Sin datos")
        elif partial:
            status = "partial"
            status_label = _("Parcial")
        elif difference == 0:
            status = "ok"
            status_label = _("OK")
        else:
            status = "diff"
            status_label = _("Diferencia")
        return {
            "concept": concept,
            "wallet_count": wallet_count or 0,
            "bank_count": bank_count,
            "difference": difference,
            "status": status,
            "status_label": status_label,
        }

    def _reconciliation_row(self, concept, wallet_amount, bank_amount, partial=False):
        difference = None if bank_amount is None else (wallet_amount or 0.0) - (bank_amount or 0.0)
        if bank_amount is None:
            status = "nodata"
            status_label = _("Sin datos")
        elif partial:
            status = "partial"
            status_label = _("Parcial")
        elif abs(difference) <= self._reconciliation_tolerance():
            status = "ok"
            status_label = _("OK")
        else:
            status = "diff"
            status_label = _("Diferencia")
        return {
            "concept": concept,
            "wallet_amount": wallet_amount or 0.0,
            "bank_amount": bank_amount,
            "difference": difference,
            "status": status,
            "status_label": status_label,
        }

    def _reconciliation_tolerance(self):
        value = self.env["ir.config_parameter"].sudo().get_param(
            "pagoflex_wallet_gateway.dashboard_reconciliation_tolerance",
            "1.00",
        )
        try:
            return abs(float(value or 1.0))
        except ValueError:
            return 1.0

    def _is_bank_incoming_movement(self, movement):
        return movement.movement_direction == "INCOMING" or movement.debit_credit == "C"

    def _is_bank_outgoing_movement(self, movement):
        return movement.movement_direction == "OUTGOING" or movement.debit_credit == "D"

    def _is_bank_commission_movement(self, movement):
        if (movement.movement_nature or "").strip().upper() == "COMMISSION":
            return True
        text = " ".join(
            value or ""
            for value in (
                movement.concept,
                movement.description,
                movement.display_label,
            )
        ).lower()
        return "comision" in text or "comisión" in text

    def _wallet_rows(self, bank_accounts, active_accounts, period_transfers, app_configs):
        app_keys = {self._app_key(app_name) for app_name in bank_accounts.mapped("app")}
        app_keys.update(self._app_key(app_name) for app_name in app_configs.mapped("app_name"))
        app_keys = sorted(app_key for app_key in app_keys if app_key)
        if self.filter_app:
            app_keys = [app_key for app_key in app_keys if app_key == self.filter_app]
        rows = []
        config_by_app = {self._app_key(config.app_name): config for config in app_configs}
        all_account_ids = set(bank_accounts.ids)

        for index, app_key in enumerate(app_keys):
            config = config_by_app.get(app_key)
            display_app_name = config.app_name if config else app_key
            app_all_accounts = bank_accounts.filtered(lambda account, key=app_key: self._app_key(account.app) == key)
            app_accounts = active_accounts.filtered(lambda account, key=app_key: self._app_key(account.app) == key)
            app_account_ids = set(app_all_accounts.ids)
            incoming_transfers = period_transfers.filtered(
                lambda transfer, account_ids=app_account_ids: self._is_external_incoming_transfer(
                    transfer,
                    account_ids,
                    all_account_ids,
                )
            )
            outgoing_transfers = period_transfers.filtered(
                lambda transfer, account_ids=app_account_ids: self._is_external_outgoing_transfer(
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
            outgoing_volume = sum(outgoing_transfers.mapped("amount"))
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
                    "outgoing_volume": outgoing_volume,
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
        incoming_volume = sum(row["incoming_volume"] for row in wallet_rows)
        outgoing_volume = sum(row["outgoing_volume"] for row in wallet_rows)
        generated_commissions = sum(row["generated_commissions"] for row in wallet_rows)
        return {
            "bank_balance": self._period_bank_movement_amount(),
            "incoming_volume": incoming_volume,
            "outgoing_volume": outgoing_volume,
            "generated_commissions": generated_commissions,
            "net_period_flow": incoming_volume - outgoing_volume - generated_commissions,
            "transfer_count": len(period_transfers),
            "active_accounts": len(active_accounts),
            "active_users": user_model.search_count(active_user_domain),
        }

    def _visible_active_accounts(self, active_accounts):
        if not self.filter_app:
            return active_accounts
        return active_accounts.filtered(lambda account: self._app_key(account.app) == self.filter_app)

    def _filtered_transfer_records(self, period_transfers, bank_accounts, app_configs):
        visible_accounts = self._visible_bank_accounts(bank_accounts)
        visible_account_ids = set(visible_accounts.ids)
        all_account_ids = set(bank_accounts.ids)
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
            or transfer.source_address in self._account_cvus_from_ids(visible_account_ids)
            or transfer.destination_address in self._account_cvus_from_ids(visible_account_ids)
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
        if not transfer._is_external_incoming_transfer_record():
            return False
        if transfer.destination_bank_account_id.id in app_account_ids:
            return True
        app_account_cvus = self._account_cvus_from_ids(app_account_ids)
        return bool(transfer.destination_address and transfer.destination_address in app_account_cvus)

    def _is_external_outgoing_transfer(self, transfer, app_account_ids, all_account_ids):
        if not transfer._is_external_outgoing_transfer_record():
            return False
        if transfer.source_bank_account_id.id in app_account_ids:
            return True
        app_account_cvus = self._account_cvus_from_ids(app_account_ids)
        return bool(transfer.source_address and transfer.source_address in app_account_cvus)

    def _visible_bank_accounts(self, bank_accounts):
        if not self.filter_app:
            return bank_accounts
        return bank_accounts.filtered(lambda account: self._app_key(account.app) == self.filter_app)

    def _account_cvus_from_ids(self, account_ids):
        if not account_ids:
            return set()
        return set(
            self.env["pf.gateway.bank.account"]
            .sudo()
            .browse(list(account_ids))
            .mapped("cvu_cbu")
        )

    def _is_commission_transfer_for_account(self, transfer, commission_account):
        if not commission_account:
            return False
        if transfer.movement_nature != "COMMISSION":
            return False
        if (transfer.status or "").upper() == "FAILED":
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
        incomplete_transfer_domain = self._incomplete_internal_transfer_domain()
        return [
            {
                "label": _("Apps sin cuenta de comisiones configurada"),
                "count": len(missing_commission_apps),
                "priority": _("Alta"),
            },
            {
                "label": _("Transferencias con vinculacion incompleta"),
                "count": self.env["pf.gateway.transfer"].search_count(incomplete_transfer_domain),
                "priority": _("Media"),
            },
            # {
            #     "label": _("Cuentas activas sin saldo actualizado"),
            #     "count": self.env["pf.gateway.bank.account"].search_count(
            #         [("status", "=", "active"), ("balance_sync_status", "in", ["never", "error", "no_balance", "not_found"])]
            #     ),
            #     "priority": _("Media"),
            # },
            {
                "label": _("Usuarios sin verificacion KYC"),
                "count": self.env["pf.gateway.user"].search_count([("active", "=", True), ("is_kyc_verified", "=", False)]),
                "priority": _("Baja"),
            },
        ]

    def _incomplete_internal_transfer_domain(self):
        return [
            ("active", "=", True),
            ("status", "!=", "FAILED"),
            ("is_external_incoming_transfer", "=", False),
            ("is_external_outgoing_transfer", "=", False),
            "|",
            ("source_bank_account_id", "=", False),
            ("destination_bank_account_id", "=", False),
        ]

    def _build_global_summary_html(self, totals):
        net_flow_color = "green" if totals["net_period_flow"] >= 0 else "red"
        cards = [
            ("bank", _("Saldo total en banco"), self._format_money(totals["bank_balance"]), _("Movimientos persistidos del periodo"), "blue"),
            ("arrow-circle-down", _("Volumen entrante del periodo"), self._format_money(totals["incoming_volume"]), _("Solo ingresos externos"), "green"),
            ("arrow-circle-up", _("Volumen saliente del periodo"), self._format_money(totals["outgoing_volume"]), _("Solo egresos externos"), "blue"),
            ("money", _("Comisiones generadas"), self._format_money(totals["generated_commissions"]), _("Acumulado del periodo"), "purple"),
            ("line-chart", _("Flujo neto del periodo"), self._format_money(totals["net_period_flow"]), _("Entrantes - salientes - comisiones"), net_flow_color),
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
            "%s%s%s%s%s%s%s%s"
            "</div>"
            "</article>"
        ) % (
            escape(row["color"]),
            escape(row["display_name"]),
            self._compact_metric_html(_("Saldo en banco"), _("No disponible"), _("Pendiente de nueva fuente")),
            self._compact_metric_html(_("Volumen entrante"), self._format_money(row["incoming_volume"]), _("Solo ingresos externos")),
            self._compact_metric_html(_("Volumen saliente"), self._format_money(row["outgoing_volume"]), _("Solo egresos externos")),
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

    def _build_reconciliation_summary_html(self, rows):
        tolerance = self._format_money(self._reconciliation_tolerance())
        body = "".join(self._reconciliation_table_row_html(row) for row in rows)
        return (
            "<section class='pf_dashboard_panel pf_dashboard_reconciliation'>"
            "<div class='pf_dashboard_panel_header'><h2>%s</h2><span>%s</span></div>"
            "<div class='pf_dashboard_reconciliation_table'>"
            "<div class='pf_dashboard_reconciliation_head'>"
            "<span>%s</span><span>%s</span><span>%s</span><span>%s</span><span>%s</span>"
            "</div>%s</div></section>"
        ) % (
            escape(_("Conciliacion operativa del periodo")),
            escape(_("Tolerancia %s") % tolerance),
            escape(_("Concepto")),
            escape(_("Billetera")),
            escape(_("Banco")),
            escape(_("Diferencia")),
            escape(_("Estado")),
            body,
        )

    def _reconciliation_table_row_html(self, row):
        bank_value = self._format_money(row["bank_amount"]) if row["bank_amount"] is not None else _("Sin datos")
        difference = self._format_money(row["difference"]) if row["difference"] is not None else "-"
        return (
            "<div class='pf_dashboard_reconciliation_row pf_dashboard_reconciliation_%s'>"
            "<span>%s</span><strong>%s</strong><strong>%s</strong><strong>%s</strong><em>%s</em>"
            "</div>"
        ) % (
            escape(row["status"]),
            escape(row["concept"]),
            escape(self._format_money(row["wallet_amount"])),
            escape(bank_value),
            escape(difference),
            escape(row["status_label"]),
        )

    def _build_temporal_reconciliation_html(self, rows):
        body = "".join(self._temporal_reconciliation_row_html(row) for row in rows)
        if not body:
            body = (
                "<div class='pf_dashboard_temporal_empty'>%s</div>"
                % escape(_("Sin movimientos para el periodo seleccionado."))
            )
        return (
            "<section class='pf_dashboard_panel pf_dashboard_temporal'>"
            "<div class='pf_dashboard_panel_header'><h2>%s</h2><span>%s</span></div>"
            "<div class='pf_dashboard_temporal_table'>"
            "<div class='pf_dashboard_temporal_head'>"
            "<span>%s</span><span>%s</span><span>%s</span><span>%s</span>"
            "<span>%s</span><span>%s</span><span>%s</span><span>%s</span>"
            "</div>%s</div></section>"
        ) % (
            escape(_("Evolucion temporal de importes")),
            escape(_("Entrantes y salientes por fecha")),
            escape(_("Fecha")),
            escape(_("Concepto")),
            escape(_("Cant. billetera")),
            escape(_("Importe billetera")),
            escape(_("Cant. banco")),
            escape(_("Importe banco")),
            escape(_("Dif. dia")),
            escape(_("Dif. acumulada")),
            body,
        )

    def _temporal_reconciliation_row_html(self, row):
        day = fields.Date.to_string(row["date"]) if row["date"] else "-"
        return (
            "<div class='pf_dashboard_temporal_row'>"
            "<span>%s</span><span>%s</span><strong>%s</strong><strong>%s</strong>"
            "<strong>%s</strong><strong>%s</strong><strong>%s</strong><strong>%s</strong>"
            "</div>"
        ) % (
            escape(day),
            escape(row["concept"]),
            escape(self._format_int(row["wallet_count"])),
            escape(self._format_money(row["wallet_amount"])),
            escape(self._format_int(row["bank_count"])),
            escape(self._format_money(row["bank_amount"])),
            escape(self._format_money(row["difference"])),
            escape(self._format_money(row["cumulative_difference"])),
        )

    def _build_transaction_count_summary_html(self, rows):
        body = "".join(self._transaction_count_table_row_html(row) for row in rows)
        return (
            "<section class='pf_dashboard_panel pf_dashboard_reconciliation pf_dashboard_transaction_count'>"
            "<div class='pf_dashboard_panel_header'><h2>%s</h2><span>%s</span></div>"
            "<div class='pf_dashboard_reconciliation_table'>"
            "<div class='pf_dashboard_reconciliation_head'>"
            "<span>%s</span><span>%s</span><span>%s</span><span>%s</span><span>%s</span>"
            "</div>%s</div></section>"
        ) % (
            escape(_("Conteo operativo del periodo")),
            escape(_("Control de sincronizacion")),
            escape(_("Concepto")),
            escape(_("Billetera")),
            escape(_("Banco")),
            escape(_("Diferencia")),
            escape(_("Estado")),
            body,
        )

    def _transaction_count_table_row_html(self, row):
        bank_value = self._format_int(row["bank_count"]) if row["bank_count"] is not None else _("Sin datos")
        difference = self._format_int(row["difference"]) if row["difference"] is not None else "-"
        return (
            "<div class='pf_dashboard_reconciliation_row pf_dashboard_reconciliation_%s'>"
            "<span>%s</span><strong>%s</strong><strong>%s</strong><strong>%s</strong><em>%s</em>"
            "</div>"
        ) % (
            escape(row["status"]),
            escape(row["concept"]),
            escape(self._format_int(row["wallet_count"])),
            escape(bank_value),
            escape(difference),
            escape(row["status_label"]),
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

    def _build_top_users_summary_html(self, period_transfers, bank_accounts):
        visible_account_ids = set(self._visible_bank_accounts(bank_accounts).ids)
        all_account_ids = set(bank_accounts.ids)
        incoming_transfers = period_transfers.filtered(
            lambda t: self._is_external_incoming_transfer(t, visible_account_ids, all_account_ids)
        )

        counts_fisica = {}
        amounts_fisica = {}
        counts_empresa = {}
        amounts_empresa = {}

        for t in incoming_transfers:
            user = t.destination_user_id
            if not user:
                continue

            dni_digits = "".join(filter(str.isdigit, str(user.dni or "")))
            cuit_digits = "".join(filter(str.isdigit, str(user.cuit_cuil or user.dni or "")))

            if len(cuit_digits) == 11:
                counts_empresa[user] = counts_empresa.get(user, 0) + 1
                amounts_empresa[user] = amounts_empresa.get(user, 0.0) + (t.amount or 0.0)
            elif len(dni_digits) <= 8 and dni_digits:
                counts_fisica[user] = counts_fisica.get(user, 0) + 1
                amounts_fisica[user] = amounts_fisica.get(user, 0.0) + (t.amount or 0.0)

        top_fisica_list = sorted(counts_fisica.items(), key=lambda x: amounts_fisica[x[0]], reverse=True)[:10]
        top_empresa_list = sorted(counts_empresa.items(), key=lambda x: amounts_empresa[x[0]], reverse=True)[:10]

        def _render_ranking(title, items, amounts_dict, color, icon):
            if not items:
                return (
                    "<div class='pf_dashboard_wallet_card pf_dashboard_wallet_%s'>"
                    "<div class='pf_dashboard_wallet_title'><i class='fa fa-%s'></i><h3>%s</h3></div>"
                    "<div class='pf_dashboard_empty text-center p-3'>%s</div>"
                    "</div>"
                ) % (color, icon, escape(title), escape(_("Sin datos en este período")))
            
            max_amount = max(amounts_dict[user] for user, _ in items) if items else 1
            if max_amount <= 0:
                max_amount = 1
                
            rows_html = ""
            for user, count in items:
                amount = amounts_dict[user]
                label = f"{user.name} ({count} txs)"
                rows_html += self._bar_row_html(label, amount, max_amount, color)
                
            return (
                "<div class='pf_dashboard_wallet_card pf_dashboard_wallet_%s'>"
                "<div class='pf_dashboard_wallet_title'><i class='fa fa-%s'></i><h3>%s</h3></div>"
                "<div style='padding-bottom: 10px;'>%s</div>"
                "</div>"
            ) % (color, icon, escape(title), rows_html)

        html_fisica = _render_ranking(_("Personas Físicas Top 10"), top_fisica_list, amounts_fisica, "green", "user")
        html_empresa = _render_ranking(_("Empresas Top 10"), top_empresa_list, amounts_empresa, "blue", "building")

        return (
            "<article class='pf_dashboard_panel pf_dashboard_top_users'>"
            "<div class='pf_dashboard_panel_header'><h2>%s</h2><span>%s</span></div>"
            "<div class='pf_dashboard_wallet_grid' style='padding: 16px; margin-bottom: 0;'>%s%s</div>"
            "</article>"
        ) % (
            escape(_("Usuarios destacados")),
            escape(_("Top 10 de usuarios con mayor volumen de transferencias entrantes externas")),
            html_fisica,
            html_empresa,
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
        ) % (escape(icon), value, escape(label), helper)

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
        today = fields.Date.context_today(self)
        return self._open_action(
            "pagoflex_wallet_gateway.action_pf_gateway_transfer",
            domain=expression.AND(
                [
                    [("active", "=", True), ("movement_nature", "=", "TRANSFER")],
                    self._transfer_business_period_domain(today, today),
                ]
            ),
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

    def action_open_balance_sync_exceptions(self):
        self.ensure_one()
        return self._open_action(
            "pagoflex_wallet_gateway.action_pf_gateway_bank_account",
            domain=[("status", "=", "active"), ("balance_sync_status", "in", ["never", "error", "no_balance", "not_found"])],
        )

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
            domain=self._incomplete_internal_transfer_domain(),
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
