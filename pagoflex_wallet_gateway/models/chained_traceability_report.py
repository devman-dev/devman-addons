import hashlib
import json
import re
import secrets
from datetime import datetime, time, timedelta
from io import BytesIO

import pytz
import xlsxwriter

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


REPORT_GROUPS = (
    "pagoflex_wallet_gateway.group_pagoflex_wallet_gateway_auditor",
    "pagoflex_wallet_gateway.group_pagoflex_wallet_gateway_admin",
)


def _has_report_group(user):
    return any(user.has_group(group) for group in REPORT_GROUPS)


class PfGatewayTraceabilityReportAudit(models.Model):
    _name = "pf.gateway.traceability.report.audit"
    _description = "Auditoría de reporte de trazabilidad por CUIT"
    _order = "requested_at desc, id desc"
    _rec_name = "uuid"

    uuid = fields.Char(required=True, readonly=True, index=True)
    requested_by_id = fields.Many2one("res.users", required=True, readonly=True, index=True)
    company_id = fields.Many2one("res.company", required=True, readonly=True, index=True)
    requested_at = fields.Datetime(required=True, readonly=True, index=True)
    cuit_json = fields.Text(required=True, readonly=True)
    all_cuits = fields.Boolean(required=True, readonly=True)
    date_from = fields.Date(required=True, readonly=True)
    date_to = fields.Date(required=True, readonly=True)
    timezone = fields.Char(required=True, readonly=True)
    operation_scope = fields.Selection(
        [("internal", "Internas"), ("external", "Externas"), ("both", "Ambas")],
        required=True,
        readonly=True,
    )
    max_depth = fields.Integer(required=True, readonly=True)
    export_format = fields.Selection([("xlsx", "XLSX")], required=True, readonly=True)
    schema_version = fields.Char(required=True, readonly=True, default="1.0")
    parameter_hash = fields.Char(required=True, readonly=True, index=True)
    download_token_hash = fields.Char(required=True, readonly=True, index=True)
    token_expires_at = fields.Datetime(required=True, readonly=True, index=True)
    event_ids = fields.One2many(
        "pf.gateway.traceability.report.audit.event", "audit_id", string="Eventos", readonly=True
    )

    _sql_constraints = [
        ("pf_gateway_traceability_audit_uuid_uniq", "unique(uuid)", "El UUID de auditoría debe ser único."),
    ]

    def write(self, vals):
        raise AccessError(_("Los registros de auditoría son inmutables."))

    def unlink(self):
        raise AccessError(_("Los registros de auditoría son inmutables."))

    @api.model
    def create_request(self, values):
        date_from = fields.Date.to_date(values["date_from"])
        date_to = fields.Date.to_date(values["date_to"])
        token = secrets.token_urlsafe(32)
        audit_uuid = secrets.token_hex(16)
        canonical = {
            "all_cuits": values["all_cuits"],
            "cuits": values["cuits"],
            "date_from": fields.Date.to_string(date_from),
            "date_to": fields.Date.to_string(date_to),
            "timezone": values["timezone"],
            "operation_scope": values["operation_scope"],
            "max_depth": values["max_depth"],
            "export_format": "xlsx",
            "schema_version": "1.0",
        }
        canonical_json = json.dumps(canonical, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        audit = self.create(
            {
                "uuid": audit_uuid,
                "requested_by_id": self.env.user.id,
                "company_id": self.env.company.id,
                "requested_at": fields.Datetime.now(),
                "cuit_json": json.dumps(values["cuits"], ensure_ascii=True),
                "all_cuits": values["all_cuits"],
                "date_from": date_from,
                "date_to": date_to,
                "timezone": values["timezone"],
                "operation_scope": values["operation_scope"],
                "max_depth": values["max_depth"],
                "export_format": "xlsx",
                "schema_version": "1.0",
                "parameter_hash": hashlib.sha256(canonical_json.encode()).hexdigest(),
                "download_token_hash": hashlib.sha256(token.encode()).hexdigest(),
                "token_expires_at": fields.Datetime.now() + timedelta(minutes=10),
            }
        )
        audit.add_event("requested")
        return audit, token

    def add_event(self, event_type, **values):
        self.ensure_one()
        payload = {
            "audit_id": self.id,
            "event_type": event_type,
            "event_at": fields.Datetime.now(),
            "user_id": self.env.user.id,
        }
        payload.update(values)
        return self.env["pf.gateway.traceability.report.audit.event"].sudo().create(payload)

    def check_download_access(self, token):
        self.ensure_one()
        if not _has_report_group(self.env.user):
            raise AccessError(_("No tiene permisos para descargar este reporte."))
        if self.requested_by_id != self.env.user and not self.env.user.has_group(
            "pagoflex_wallet_gateway.group_pagoflex_wallet_gateway_admin"
        ):
            raise AccessError(_("El reporte pertenece a otro usuario."))
        if not token or not secrets.compare_digest(
            self.download_token_hash, hashlib.sha256(token.encode()).hexdigest()
        ):
            raise AccessError(_("El enlace de descarga no es válido."))
        if self.token_expires_at < fields.Datetime.now():
            raise AccessError(_("El enlace de descarga venció."))
        already_used = self.env["pf.gateway.traceability.report.audit.event"].sudo().search_count(
            [("audit_id", "=", self.id), ("event_type", "=", "completed")]
        )
        if already_used:
            raise AccessError(_("El enlace de descarga ya fue utilizado."))
        return True

    @api.model
    def init(self):
        # Database-level protection complements ACL and ORM guards.
        self.env.cr.execute(
            """
            CREATE OR REPLACE FUNCTION pf_gateway_reject_audit_mutation()
            RETURNS trigger AS $fn$
            BEGIN
                RAISE EXCEPTION 'PagoFlex traceability audit records are immutable';
            END;
            $fn$ LANGUAGE plpgsql
            """
        )
        for table in (
            "pf_gateway_traceability_report_audit",
            "pf_gateway_traceability_report_audit_event",
        ):
            self.env.cr.execute(
                """
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = current_schema() AND table_name = %s
                """,
                [table],
            )
            if not self.env.cr.fetchone():
                continue
            trigger = "%s_immutable" % table
            self.env.cr.execute('DROP TRIGGER IF EXISTS "%s" ON "%s"' % (trigger, table))
            self.env.cr.execute(
                'CREATE TRIGGER "%s" BEFORE UPDATE OR DELETE ON "%s" '
                "FOR EACH ROW EXECUTE FUNCTION pf_gateway_reject_audit_mutation()" % (trigger, table)
            )


class PfGatewayTraceabilityReportAuditEvent(models.Model):
    _name = "pf.gateway.traceability.report.audit.event"
    _description = "Evento de auditoría de reporte de trazabilidad"
    _order = "event_at, id"
    _rec_name = "event_type"

    audit_id = fields.Many2one(
        "pf.gateway.traceability.report.audit", required=True, readonly=True, ondelete="restrict", index=True
    )
    event_type = fields.Selection(
        [
            ("requested", "Solicitado"),
            ("started", "Iniciado"),
            ("completed", "Completado"),
            ("failed", "Fallido"),
            ("limit_exceeded", "Límite excedido"),
        ],
        required=True,
        readonly=True,
        index=True,
    )
    event_at = fields.Datetime(required=True, readonly=True, index=True)
    user_id = fields.Many2one("res.users", required=True, readonly=True, index=True)
    row_count = fields.Integer(readonly=True)
    file_size = fields.Integer(readonly=True)
    file_hash = fields.Char(readonly=True)
    message = fields.Char(readonly=True)

    def write(self, vals):
        raise AccessError(_("Los eventos de auditoría son inmutables."))

    def unlink(self):
        raise AccessError(_("Los eventos de auditoría son inmutables."))

    @api.model
    def init(self):
        self.env.cr.execute(
            """
            CREATE OR REPLACE FUNCTION pf_gateway_reject_audit_mutation()
            RETURNS trigger AS $fn$
            BEGIN
                RAISE EXCEPTION 'PagoFlex traceability audit records are immutable';
            END;
            $fn$ LANGUAGE plpgsql
            """
        )
        self.env.cr.execute(
            "DROP TRIGGER IF EXISTS pf_gateway_traceability_report_audit_event_immutable "
            "ON pf_gateway_traceability_report_audit_event"
        )
        self.env.cr.execute(
            "CREATE TRIGGER pf_gateway_traceability_report_audit_event_immutable "
            "BEFORE UPDATE OR DELETE ON pf_gateway_traceability_report_audit_event "
            "FOR EACH ROW EXECUTE FUNCTION pf_gateway_reject_audit_mutation()"
        )


class PfGatewayChainedTraceabilityReportWizard(models.TransientModel):
    _name = "pf.gateway.chained.traceability.report.wizard"
    _description = "Reporte de trazabilidad de movimientos encadenados por CUIT"

    cuit_text = fields.Text(string="CUITs", help="Separados por coma, punto y coma, espacio o salto de línea. Vacío = todos.")
    date_from = fields.Date(string="Desde", required=True, default=fields.Date.context_today)
    date_to = fields.Date(string="Hasta", required=True, default=fields.Date.context_today)
    operation_scope = fields.Selection(
        [("internal", "Internas"), ("external", "Externas"), ("both", "Ambas")],
        string="Tipo de operación",
        required=True,
        default="both",
    )
    max_depth = fields.Integer(string="Profundidad máxima", required=True, default=10)
    export_format = fields.Selection([("xlsx", "XLSX")], required=True, default="xlsx", readonly=True)

    @api.constrains("date_from", "date_to", "max_depth")
    def _check_parameters(self):
        for wizard in self:
            if wizard.date_from and wizard.date_to and wizard.date_from > wizard.date_to:
                raise ValidationError(_("La fecha Desde no puede ser posterior a Hasta."))
            if wizard.date_from and wizard.date_to and (wizard.date_to - wizard.date_from).days > 366:
                raise ValidationError(_("El rango máximo permitido es de 366 días."))
            if not 1 <= wizard.max_depth <= 25:
                raise ValidationError(_("La profundidad debe estar entre 1 y 25."))

    @staticmethod
    def _is_valid_cuit(cuit):
        if len(cuit) != 11 or not cuit.isdigit():
            return False
        weights = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)
        remainder = sum(int(digit) * weight for digit, weight in zip(cuit[:10], weights)) % 11
        verifier = 11 - remainder
        verifier = 0 if verifier == 11 else 9 if verifier == 10 else verifier
        return verifier == int(cuit[-1])

    def _normalized_cuits(self):
        self.ensure_one()
        parts = [re.sub(r"\D", "", value) for value in re.split(r"[,;\s]+", self.cuit_text or "") if value]
        invalid = [value for value in parts if not self._is_valid_cuit(value)]
        if invalid:
            raise ValidationError(_("CUIT inválido: %s") % ", ".join(invalid[:10]))
        normalized = list(dict.fromkeys(parts))
        if len(normalized) > 500:
            raise ValidationError(_("Se permiten como máximo 500 CUITs por solicitud."))
        return normalized

    def action_generate_xlsx(self):
        self.ensure_one()
        if not _has_report_group(self.env.user):
            raise AccessError(_("No tiene permisos para generar este reporte."))
        self._check_parameters()
        cuits = self._normalized_cuits()
        audit, token = self.env["pf.gateway.traceability.report.audit"].create_request(
            {
                "cuits": cuits,
                "all_cuits": not bool(cuits),
                "date_from": self.date_from,
                "date_to": self.date_to,
                "timezone": self.env.user.tz or "UTC",
                "operation_scope": self.operation_scope,
                "max_depth": self.max_depth,
            }
        )
        return {
            "type": "ir.actions.act_url",
            "url": "/pagoflex/traceability/%s/xlsx?token=%s" % (audit.uuid, token),
            "target": "self",
        }


