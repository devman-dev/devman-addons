import logging
import hashlib
from datetime import datetime

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


_logger = logging.getLogger(__name__)


class PfGatewayBankMovementSyncRun(models.Model):
    _name = "pf.gateway.bank.movement.sync.run"
    _description = "Consulta histórica de movimientos bancarios"
    _order = "started_at desc, id desc"

    name = fields.Char(string="Referencia", compute="_compute_name", store=True)
    bank_account_id = fields.Many2one("pf.gateway.bank.account", string="Cuenta billetera", ondelete="set null", index=True)
    cbu_cvu_alias = fields.Char(string="CBU/CVU/Alias consultado", required=True, index=True)
    start_date = fields.Date(string="Fecha desde", required=True)
    end_date = fields.Date(string="Fecha hasta", required=True)
    page_size = fields.Integer(string="Tamaño página", default=10000)
    first_page_offset = fields.Integer(string="Offset inicial", default=1)
    last_page_offset = fields.Integer(string="Offset final")
    fetch_all_pages = fields.Boolean(string="Todas las páginas")
    state = fields.Selection(
        [("running", "En curso"), ("success", "Correcta"), ("failed", "Fallida")],
        default="running",
        required=True,
        index=True,
    )
    started_at = fields.Datetime(string="Inicio", default=fields.Datetime.now, required=True, index=True)
    finished_at = fields.Datetime(string="Fin")
    total_records = fields.Integer(string="Total informado")
    pages_fetched = fields.Integer(string="Páginas consultadas")
    movements_found = fields.Integer(string="Movimientos recibidos")
    movements_created = fields.Integer(string="Movimientos creados")
    movements_updated = fields.Integer(string="Movimientos existentes")
    movement_ids = fields.Many2many(
        "pf.gateway.bank.movement",
        "pf_gateway_bank_movement_sync_run_rel",
        "sync_run_id",
        "movement_id",
        string="Movimientos",
    )
    error_detail = fields.Text(string="Detalle de error")
    last_response_raw = fields.Text(string="Última respuesta cruda")

    @api.depends("cbu_cvu_alias", "start_date", "end_date", "started_at")
    def _compute_name(self):
        for record in self:
            record.name = "%s %s/%s" % (
                record.cbu_cvu_alias or "-",
                record.start_date or "-",
                record.end_date or "-",
            )


