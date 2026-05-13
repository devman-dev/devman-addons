from odoo import _, api, fields, models
from odoo.exceptions import UserError


class PfGatewayBankAccountAssignment(models.Model):
    _name = "pf.gateway.bank.account.assignment"
    _description = "Asignacion de CVU a comisionista"
    _inherit = "pf.gateway.client.mixin"
    _order = "updated_at desc, id desc"

    external_id = fields.Char(string="ID gateway", index=True, readonly=True)
    bank_account_id = fields.Many2one(
        "pf.gateway.bank.account",
        string="Cuenta bancaria",
        ondelete="cascade",
        index=True,
    )
    assigned_user_id = fields.Many2one(
        "pf.gateway.user",
        string="Usuario asignado",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        "pf.gateway.company",
        string="Empresa",
        required=True,
        ondelete="cascade",
        index=True,
    )
    assignment_type = fields.Char(string="Tipo de asignacion", required=True, default="commission_agent", index=True)
    is_active = fields.Boolean(string="Activo", default=True, index=True)
    created_at = fields.Datetime(string="Creado en gateway", readonly=True)
    updated_at = fields.Datetime(string="Actualizado en gateway", readonly=True, index=True)
    last_sync_at = fields.Datetime(string="Última sincronización", readonly=True, index=True)
    raw_payload = fields.Text(string="Payload crudo", readonly=True)

    _sql_constraints = [
        (
            "pf_gateway_bank_account_assignment_external_id_uniq",
            "unique(external_id)",
            "El ID gateway de la asignacion debe ser unico.",
        ),
        (
            "pf_gateway_bank_account_assignment_unique_tuple",
            "unique(bank_account_id, assigned_user_id, company_id, assignment_type)",
            "Ya existe una asignación con la misma cuenta, usuario, empresa y tipo.",
        ),
    ]

    def _gateway_payload(self):
        self.ensure_one()
        if not self.bank_account_id:
            return {}
        if not self.bank_account_id.external_id:
            raise UserError(_("La cuenta bancaria seleccionada no tiene ID gateway."))
        if not self.assigned_user_id.external_id:
            raise UserError(_("El usuario asignado no tiene ID gateway."))
        if not self.company_id.external_id:
            raise UserError(_("La empresa seleccionada no tiene ID gateway."))

        payload = {
            "bank_account_id": self.bank_account_id.external_id,
            "assigned_user_id": self.assigned_user_id.external_id,
            "company_id": self.company_id.external_id,
            "assignment_type": self.assignment_type,
            "is_active": bool(self.is_active),
        }
        if self.external_id:
            payload["id"] = self.external_id
        return payload

    def _resolve_bank_account(self, external_id):
        bank_account = self.env["pf.gateway.bank.account"].search([("external_id", "=", str(external_id))], limit=1)
        if not bank_account:
            raise UserError(
                _("No existe la cuenta bancaria local para bank_account_id=%s. Sincroniza cuentas primero.") % external_id
            )
        return bank_account

    def _resolve_assigned_user(self, external_id):
        user = self.env["pf.gateway.user"].search([("external_id", "=", str(external_id))], limit=1)
        if not user:
            raise UserError(_("No existe el usuario local para assigned_user_id=%s. Sincroniza usuarios primero.") % external_id)
        return user

    def _resolve_company(self, external_id):
        company = self.env["pf.gateway.company"].search([("external_id", "=", str(external_id))], limit=1)
        if not company:
            raise UserError(_("No existe la empresa local para company_id=%s. Sincroniza empresas primero.") % external_id)
        return company

    def _values_from_gateway_item(self, item):
        bank_account_external_id = item.get("bank_account_id")
        assigned_user_external_id = item.get("assigned_user_id")
        company_external_id = item.get("company_id")

        if not bank_account_external_id:
            raise UserError(_("El gateway no devolvió bank_account_id para una asignación."))
        if not assigned_user_external_id:
            raise UserError(_("El gateway no devolvió assigned_user_id para una asignación."))
        if not company_external_id:
            raise UserError(_("El gateway no devolvió company_id para una asignación."))

        bank_account = self._resolve_bank_account(bank_account_external_id)
        assigned_user = self._resolve_assigned_user(assigned_user_external_id)
        company = self._resolve_company(company_external_id)

        return {
            "external_id": str(item.get("id")) if item.get("id") is not None else False,
            "bank_account_id": bank_account.id,
            "assigned_user_id": assigned_user.id,
            "company_id": company.id,
            "assignment_type": item.get("assignment_type") or "commission_agent",
            "is_active": item.get("is_active", True),
            "created_at": self._coerce_datetime(item.get("created_at"), field_name="created_at"),
            "updated_at": self._coerce_datetime(item.get("updated_at"), field_name="updated_at"),
            "last_sync_at": fields.Datetime.now(),
            "raw_payload": self._payload_to_text(item),
        }

    def _update_from_gateway_payload(self, payload):
        self.ensure_one()
        if not isinstance(payload, dict):
            return
        vals = self._values_from_gateway_item(payload)
        vals["raw_payload"] = self._payload_to_text(payload)
        self.with_context(skip_gateway_bank_account_assignment_push=True).write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if self.env.context.get("skip_gateway_bank_account_assignment_push"):
            return records

        for record in records:
            if not record.bank_account_id:
                continue
            response = record._gateway_request_json(
                "POST",
                "/admin/gateway/bank-account-assignments",
                payload=record._gateway_payload(),
            )
            record._update_from_gateway_payload(response)
        return records

    def write(self, vals):
        result = super().write(vals)
        if self.env.context.get("skip_gateway_bank_account_assignment_push"):
            return result

        push_fields = {"bank_account_id", "assigned_user_id", "company_id", "assignment_type", "is_active"}
        if not push_fields.intersection(vals):
            return result

        for record in self:
            if not record.bank_account_id:
                continue
            response = record._gateway_request_json(
                "POST",
                "/admin/gateway/bank-account-assignments",
                payload=record._gateway_payload(),
            )
            record._update_from_gateway_payload(response)
        return result

    def unlink(self):
        if self.env.context.get("skip_gateway_bank_account_assignment_push"):
            return super().unlink()

        for record in self:
            if not record.external_id:
                continue
            record._gateway_request_json(
                "DELETE",
                f"/admin/gateway/bank-account-assignments/{record.external_id}",
            )
        return super().unlink()

    def action_sync_bank_account_assignments(self):
        self.sync_from_gateway(mode="manual", sync_mode="incremental")
        return True

    def action_create_subaccount(self):
        self.ensure_one()
        company_user = self.company_id.created_by_user_id
        return {
            "type": "ir.actions.act_window",
            "name": _("Crear cuenta bancaria para asignación"),
            "res_model": "pf.gateway.bank.account.assignment.subaccount.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_assignment_id": self.id,
                "default_user_id": company_user.id if company_user else False,
            },
        }

    def action_refresh_from_gateway(self):
        for record in self:
            if not record.external_id:
                continue
            payload = record._gateway_request_json(
                "GET",
                f"/admin/gateway/bank-account-assignments/{record.external_id}",
            )
            record._update_from_gateway_payload(payload)
        return True

    def sync_from_gateway(self, mode="manual", sync_mode="incremental", company=None, assignment_type=None, job=None):
        updated_since = None
        if sync_mode == "incremental":
            updated_since = self.search([], order="updated_at desc", limit=1).updated_at

        extra_params = {}
        if company and company.external_id:
            extra_params["company_id"] = company.external_id
        if assignment_type:
            extra_params["assignment_type"] = assignment_type

        log = self.env["pf.gateway.sync.log"].create(
            {
                "name": f"Sincronizar asignaciones de cuentas ({sync_mode})",
                "resource": "bank_account_assignments",
                "mode": mode,
                "job_id": job.id if job else False,
            }
        )
        try:
            items = self._gateway_paginated_get(
                "/admin/gateway/bank-account-assignments",
                updated_since=updated_since,
                extra_params=extra_params,
            )
            for item in items:
                values = self._values_from_gateway_item(item)
                record = self.search([("external_id", "=", values["external_id"])], limit=1)
                if not record:
                    record = self.search(
                        [
                            ("bank_account_id", "=", values["bank_account_id"]),
                            ("assigned_user_id", "=", values["assigned_user_id"]),
                            ("company_id", "=", values["company_id"]),
                            ("assignment_type", "=", values["assignment_type"]),
                        ],
                        limit=1,
                    )
                if record:
                    record.with_context(skip_gateway_bank_account_assignment_push=True).write(values)
                else:
                    self.with_context(skip_gateway_bank_account_assignment_push=True).create(values)

            log.write(
                {
                    "status": "success",
                    "finished_at": fields.Datetime.now(),
                    "records_processed": len(items),
                    "message": f"Asignaciones sincronizadas: {len(items)}",
                }
            )
            return len(items)
        except Exception as exc:
            log.write(
                {
                    "status": "failed",
                    "finished_at": fields.Datetime.now(),
                    "error_detail": str(exc),
                    "message": "La sincronización de asignaciones falló.",
                }
            )
            if job:
                job.write(
                    {
                        "last_run_at": fields.Datetime.now(),
                        "last_status": "failed",
                        "last_message": str(exc),
                    }
                )
            raise