class PfGatewayChainedTraceabilityReportService(models.AbstractModel):
    _name = "pf.gateway.chained.traceability.report.service"
    _description = "Servicio de reporte de trazabilidad por CUIT"

    _HEADERS = [
        "cuit_raiz", "nivel", "ruta_transferencias", "transferencia_id_odoo", "external_id",
        "origin_id", "payment_id", "connector_id", "fecha_hora_utc", "fecha_hora_local",
        "fecha_negocio", "estado_transferencia", "importe", "moneda", "concepto", "descripcion",
        "tipo_operacion", "origen_es_interno", "destino_es_interno", "cvu_cbu_origen",
        "estado_cvu_origen", "alias_origen", "app_origen", "cuit_origen", "dni_origen",
        "nombre_origen", "email_origen", "telefono_origen", "kyc_verificado_origen",
        "titular_origen_payload", "cvu_cbu_destino", "estado_cvu_destino", "alias_destino",
        "app_destino", "cuit_destino", "dni_destino", "nombre_destino", "email_destino",
        "telefono_destino", "kyc_verificado_destino", "titular_destino_payload",
    ]

    _ELIGIBLE_QUERY = r"""
        CREATE TEMP TABLE pf_trace_eligible ON COMMIT DROP AS
        WITH accounts AS (
            SELECT DISTINCT ON (regexp_replace(COALESCE(a.cvu_cbu, ''), '\D', '', 'g'))
                   a.id, a.gateway_user_id, a.cvu_cbu, a.alias, a.app, a.status,
                   regexp_replace(COALESCE(a.cvu_cbu, ''), '\D', '', 'g') AS normalized_address
              FROM pf_gateway_bank_account a
             WHERE a.cvu_cbu IS NOT NULL AND a.cvu_cbu <> ''
             ORDER BY regexp_replace(COALESCE(a.cvu_cbu, ''), '\D', '', 'g'), a.id
        ),
        users_by_cuit AS (
            SELECT DISTINCT ON (regexp_replace(COALESCE(user_rec.cuit_cuil, ''), '\D', '', 'g'))
                   user_rec.id,
                   regexp_replace(COALESCE(user_rec.cuit_cuil, ''), '\D', '', 'g') AS normalized_cuit
              FROM pf_gateway_user user_rec
             WHERE user_rec.cuit_cuil IS NOT NULL AND user_rec.cuit_cuil <> ''
             ORDER BY regexp_replace(COALESCE(user_rec.cuit_cuil, ''), '\D', '', 'g'), user_rec.id
        )
        SELECT t.id, t.external_id, t.origin_id, t.payment_id, t.connector_id,
                   t.transaction_at, t.fecha_negocio, t.status AS transfer_status, t.amount,
                   t.currency, t.concept, t.description,
                   t.source_address, t.destination_address, t.source_owner_name, t.destination_owner_name,
                   COALESCE(sa.id, saf.id) AS source_account_id,
                   COALESCE(da.id, daf.id) AS destination_account_id,
                   COALESCE(t.source_user_id, sa.gateway_user_id, saf.gateway_user_id, suf.id) AS source_user_id,
                   COALESCE(t.destination_user_id, da.gateway_user_id, daf.gateway_user_id, duf.id) AS destination_user_id,
                   COALESCE(
                       su.cuit_cuil, sua.cuit_cuil,
                       CASE WHEN UPPER(COALESCE(t.source_owner_id_type, '')) IN ('CUIT', 'CUIL', 'CUIT_CUIL')
                            THEN t.source_owner_id END
                   ) AS source_cuit_raw,
                   regexp_replace(COALESCE(
                       su.cuit_cuil, sua.cuit_cuil,
                       CASE WHEN UPPER(COALESCE(t.source_owner_id_type, '')) IN ('CUIT', 'CUIL', 'CUIT_CUIL')
                            THEN t.source_owner_id END,
                       ''
                   ), '\D', '', 'g') AS source_cuit,
                   COALESCE(
                       du.cuit_cuil, dua.cuit_cuil,
                       CASE WHEN UPPER(COALESCE(t.destination_owner_id_type, '')) IN ('CUIT', 'CUIL', 'CUIT_CUIL')
                            THEN t.destination_owner_id END
                   ) AS destination_cuit_raw,
                   COALESCE(sa.cvu_cbu, saf.cvu_cbu, t.source_address) AS source_cvu,
                   COALESCE(da.cvu_cbu, daf.cvu_cbu, t.destination_address) AS destination_cvu,
                   regexp_replace(COALESCE(sa.cvu_cbu, saf.cvu_cbu, t.source_address, ''), '\D', '', 'g')
                       AS source_cvu_normalized,
                   regexp_replace(COALESCE(da.cvu_cbu, daf.cvu_cbu, t.destination_address, ''), '\D', '', 'g')
                       AS destination_cvu_normalized,
                   COALESCE(sa.status, saf.status) AS source_account_status,
                   COALESCE(da.status, daf.status) AS destination_account_status,
                   COALESCE(sa.alias, saf.alias) AS source_alias,
                   COALESCE(da.alias, daf.alias) AS destination_alias,
                   COALESCE(sa.app, saf.app) AS source_app,
                   COALESCE(da.app, daf.app) AS destination_app,
                   COALESCE(su.dni, sua.dni) AS source_dni,
                   COALESCE(su.full_name, sua.full_name, t.source_owner_name) AS source_name,
                   COALESCE(su.email, sua.email) AS source_email,
                   COALESCE(su.phone, sua.phone) AS source_phone,
                   COALESCE(su.is_kyc_verified, sua.is_kyc_verified) AS source_kyc,
                   COALESCE(du.dni, dua.dni) AS destination_dni,
                   COALESCE(du.full_name, dua.full_name, t.destination_owner_name) AS destination_name,
                   COALESCE(du.email, dua.email) AS destination_email,
                   COALESCE(du.phone, dua.phone) AS destination_phone,
                   COALESCE(du.is_kyc_verified, dua.is_kyc_verified) AS destination_kyc
              FROM pf_gateway_transfer t
              LEFT JOIN accounts sa ON sa.id = t.source_bank_account_id
              LEFT JOIN accounts da ON da.id = t.destination_bank_account_id
              LEFT JOIN accounts saf ON saf.normalized_address = regexp_replace(COALESCE(t.source_address, ''), '\D', '', 'g')
              LEFT JOIN accounts daf ON daf.normalized_address = regexp_replace(COALESCE(t.destination_address, ''), '\D', '', 'g')
              LEFT JOIN pf_gateway_user su ON su.id = t.source_user_id
              LEFT JOIN pf_gateway_user du ON du.id = t.destination_user_id
              LEFT JOIN pf_gateway_user sua ON sua.id = COALESCE(sa.gateway_user_id, saf.gateway_user_id)
              LEFT JOIN pf_gateway_user dua ON dua.id = COALESCE(da.gateway_user_id, daf.gateway_user_id)
              LEFT JOIN users_by_cuit suf ON suf.normalized_cuit = regexp_replace(COALESCE(
                  su.cuit_cuil, sua.cuit_cuil,
                  CASE WHEN UPPER(COALESCE(t.source_owner_id_type, '')) IN ('CUIT', 'CUIL', 'CUIT_CUIL')
                       THEN t.source_owner_id END,
                  ''
              ), '\D', '', 'g')
              LEFT JOIN users_by_cuit duf ON duf.normalized_cuit = regexp_replace(COALESCE(
                  du.cuit_cuil, dua.cuit_cuil,
                  CASE WHEN UPPER(COALESCE(t.destination_owner_id_type, '')) IN ('CUIT', 'CUIL', 'CUIT_CUIL')
                       THEN t.destination_owner_id END,
                  ''
              ), '\D', '', 'g')
         WHERE t.movement_nature = 'TRANSFER'
           AND t.transaction_at >= %s AND t.transaction_at < %s
           AND UPPER(COALESCE(t.status, '')) NOT IN ('FAILED', 'CANCELLED')
    """

    _FINAL_QUERY = r"""
        SELECT result.root_cuit, result.depth, array_to_string(result.path_transfer_ids, '>'),
               eligible.id, eligible.external_id,
               origin_id, payment_id, connector_id, transaction_at, fecha_negocio, transfer_status,
               amount, currency, concept, description,
               CASE WHEN source_account_id IS NOT NULL AND destination_account_id IS NOT NULL
                    THEN 'INTERNA' ELSE 'EXTERNA' END AS operation_type,
               source_account_id IS NOT NULL, destination_account_id IS NOT NULL,
               source_cvu, source_account_status, source_alias, source_app, source_cuit_raw,
               source_dni, source_name, source_email, source_phone, source_kyc, source_owner_name,
               destination_cvu, destination_account_status, destination_alias, destination_app,
               destination_cuit_raw, destination_dni, destination_name, destination_email,
               destination_phone, destination_kyc, destination_owner_name
          FROM pf_trace_result result
          JOIN pf_trace_eligible eligible ON eligible.id = result.transfer_id
         WHERE %s = 'both'
            OR (%s = 'internal' AND source_account_id IS NOT NULL AND destination_account_id IS NOT NULL)
            OR (%s = 'external' AND (source_account_id IS NULL OR destination_account_id IS NULL))
         ORDER BY result.root_cuit, result.path_transfer_ids, result.depth, transaction_at, eligible.id
    """

    def _prepare_trace_query(self, audit, cuits, start, end):
        """Build a bounded breadth-first traversal without enumerating every path."""
        self.env.cr.execute(self._ELIGIBLE_QUERY, [start, end])
        self.env.cr.execute("CREATE INDEX ON pf_trace_eligible (source_user_id, transaction_at, id)")
        self.env.cr.execute("CREATE INDEX ON pf_trace_eligible (source_cuit)")
        self.env.cr.execute("CREATE INDEX ON pf_trace_eligible (source_cvu_normalized, transaction_at, id)")
        self.env.cr.execute(
            """
            CREATE TEMP TABLE pf_trace_result (
                root_cuit text NOT NULL,
                depth integer NOT NULL,
                path_transfer_ids integer[] NOT NULL,
                transfer_id integer NOT NULL,
                PRIMARY KEY (root_cuit, transfer_id)
            ) ON COMMIT DROP
            """
        )

        if audit.all_cuits:
            # Every CUIT is already a root. Recursing would only reproduce the same
            # transfer under many ancestors, so export every eligible edge once.
            self.env.cr.execute(
                """
                INSERT INTO pf_trace_result (root_cuit, depth, path_transfer_ids, transfer_id)
                SELECT eligible.source_cuit, 1, ARRAY[eligible.id]::integer[], eligible.id
                  FROM pf_trace_eligible eligible
                 WHERE eligible.source_cuit = ANY(%s::text[])
                ON CONFLICT DO NOTHING
                """,
                [cuits],
            )
        else:
            self._prepare_explicit_cuit_trace(cuits, audit.max_depth)

        self.env.cr.execute(
            self._FINAL_QUERY,
            [audit.operation_scope, audit.operation_scope, audit.operation_scope],
        )

    def _prepare_explicit_cuit_trace(self, cuits, max_depth):
        self.env.cr.execute(
            """
            CREATE TEMP TABLE pf_trace_visited (
                root_cuit text NOT NULL,
                node_key text NOT NULL,
                user_id integer,
                cvu text,
                depth integer NOT NULL,
                arrival_at timestamp,
                arrival_transfer_id integer,
                path_transfer_ids integer[] NOT NULL,
                PRIMARY KEY (root_cuit, node_key)
            ) ON COMMIT DROP
            """
        )
        self.env.cr.execute(
            """
            CREATE TEMP TABLE pf_trace_frontier
            (LIKE pf_trace_visited INCLUDING DEFAULTS) ON COMMIT DROP
            """
        )
        self.env.cr.execute(
            r"""
            INSERT INTO pf_trace_visited
                (root_cuit, node_key, user_id, cvu, depth, arrival_at, arrival_transfer_id, path_transfer_ids)
            SELECT DISTINCT regexp_replace(COALESCE(user_rec.cuit_cuil, ''), '\D', '', 'g'),
                            'U:' || user_rec.id::text, user_rec.id, NULL::text,
                            0, NULL::timestamp, NULL::integer, ARRAY[]::integer[]
              FROM pf_gateway_user user_rec
             WHERE regexp_replace(COALESCE(user_rec.cuit_cuil, ''), '\D', '', 'g') = ANY(%s::text[])
            """,
            [cuits],
        )
        self.env.cr.execute("INSERT INTO pf_trace_frontier SELECT * FROM pf_trace_visited")

        for depth in range(1, max_depth + 1):
            self.env.cr.execute(
                """
                INSERT INTO pf_trace_result (root_cuit, depth, path_transfer_ids, transfer_id)
                SELECT frontier.root_cuit, %s,
                       frontier.path_transfer_ids || eligible.id, eligible.id
                  FROM pf_trace_frontier frontier
                  JOIN pf_trace_eligible eligible ON (
                       (frontier.cvu IS NOT NULL AND eligible.source_cvu_normalized = frontier.cvu)
                       OR
                       (frontier.cvu IS NULL AND eligible.source_user_id = frontier.user_id)
                  )
                   AND (
                       frontier.arrival_at IS NULL
                       OR (eligible.transaction_at, eligible.id) >
                          (frontier.arrival_at, frontier.arrival_transfer_id)
                   )
                ON CONFLICT DO NOTHING
                """,
                [depth],
            )
            if depth >= max_depth:
                break
            self.env.cr.execute(
                """
                CREATE TEMP TABLE pf_trace_next_frontier ON COMMIT DROP AS
                SELECT DISTINCT ON (result.root_cuit, candidate.node_key)
                       result.root_cuit, candidate.node_key,
                       eligible.destination_user_id AS user_id,
                       candidate.cvu,
                       %s::integer AS depth, eligible.transaction_at AS arrival_at,
                       eligible.id AS arrival_transfer_id,
                       result.path_transfer_ids
                  FROM pf_trace_result result
                  JOIN pf_trace_eligible eligible ON eligible.id = result.transfer_id
                  CROSS JOIN LATERAL (
                      SELECT
                          CASE
                              WHEN eligible.destination_cvu_normalized <> ''
                                  THEN 'C:' || eligible.destination_cvu_normalized
                              WHEN eligible.destination_user_id IS NOT NULL
                                  THEN 'U:' || eligible.destination_user_id::text
                          END AS node_key,
                          NULLIF(eligible.destination_cvu_normalized, '') AS cvu
                  ) candidate
                  LEFT JOIN pf_trace_visited visited
                    ON visited.root_cuit = result.root_cuit
                   AND visited.node_key = candidate.node_key
                 WHERE result.depth = %s
                   AND candidate.node_key IS NOT NULL
                   AND visited.node_key IS NULL
                 ORDER BY result.root_cuit, candidate.node_key,
                          eligible.transaction_at, eligible.id
                """,
                [depth, depth],
            )
            self.env.cr.execute(
                """
                INSERT INTO pf_trace_visited
                SELECT * FROM pf_trace_next_frontier
                ON CONFLICT DO NOTHING
                """
            )
            self.env.cr.execute("TRUNCATE pf_trace_frontier")
            self.env.cr.execute(
                """
                INSERT INTO pf_trace_frontier
                SELECT next.*
                  FROM pf_trace_next_frontier next
                  JOIN pf_trace_visited visited
                    ON visited.root_cuit = next.root_cuit
                   AND visited.node_key = next.node_key
                   AND visited.depth = next.depth
                   AND visited.arrival_transfer_id = next.arrival_transfer_id
                """
            )
            self.env.cr.execute("SELECT COUNT(*) FROM pf_trace_frontier")
            frontier_count = self.env.cr.fetchone()[0]
            self.env.cr.execute("DROP TABLE pf_trace_next_frontier")
            if not frontier_count:
                break

    def _all_valid_cuits(self):
        raw = self.env["pf.gateway.user"].sudo().search([("cuit_cuil", "!=", False)]).mapped("cuit_cuil")
        normalized = [re.sub(r"\D", "", value or "") for value in raw]
        return sorted({value for value in normalized if len(value) == 11})

    @staticmethod
    def _utc_bounds(audit):
        timezone = pytz.timezone(audit.timezone or "UTC")
        start = timezone.localize(datetime.combine(audit.date_from, time.min)).astimezone(pytz.UTC).replace(tzinfo=None)
        end = timezone.localize(datetime.combine(audit.date_to + timedelta(days=1), time.min)).astimezone(pytz.UTC).replace(tzinfo=None)
        return start, end, timezone

    @staticmethod
    def _safe_text(value):
        if value is None:
            return ""
        text = str(value)
        if text.startswith(("=", "+", "-", "@", "\t", "\r")):
            return "'" + text
        return text

    @staticmethod
    def _account_status(value, internal):
        if not internal:
            return "NO_APLICA_EXTERNO"
        return {"active": "ACTIVO", "suspended": "SUSPENDIDO", "blocked": "BLOQUEADO"}.get(
            value, "NO_ENCONTRADO"
        )

    def generate_xlsx(self, audit):
        audit.ensure_one()
        cuits = json.loads(audit.cuit_json)
        if audit.all_cuits:
            cuits = self._all_valid_cuits()
        if not cuits:
            raise UserError(_("No se encontraron CUITs para procesar."))
        start, end, timezone = self._utc_bounds(audit)
        self.env.cr.execute("SELECT set_config('statement_timeout', %s, true)", ["90000"])
        self._prepare_trace_query(audit, cuits, start, end)

        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True, "strings_to_formulas": False, "strings_to_urls": False})
        sheet = workbook.add_worksheet("Trazabilidad")
        text_format = workbook.add_format({"num_format": "@"})
        for column, header in enumerate(self._HEADERS):
            sheet.write_string(0, column, header)

        row_number = 1
        max_rows = 200000
        while True:
            rows = self.env.cr.fetchmany(1000)
            if not rows:
                break
            for row in rows:
                if row_number > max_rows:
                    workbook.close()
                    audit.add_event("limit_exceeded", row_count=row_number - 1, message="Límite de 200000 filas")
                    raise UserError(_("El reporte supera el límite de 200.000 filas. Reduzca el período o los CUITs."))
                values = list(row)
                transaction_at = values[8]
                local_time = pytz.UTC.localize(transaction_at).astimezone(timezone) if transaction_at else None
                source_internal = bool(values[16])
                destination_internal = bool(values[17])
                export = values[:9] + [local_time.isoformat() if local_time else ""] + values[9:19]
                export += [self._account_status(values[19], source_internal)] + values[20:29]
                export += [values[29], self._account_status(values[30], destination_internal)] + values[31:]
                for column, value in enumerate(export):
                    if column == 12 and isinstance(value, (int, float)):
                        sheet.write_number(row_number, column, value)
                    else:
                        sheet.write_string(row_number, column, self._safe_text(value), text_format)
                row_number += 1

        params = workbook.add_worksheet("Parametros")
        parameter_rows = [
            ("auditoria_uuid", audit.uuid), ("generado_en_utc", fields.Datetime.now()),
            ("cuits", "TODOS" if audit.all_cuits else ",".join(cuits)),
            ("desde", audit.date_from), ("hasta", audit.date_to), ("zona_horaria", audit.timezone),
            ("tipo_operacion", audit.operation_scope), ("profundidad_maxima", audit.max_depth),
            ("cantidad_filas", row_number - 1), ("version_esquema", audit.schema_version),
        ]
        for row_idx, (key, value) in enumerate(parameter_rows):
            params.write_string(row_idx, 0, key)
            params.write_string(row_idx, 1, self._safe_text(value), text_format)
        workbook.close()
        content = output.getvalue()
        return content, row_number - 1
