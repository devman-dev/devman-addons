from datetime import datetime, time, timedelta

import pytz

from odoo import _, api, fields, models
from odoo.osv import expression

class PfReconciliationControl(models.Model):
    _name = "pf.reconciliation.control"
    _description = "Control Diario de Conciliación"
    _order = "date desc, time_window desc"
    _RECONCILIATION_TZ_PARAM = "pagoflex_wallet_gateway.reconciliation_timezone"
    _DEFAULT_RECONCILIATION_TZ = "America/Argentina/Buenos_Aires"

    date = fields.Date(string="Fecha", required=True, index=True)
    time_window = fields.Selection(
        [
            ("00_12", "Mañana (00:00 - 11:59)"),
            ("12_21", "Tarde (12:00 - 20:59)"),
            ("21_24", "Noche (21:00 - 23:59)"),
        ],
        string="Franja Horaria",
        required=True,
        index=True,
    )
    datetime_start = fields.Datetime(string="Inicio Franja", required=True)
    datetime_end = fields.Datetime(string="Fin Franja", required=True)

    # Métricas Entrantes
    wallet_in_count = fields.Integer(string="Billetera Entrantes (Cant.)", default=0)
    wallet_in_amount = fields.Float(string="Billetera Entrantes ($)", digits=(16, 2), default=0.0)
    bank_in_count = fields.Integer(string="Banco Entrantes (Cant.)", default=0)
    bank_in_amount = fields.Float(string="Banco Entrantes ($)", digits=(16, 2), default=0.0)
    
    diff_in_count = fields.Integer(string="Dif. Entrantes (Cant.)", compute="_compute_differences", store=True)
    diff_in_amount = fields.Float(string="Dif. Entrantes ($)", digits=(16, 2), compute="_compute_differences", store=True)

    # Métricas Salientes
    wallet_out_count = fields.Integer(string="Billetera Salientes (Cant.)", default=0)
    wallet_out_amount = fields.Float(string="Billetera Salientes ($)", digits=(16, 2), default=0.0)
    bank_out_count = fields.Integer(string="Banco Salientes (Cant.)", default=0)
    bank_out_amount = fields.Float(string="Banco Salientes ($)", digits=(16, 2), default=0.0)
    
    diff_out_count = fields.Integer(string="Dif. Salientes (Cant.)", compute="_compute_differences", store=True)
    diff_out_amount = fields.Float(string="Dif. Salientes ($)", digits=(16, 2), compute="_compute_differences", store=True)

    _sql_constraints = [
        ("pf_reconciliation_control_date_window_uniq", "unique(date, time_window)", "La franja horaria para esa fecha ya existe."),
    ]

    @api.depends("wallet_in_count", "bank_in_count", "wallet_in_amount", "bank_in_amount",
                 "wallet_out_count", "bank_out_count", "wallet_out_amount", "bank_out_amount")
    def _compute_differences(self):
        for record in self:
            record.diff_in_count = record.wallet_in_count - record.bank_in_count
            record.diff_in_amount = record.wallet_in_amount - record.bank_in_amount
            record.diff_out_count = record.wallet_out_count - record.bank_out_count
            record.diff_out_amount = record.wallet_out_amount - record.bank_out_amount

    def name_get(self):
        result = []
        for record in self:
            window_label = dict(self._fields['time_window'].selection).get(record.time_window)
            name = f"{record.date} - {window_label}"
            result.append((record.id, name))
        return result

    @api.model
    def cron_generate_reconciliation_windows(self, lookback_days=10):
        """
        Calcula y actualiza los registros de control de conciliación de los últimos N días.
        Se ejecuta por cron, idealmente 2 o 3 veces al día.
        """
        today = fields.Date.context_today(self)
        start_date = today - timedelta(days=lookback_days)
        
        current_date = start_date
        while current_date <= today:
            self._process_day_windows(current_date)
            current_date += timedelta(days=1)

    def _process_day_windows(self, target_date):
        windows = [
            ("00_12", time(0, 0, 0), time(11, 59, 59)),
            ("12_21", time(12, 0, 0), time(20, 59, 59)),
            ("21_24", time(21, 0, 0), time(23, 59, 59, 999999)),
        ]
        
        for window_code, time_start, time_end in windows:
            dt_start = datetime.combine(target_date, time_start)
            dt_end = datetime.combine(target_date, time_end)
            
            # Buscar o crear registro
            record = self.search([("date", "=", target_date), ("time_window", "=", window_code)], limit=1)
            if not record:
                record = self.create({
                    "date": target_date,
                    "time_window": window_code,
                    "datetime_start": dt_start,
                    "datetime_end": dt_end,
                })
            
            # Recalcular métricas
            self._recalculate_metrics(record, dt_start, dt_end)

    def _local_tz(self):
        tz_name = (
            self.env.context.get("tz")
            or self.env["ir.config_parameter"].sudo().get_param(self._RECONCILIATION_TZ_PARAM)
            or self.env.user.tz
            or self._DEFAULT_RECONCILIATION_TZ
        )
        try:
            return pytz.timezone(tz_name)
        except pytz.UnknownTimeZoneError:
            return pytz.timezone(self._DEFAULT_RECONCILIATION_TZ)

    def _datetime_to_local_time(self, value):
        if not value:
            return False
        dt_value = fields.Datetime.to_datetime(value)
        if not dt_value:
            return False
        utc_value = pytz.UTC.localize(dt_value) if dt_value.tzinfo is None else dt_value.astimezone(pytz.UTC)
        return utc_value.astimezone(self._local_tz()).time()

    def _local_datetime_to_utc(self, value):
        if not value:
            return False
        dt_value = fields.Datetime.to_datetime(value)
        if not dt_value:
            return False
        local_tz = self._local_tz()
        local_value = local_tz.localize(dt_value) if dt_value.tzinfo is None else dt_value.astimezone(local_tz)
        return local_value.astimezone(pytz.UTC).replace(tzinfo=None)

    def _time_in_window(self, value, time_start, time_end):
        if not value:
            return False
        return time_start <= value <= time_end

    def _recalculate_metrics(self, record, dt_start, dt_end):
        transfer_model = self.env["pf.gateway.transfer"].sudo()
        movement_model = self.env["pf.gateway.bank.movement"].sudo()
        time_start = dt_start.time()
        time_end = dt_end.time()
        utc_start = self._local_datetime_to_utc(dt_start)
        utc_end = self._local_datetime_to_utc(dt_end)

        # 1. Billetera (Transfers)
        wallet_domain_base = [
            ("active", "=", True),
            ("status", "!=", "FAILED"),
            ("transaction_at", ">=", utc_start),
            ("transaction_at", "<=", utc_end),
        ]

        # Incomings Billetera
        in_transfers = transfer_model.search(expression.AND([
            wallet_domain_base,
            [("is_external_incoming_transfer", "=", True)]
        ])).filtered(lambda transfer: self._time_in_window(
            self._datetime_to_local_time(transfer.transaction_at),
            time_start,
            time_end,
        ))
        record.wallet_in_count = len(in_transfers)
        record.wallet_in_amount = sum(in_transfers.mapped("amount"))

        # Outgoings Billetera
        out_transfers = transfer_model.search(expression.AND([
            wallet_domain_base,
            [("is_external_outgoing_transfer", "=", True)]
        ])).filtered(lambda transfer: self._time_in_window(
            self._datetime_to_local_time(transfer.transaction_at),
            time_start,
            time_end,
        ))
        record.wallet_out_count = len(out_transfers)
        record.wallet_out_amount = sum(out_transfers.mapped("amount"))

        # 2. Banco (Movements)
        bank_domain_base = [
            ("active", "=", True),
            ("movement_datetime", ">=", utc_start),
            ("movement_datetime", "<=", utc_end),
            "!", ("movement_nature", "ilike", "COMMISSION"),
            "!", ("concept", "ilike", "comision"),
            "!", ("description", "ilike", "comision"),
            "!", ("display_label", "ilike", "comision"),
        ]

        # Incomings Banco
        in_movements = movement_model.search(expression.AND([
            bank_domain_base,
            ["|", ("movement_direction", "=", "INCOMING"), ("debit_credit", "=", "C")]
        ])).filtered(lambda movement: self._time_in_window(
            self._datetime_to_local_time(movement.movement_datetime),
            time_start,
            time_end,
        ))
        record.bank_in_count = len(in_movements)
        record.bank_in_amount = sum(abs(m.amount) for m in in_movements)

        # Outgoings Banco
        out_movements = movement_model.search(expression.AND([
            bank_domain_base,
            ["|", ("movement_direction", "=", "OUTGOING"), ("debit_credit", "=", "D")]
        ])).filtered(lambda movement: self._time_in_window(
            self._datetime_to_local_time(movement.movement_datetime),
            time_start,
            time_end,
        ))
        record.bank_out_count = len(out_movements)
        record.bank_out_amount = sum(abs(m.amount) for m in out_movements)