class PfGatewayBankMovement(models.Model):
    _name = "pf.gateway.bank.movement"
    _description = "Movimiento bancario PagoFlex Gateway"
    _inherit = "pf.gateway.client.mixin"
    _order = "movement_date desc, movement_time desc, id desc"

    name = fields.Char(compute="_compute_name", store=True)
    active = fields.Boolean(default=True)
    bank_account_id = fields.Many2one("pf.gateway.bank.account", string="Cuenta billetera", ondelete="set null", index=True)
    cbu_cvu_alias = fields.Char(string="CBU/CVU/Alias consultado", required=True, index=True)
    product_uid = fields.Char(string="Producto UID", index=True)
    request_date_from = fields.Date(string="Fecha desde")
    request_date_to = fields.Date(string="Fecha hasta")
    opening_balance = fields.Float(string="Saldo partida", digits=(16, 2))
    total_records = fields.Integer(string="Total registros informado")

    movement_id = fields.Char(string="ID movimiento", index=True)
    movement_identity = fields.Char(string="Identidad bancaria", compute="_compute_movement_identity", store=True, index=True)
    origin_id = fields.Char(string="Origin ID", index=True)
    movement_date = fields.Date(string="Fecha", index=True)
    movement_time = fields.Char(string="Hora")
    movement_datetime = fields.Datetime(string="Fecha/hora", compute="_compute_movement_datetime", store=True, index=True)
    concept = fields.Char(string="Concepto")
    description = fields.Text(string="Descripción")
    reference = fields.Char(string="Referencia", index=True)
    debit_credit = fields.Selection([("D", "Débito"), ("C", "Crédito")], string="Débito/Crédito", index=True)
    currency = fields.Char(string="Moneda")
    amount = fields.Float(string="Importe", digits=(16, 2), index=True)
    coelsa_id = fields.Char(string="ID Coelsa", index=True)
    movement_nature = fields.Char(string="Naturaleza")
    movement_direction = fields.Selection(
        [("INCOMING", "Entrante"), ("OUTGOING", "Saliente")],
        string="Dirección",
        index=True,
    )
    display_label = fields.Char(string="Etiqueta")

    counterparty_name = fields.Char(string="Contraparte")
    counterparty_vat = fields.Char(string="CUIT/CUIL contraparte", index=True)
    counterparty_cbu_cvu = fields.Char(string="CBU/CVU contraparte", index=True)

    matched_transfer_id = fields.Many2one("pf.gateway.transfer", string="Transferencia conciliada", ondelete="set null", index=True)
    reconciliation_state = fields.Selection(
        [
            ("pending", "Pendiente"),
            ("auto", "Conciliada automática"),
            ("manual", "Conciliada manual"),
            ("conflict", "Revisar"),
            ("ignored", "Ignorada"),
        ],
        string="Estado conciliación",
        default="pending",
        required=True,
        index=True,
    )
    reconciliation_note = fields.Char(string="Nota conciliación")
    reconciled_at = fields.Datetime(string="Fecha conciliación")
    last_sync_at = fields.Datetime(string="Última sincronización", index=True)
    sync_run_ids = fields.Many2many(
        "pf.gateway.bank.movement.sync.run",
        "pf_gateway_bank_movement_sync_run_rel",
        "movement_id",
        "sync_run_id",
        string="Consultas históricas",
    )
    raw_payload = fields.Text(string="Payload crudo")

    _sql_constraints = [
        (
            "pf_gateway_bank_movement_cvu_identity_uniq",
            "unique(cbu_cvu_alias, movement_identity)",
            "El movimiento bancario ya existe para la cuenta consultada.",
        ),
    ]

    @api.depends("movement_id", "origin_id", "movement_date", "amount")
    def _compute_name(self):
        for record in self:
            label = record.movement_id or record.origin_id or _("Sin ID")
            if record.movement_date:
                label = f"{record.movement_date} - {label}"
            if record.amount:
                label = f"{label} ({record.amount:.2f})"
            record.name = label

    @api.depends(
        "movement_id",
        "origin_id",
        "movement_date",
        "movement_time",
        "concept",
        "reference",
        "debit_credit",
        "amount",
        "coelsa_id",
        "movement_direction",
        "counterparty_vat",
        "counterparty_cbu_cvu",
    )
    def _compute_movement_identity(self):
        for record in self:
            record.movement_identity = self._movement_identity_hash(
                {
                    "movement_id": record.movement_id,
                    "origin_id": record.origin_id,
                    "movement_date": fields.Date.to_string(record.movement_date) if record.movement_date else False,
                    "movement_time": record.movement_time,
                    "concept": record.concept,
                    "reference": record.reference,
                    "debit_credit": record.debit_credit,
                    "amount": record.amount,
                    "coelsa_id": record.coelsa_id,
                    "movement_direction": record.movement_direction,
                    "counterparty_vat": record.counterparty_vat,
                    "counterparty_cbu_cvu": record.counterparty_cbu_cvu,
                }
            )

    @api.depends("movement_date", "movement_time")
    def _compute_movement_datetime(self):
        for record in self:
            record.movement_datetime = False
            if not record.movement_date:
                continue
            time_value = (record.movement_time or "00:00:00").strip() or "00:00:00"
            try:
                parsed = datetime.strptime(f"{record.movement_date} {time_value[:8]}", "%Y-%m-%d %H:%M:%S")
            except ValueError:
                parsed = datetime.combine(record.movement_date, datetime.min.time())
            record.movement_datetime = parsed

    @api.constrains("request_date_from", "request_date_to")
    def _check_request_dates(self):
        for record in self:
            if record.request_date_from and record.request_date_to and record.request_date_from > record.request_date_to:
                raise ValidationError(_("La fecha desde no puede ser posterior a la fecha hasta."))

    @api.model
    def sync_from_gateway_account(
        self,
        bank_account=None,
        cbu_cvu_alias=None,
        start_date=None,
        end_date=None,
        page_size=10000,
        page_offset=1,
        fetch_all_pages=False,
    ):
        bank_account = bank_account or self.env["pf.gateway.bank.account"].browse()
        cbu_cvu_alias = (cbu_cvu_alias or bank_account.cvu_cbu or bank_account.alias or "").strip()
        if not cbu_cvu_alias:
            raise UserError(_("Debes indicar un CBU/CVU/Alias para consultar movimientos."))
        if not start_date or not end_date:
            raise UserError(_("Debes indicar fecha desde y fecha hasta."))
        if start_date > end_date:
            raise UserError(_("La fecha desde no puede ser posterior a la fecha hasta."))

        page_size = int(page_size or 10000)
        current_offset = int(page_offset or 1)
        run = self.env["pf.gateway.bank.movement.sync.run"].sudo().create(
            {
                "bank_account_id": bank_account.id if bank_account else False,
                "cbu_cvu_alias": cbu_cvu_alias,
                "start_date": start_date,
                "end_date": end_date,
                "page_size": page_size,
                "first_page_offset": current_offset,
                "last_page_offset": current_offset,
                "fetch_all_pages": bool(fetch_all_pages),
            }
        )

        records = self.browse()
        created_count = 0
        updated_count = 0
        received_count = 0
        total_records = 0
        pages_fetched = 0
        seen_page_keys = set()
        try:
            for _page_guard in range(1000):
                response, data, movements = self._fetch_bank_movements_page(
                    cbu_cvu_alias=cbu_cvu_alias,
                    start_date=start_date,
                    end_date=end_date,
                    page_size=page_size,
                    page_offset=current_offset,
                )
                page_total = data.get("totalRegistros") or 0
                total_records = max(total_records, page_total, len(movements))
                received_count += len(movements)
                pages_fetched += 1
                page_keys = {
                    self._movement_identity_key(item, cbu_cvu_alias)
                    for item in movements
                    if isinstance(item, dict)
                }

                for item in movements:
                    if not isinstance(item, dict):
                        continue
                    values = self._values_from_gateway_item(
                        item,
                        bank_account=bank_account,
                        cbu_cvu_alias=cbu_cvu_alias,
                        response_data=data,
                    )
                    domain = self._movement_lookup_domain(values)
                    record = self.sudo().search(domain, limit=1) if domain else self.browse()
                    write_values = dict(values)
                    write_values.pop("movement_identity", None)
                    if record:
                        record.write(write_values)
                        updated_count += 1
                    else:
                        record = self.sudo().create(write_values)
                        created_count += 1
                    records |= record

                run.write(
                    {
                        "last_page_offset": current_offset,
                        "total_records": total_records,
                        "pages_fetched": pages_fetched,
                        "movements_found": received_count,
                        "movements_created": created_count,
                        "movements_updated": updated_count,
                        "movement_ids": [(6, 0, records.ids)],
                        "last_response_raw": self._payload_to_text(response),
                    }
                )

                if not fetch_all_pages:
                    break
                if not movements:
                    break
                if page_keys and page_keys.issubset(seen_page_keys):
                    break
                seen_page_keys.update(page_keys)
                current_offset += 1
            else:
                raise UserError(_("Se alcanzó el límite de 1000 páginas para una única consulta."))

            run.write({"state": "success", "finished_at": fields.Datetime.now()})
        except Exception as exc:
            run.write(
                {
                    "state": "failed",
                    "finished_at": fields.Datetime.now(),
                    "error_detail": str(exc),
                    "movement_ids": [(6, 0, records.ids)],
                }
            )
            raise

        return {
            "count": len(records),
            "record_ids": records.ids,
            "created": created_count,
            "updated": updated_count,
            "total_records": total_records,
            "pages_fetched": pages_fetched,
            "sync_run_id": run.id,
        }

    @api.model
    def _fetch_bank_movements_page(self, *, cbu_cvu_alias, start_date, end_date, page_size, page_offset):
        payload = {
            "startDate": fields.Date.to_string(start_date),
            "endDate": fields.Date.to_string(end_date),
            "pageSize": int(page_size or 10000),
            "pageOffset": int(page_offset or 1),
        }
        response = self._gateway_request_json(
            "POST",
            f"/admin/gateway/movements/{cbu_cvu_alias}",
            payload=payload,
        )
        data = response.get("data") if isinstance(response, dict) else None
        if not isinstance(data, dict):
            raise UserError(_("La respuesta del gateway no contiene data válida."))

        movements = data.get("movimientos") or []
        if not isinstance(movements, list):
            raise UserError(_("La respuesta del gateway no contiene una lista válida de movimientos."))
        return response, data, movements

    @api.model
    def _movement_identity_key(self, item, cbu_cvu_alias):
        return (cbu_cvu_alias, self._movement_identity_hash(self._movement_identity_values_from_item(item)))

    @api.model
    def _movement_identity_values_from_item(self, item):
        counterparty = item.get("detalleContraparte") if isinstance(item.get("detalleContraparte"), dict) else {}
        return {
            "movement_id": item.get("idMovimiento"),
            "origin_id": item.get("origin_id"),
            "movement_date": item.get("fecha"),
            "movement_time": item.get("hora"),
            "concept": item.get("concepto"),
            "reference": item.get("referencia"),
            "debit_credit": item.get("debitoCredito"),
            "amount": item.get("importe"),
            "coelsa_id": item.get("idCoelsa"),
            "movement_direction": item.get("movement_direction"),
            "counterparty_vat": counterparty.get("cuitCuil"),
            "counterparty_cbu_cvu": counterparty.get("cbuCvu"),
        }

    @api.model
    def _movement_identity_hash(self, values):
        parts = [
            str(values.get("movement_id") or values.get("origin_id") or ""),
            str(values.get("movement_date") or ""),
            str(values.get("movement_time") or ""),
            str(values.get("concept") or ""),
            str(values.get("reference") or ""),
            str(values.get("debit_credit") or ""),
            "%.2f" % float(values.get("amount") or 0.0),
            str(values.get("coelsa_id") or ""),
            str(values.get("movement_direction") or ""),
            str(values.get("counterparty_vat") or ""),
            str(values.get("counterparty_cbu_cvu") or ""),
        ]
        return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()

    @api.model
    def _values_from_gateway_item(self, item, *, bank_account, cbu_cvu_alias, response_data):
        counterparty = item.get("detalleContraparte") if isinstance(item.get("detalleContraparte"), dict) else {}
        return {
            "active": True,
            "bank_account_id": bank_account.id if bank_account else False,
            "cbu_cvu_alias": cbu_cvu_alias,
            "product_uid": response_data.get("productoUID"),
            "request_date_from": self._coerce_date(response_data.get("fechaDesde"), field_name="fechaDesde"),
            "request_date_to": self._coerce_date(response_data.get("fechaHasta"), field_name="fechaHasta"),
            "opening_balance": response_data.get("saldoPartida") or 0.0,
            "total_records": response_data.get("totalRegistros") or 0,
            "movement_id": item.get("idMovimiento"),
            "movement_identity": self._movement_identity_hash(self._movement_identity_values_from_item(item)),
            "origin_id": item.get("origin_id"),
            "movement_date": self._coerce_date(item.get("fecha"), field_name="fecha"),
            "movement_time": item.get("hora"),
            "concept": item.get("concepto"),
            "description": item.get("description"),
            "reference": item.get("referencia"),
            "debit_credit": item.get("debitoCredito") if item.get("debitoCredito") in ("D", "C") else False,
            "currency": item.get("moneda"),
            "amount": item.get("importe") or 0.0,
            "coelsa_id": item.get("idCoelsa"),
            "movement_nature": item.get("movement_nature"),
            "movement_direction": item.get("movement_direction") if item.get("movement_direction") in ("INCOMING", "OUTGOING") else False,
            "display_label": item.get("display_label"),
            "counterparty_name": counterparty.get("nombre"),
            "counterparty_vat": counterparty.get("cuitCuil"),
            "counterparty_cbu_cvu": counterparty.get("cbuCvu"),
            "last_sync_at": fields.Datetime.now(),
            "raw_payload": self._payload_to_text(item),
        }

    @api.model
    def _movement_lookup_domain(self, values):
        account_id = values.get("bank_account_id")
        cbu_cvu_alias = values.get("cbu_cvu_alias")
        movement_identity = values.get("movement_identity")
        movement_id = values.get("movement_id")
        origin_id = values.get("origin_id")
        if cbu_cvu_alias and movement_identity:
            return [("cbu_cvu_alias", "=", cbu_cvu_alias), ("movement_identity", "=", movement_identity)]
        if account_id and movement_id:
            return [("bank_account_id", "=", account_id), ("movement_id", "=", movement_id)]
        if cbu_cvu_alias and movement_id:
            return [("cbu_cvu_alias", "=", cbu_cvu_alias), ("movement_id", "=", movement_id)]
        if account_id and origin_id:
            return [("bank_account_id", "=", account_id), ("origin_id", "=", origin_id)]
        if cbu_cvu_alias and origin_id:
            return [("cbu_cvu_alias", "=", cbu_cvu_alias), ("origin_id", "=", origin_id)]
        return []

    def action_auto_reconcile(self):
        reconciled = 0
        conflicts = 0
        for record in self:
            if record.matched_transfer_id and record.reconciliation_state in ("auto", "manual"):
                continue
            candidates = record._find_transfer_candidates()
            if len(candidates) == 1:
                record.write(
                    {
                        "matched_transfer_id": candidates.id,
                        "reconciliation_state": "auto",
                        "reconciliation_note": _("Conciliada automáticamente."),
                        "reconciled_at": fields.Datetime.now(),
                    }
                )
                reconciled += 1
            elif len(candidates) > 1:
                record.write(
                    {
                        "reconciliation_state": "conflict",
                        "reconciliation_note": _("Más de una transferencia candidata. Requiere revisión manual."),
                    }
                )
                conflicts += 1
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Conciliación automática"),
                "message": _("Conciliadas: %(ok)s. Conflictos: %(conflicts)s.") % {"ok": reconciled, "conflicts": conflicts},
                "type": "success" if not conflicts else "warning",
                "sticky": False,
            },
        }

    def _find_transfer_candidates(self):
        self.ensure_one()
        transfer_model = self.env["pf.gateway.transfer"].sudo()
        domains = []
        if self.origin_id:
            domains.append([("origin_id", "=", self.origin_id)])
        if self.coelsa_id:
            domains.append([("connector_id", "=", self.coelsa_id)])
        if self.reference:
            domains.append(["|", ("payment_id", "=", self.reference), ("origin_id", "=", self.reference)])

        candidates = transfer_model.browse()
        for domain in domains:
            candidates |= transfer_model.search(domain)
        if candidates:
            return candidates

        if not self.movement_date:
            return candidates
        amount = abs(self.amount or 0.0)
        if not amount:
            return candidates
        return transfer_model.search(
            [
                ("transaction_at", ">=", datetime.combine(self.movement_date, datetime.min.time())),
                ("transaction_at", "<=", datetime.combine(self.movement_date, datetime.max.time())),
                ("amount", "=", amount),
            ]
        )

    def action_mark_manual_reconciled(self):
        for record in self:
            if not record.matched_transfer_id:
                raise UserError(_("Selecciona una transferencia para conciliar manualmente."))
            record.write(
                {
                    "reconciliation_state": "manual",
                    "reconciliation_note": _("Conciliada manualmente."),
                    "reconciled_at": fields.Datetime.now(),
                }
            )
        return True

    def action_reset_reconciliation(self):
        self.write(
            {
                "matched_transfer_id": False,
                "reconciliation_state": "pending",
                "reconciliation_note": False,
                "reconciled_at": False,
            }
        )
        return True

    def action_ignore_reconciliation(self):
        self.write(
            {
                "reconciliation_state": "ignored",
                "reconciliation_note": _("Movimiento ignorado manualmente."),
                "reconciled_at": fields.Datetime.now(),
            }
        )
        return True
