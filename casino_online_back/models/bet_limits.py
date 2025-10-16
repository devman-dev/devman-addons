# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_round

from psycopg2 import IntegrityError

class BetLimits(models.Model):
    _name = "casino.game.bet.limits"
    _description = "Bet Limits by Partner"
    _rec_name = "partner_id"
    _order = "id desc"
    _check_company_auto = True

    partner_id = fields.Many2one("res.partner", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
    currency_id = fields.Many2one(related="company_id.currency_id", store=True, readonly=True)

    # Límites (0 => sin límite)
    limit_daily = fields.Monetary(string="Límite diario", currency_field="currency_id", default=0.0)
    limit_weekly = fields.Monetary(string="Límite semanal", currency_field="currency_id", default=0.0)
    limit_monthly = fields.Monetary(string="Límite mensual", currency_field="currency_id", default=0.0)

    # Acumulados
    spent_daily = fields.Monetary(string="Acumulado diario", currency_field="currency_id", default=0.0, readonly=True)
    spent_weekly = fields.Monetary(string="Acumulado semanal", currency_field="currency_id", default=0.0, readonly=True)
    spent_monthly = fields.Monetary(string="Acumulado mensual", currency_field="currency_id", default=0.0, readonly=True)

    # Mensajes
    msg_daily   = fields.Char(string="Mensaje diario (empresa)",   related="company_id.bet_msg_daily",   readonly=True)
    msg_weekly  = fields.Char(string="Mensaje semanal (empresa)",  related="company_id.bet_msg_weekly",  readonly=True)
    msg_monthly = fields.Char(string="Mensaje mensual (empresa)",  related="company_id.bet_msg_monthly", readonly=True)

    # Ventanas rodantes
    last_reset_daily = fields.Datetime(string="Último reset diario")
    last_reset_weekly = fields.Datetime(string="Último reset semanal")
    last_reset_monthly = fields.Datetime(string="Último reset mensual")

    _sql_constraints = [
        ("partner_company_unique", "unique(partner_id, company_id)", "Ya existe un registro de límites para este partner y compañía."),
        ("non_negative_limits", "CHECK (limit_daily >= 0 AND limit_weekly >= 0 AND limit_monthly >= 0)", "Los límites no pueden ser negativos."),
        ("non_negative_spent", "CHECK (spent_daily >= 0 AND spent_weekly >= 0 AND spent_monthly >= 0)", "Los acumulados no pueden ser negativos."),
    ]

    # -------- Helpers config --------
    @api.model
    def _get_param(self, key, default=None):
        return self.env["ir.config_parameter"].sudo().get_param(f"bet_limits.{key}", default)

    @api.model
    def _get_window_mode(self):
        # "calendar" | "rolling"
        return self._get_param("window_mode", "calendar")

    @api.model
    def _default_msg(self, period):
        return self._get_param(f"message_{period}", "")

    @api.model
    def create_for_partner(self, partner):
        """Crea el registro para el partner si no existe, usando defaults globales."""
        self = self.sudo()
        record = self.search([("partner_id", "=", partner.id), ("company_id", "=", partner.company_id.id)], limit=1)
        if record:
            return record
        vals = {
            "partner_id": partner.id,
            "company_id": partner.company_id.id or self.env.company.id,
            "limit_daily": float(self._get_param("default_limit_daily", "0") or 0.0),
            "limit_weekly": float(self._get_param("default_limit_weekly", "0") or 0.0),
            "limit_monthly": float(self._get_param("default_limit_monthly", "0") or 0.0),
            "msg_daily": self._default_msg("daily"),
            "msg_weekly": self._default_msg("weekly"),
            "msg_monthly": self._default_msg("monthly"),
        }
        return self.create(vals)

    # -------- Ventanas rodantes --------
    def _maybe_roll_windows(self):
        if self._get_window_mode() != "rolling":
            return
        now = fields.Datetime.now()
        for rec in self.sudo():
            vals = {}
            if not rec.last_reset_daily or fields.Datetime.subtract(now, days=1) >= rec.last_reset_daily:
                vals.update(spent_daily=0.0, last_reset_daily=now)
            if not rec.last_reset_weekly or fields.Datetime.subtract(now, days=7) >= rec.last_reset_weekly:
                vals.update(spent_weekly=0.0, last_reset_weekly=now)
            if not rec.last_reset_monthly or fields.Datetime.subtract(now, days=30) >= rec.last_reset_monthly:
                vals.update(spent_monthly=0.0, last_reset_monthly=now)
            if vals:
                rec.write(vals)

    # -------- API: check --------
    def check_game_casino_bet_limits(self, amount):
        """Calcula remanentes y si está permitido (sin escribir)."""
        self.ensure_one()
        self._maybe_roll_windows()
        cur = self.currency_id
        prec = (cur.decimal_places if cur else 2)
        ld = self.limit_daily or float(self._get_param("default_limit_daily", "0") or 0.0)
        lw = self.limit_weekly or float(self._get_param("default_limit_weekly", "0") or 0.0)
        lm = self.limit_monthly or float(self._get_param("default_limit_monthly", "0") or 0.0)

        rd = max(0.0, float_round(ld - (self.spent_daily or 0.0), precision_digits=prec))
        rw = max(0.0, float_round(lw - (self.spent_weekly or 0.0), precision_digits=prec))
        rm = max(0.0, float_round(lm - (self.spent_monthly or 0.0), precision_digits=prec))

        def ok(limit, remaining):  # 0 => sin límite
            return True if (limit or 0.0) == 0.0 else amount <= remaining

        allowed = ok(ld, rd) and ok(lw, rw) and ok(lm, rm)

        blocking = None
        message = None
        if not allowed:
            if not ok(ld, rd):
                blocking = "daily"; message = self.company_id.bet_msg_daily or self._default_msg("daily")
            elif not ok(lw, rw):
                blocking = "weekly"; message = self.company_id.bet_msg_weekly or self._default_msg("weekly")
            else:
                blocking = "monthly"; message = self.company_id.bet_msg_monthly or self._default_msg("monthly")

        return {
            "allowed": allowed,
            "blocking_period": blocking,
            "remaining": {"daily": rd, "weekly": rw, "monthly": rm},
            "message": message,
        }

    # -------- API: register (CONCURRENCIA ALTA, operación atómica) --------
    def register_bet(self, amount):
        """
        Valida e imputa la apuesta con una actualización atómica:
        - Resetea ventanas si aplica (rolling)
        - Intenta UPDATE ... WHERE (condiciones que respetan los límites)
        - Si no actualiza filas => se excede algún límite; informa cuál.
        """
        self.ensure_one()
        self._maybe_roll_windows()

        self.env.cr.execute("""
            UPDATE casino_game_bet_limits bl
               SET spent_daily   = spent_daily   + %(amt)s,
                   spent_weekly  = spent_weekly  + %(amt)s,
                   spent_monthly = spent_monthly + %(amt)s,
                   last_reset_daily   = COALESCE(last_reset_daily,   NOW()),
                   last_reset_weekly  = COALESCE(last_reset_weekly,  NOW()),
                   last_reset_monthly = COALESCE(last_reset_monthly, NOW())
             WHERE bl.id = %(id)s
               AND (
                    (COALESCE(bl.limit_daily, 0)  = 0) OR (bl.spent_daily   + %(amt)s <= bl.limit_daily)
                   )
               AND (
                    (COALESCE(bl.limit_weekly, 0) = 0) OR (bl.spent_weekly  + %(amt)s <= bl.limit_weekly)
                   )
               AND (
                    (COALESCE(bl.limit_monthly,0) = 0) OR (bl.spent_monthly + %(amt)s <= bl.limit_monthly)
                   )
         RETURNING bl.id
        """, {"id": self.id, "amt": float(amount)})
        updated = self.env.cr.rowcount

        if updated:
            return {"allowed": True}

        # No se pudo actualizar: identificar el período bloqueante (lectura una sola vez)
        self.env.cr.execute("""
            SELECT spent_daily, spent_weekly, spent_monthly, limit_daily, limit_weekly, limit_monthly
              FROM casino_game_bet_limits WHERE id = %s
        """, (self.id,))
        row = self.env.cr.fetchone()
        if not row:
            raise ValidationError(_("Registro de límites no encontrado."))

        sd, sw, sm, ld, lw, lm = row
        def remaining(limit, spent): return float("inf") if (limit or 0.0) == 0.0 else (limit - spent)
        rem = {"daily": remaining(ld, sd), "weekly": remaining(lw, sw), "monthly": remaining(lm, sm)}

        # Elige el primero que bloquee
        blocking = next((p for p in ("daily", "weekly", "monthly") if rem[p] < amount), None)
        msg_map = {
            "daily":   self.company_id.bet_msg_daily   or _("Has alcanzado tu límite diario."),
            "weekly":  self.company_id.bet_msg_weekly  or _("Has alcanzado tu límite semanal."),
            "monthly": self.company_id.bet_msg_monthly or _("Has alcanzado tu límite mensual."),
        }
        raise ValidationError(msg_map.get(blocking) or _("Has alcanzado tu límite de apuestas."))

    @api.model
    def _cron_reset(self, period):
        """Resetea acumulados según período. Se llama desde ir.cron.
        No depende de parámetros globales."""
        now = fields.Datetime.now()
        vals_map = {
            "daily":   {"spent_daily": 0.0,  "last_reset_daily": now},
            "weekly":  {"spent_weekly": 0.0, "last_reset_weekly": now},
            "monthly": {"spent_monthly": 0.0,"last_reset_monthly": now},
        }
        vals = vals_map.get(period, {})
        if not vals:
            return
        # procesar en lotes por si hay muchos registros
        Model = self.sudo()
        count = Model.search_count([])
        offset = 0
        while offset < count:
            recs = Model.search([], offset=offset, limit=5000)
            if recs:
                recs.write(vals)
            offset += 5000

    @api.model
    def get_or_create_for_partner(self, partner, company=None):
        """Devuelve el bet.limits (partner, company). Si no existe, lo crea con ceros.
        Maneja concurrencia usando unique(partner_id, company_id)."""
        self = self.sudo()
        company = company or partner.company_id or self.env.company

        rec = self.search([
            ('partner_id', '=', partner.id),
            ('company_id', '=', company.id),
        ], limit=1)
        if rec:
            return rec

        # crear con ceros; si otra transacción lo crea al mismo tiempo, capturamos la unique
        try:
            with self.env.cr.savepoint():
                return self.create({
                    'partner_id': partner.id,
                    'company_id': company.id,
                    'limit_daily': 0.0,
                    'limit_weekly': 0.0,
                    'limit_monthly': 0.0,
                    # mensajes opcionales vacíos
                    'msg_daily': '',
                    'msg_weekly': '',
                    'msg_monthly': '',
                    # marcas de reset se completarán en la primera escritura si querés
                })
        except IntegrityError:
            # ya lo creó otro worker casi al mismo tiempo -> lo buscamos y devolvemos
            self.env.cr.rollback()
            return self.search([
                ('partner_id', '=', partner.id),
                ('company_id', '=', company.id),
            ], limit=1)
        