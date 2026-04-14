from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None


class CasinoProviderConfig(models.Model):
    _name = "casino.provider.config"
    _description = "Casino Provider YAML Configuration"
    _order = "provider_code, id desc"

    name = fields.Char(required=True)
    provider_code = fields.Char(required=True, index=True)
    file_name = fields.Char(required=True)
    yaml_content = fields.Text(required=True, default="")
    active = fields.Boolean(default=True)
    is_active = fields.Boolean(string="Activo", related="active", readonly=False)
    file_path = fields.Char(readonly=True)
    version = fields.Integer(default=1)
    last_loaded_at = fields.Datetime(readonly=True)
    last_written_at = fields.Datetime(readonly=True)
    last_validation_status = fields.Selection(
        [("draft", "Draft"), ("valid", "Valid"), ("invalid", "Invalid")],
        default="draft",
        readonly=True,
    )
    last_validation_message = fields.Text(readonly=True)
    notes = fields.Text()
    loaded_from_disk = fields.Boolean(readonly=True, default=False)

    yaml_parse_error = fields.Text(compute="_compute_yaml_details")
    provider_name_yaml = fields.Char(string="Nombre del proveedor", compute="_compute_yaml_details")
    provider_type_yaml = fields.Char(string="Tipo de proveedor", compute="_compute_yaml_details")
    base_url_yaml = fields.Char(string="URL base", compute="_compute_yaml_details")
    agency_id_yaml = fields.Char(string="Agency ID", compute="_compute_yaml_details")
    agency_code_yaml = fields.Char(string="Agency Code", compute="_compute_yaml_details")
    auth_mode_yaml = fields.Char(string="Modo de autenticacion", compute="_compute_yaml_details")
    auth_session_operation_yaml = fields.Char(string="Operacion de sesion", compute="_compute_yaml_details")
    auth_token_field_yaml = fields.Char(string="Campo del token", compute="_compute_yaml_details")
    auth_token_location_yaml = fields.Char(string="Ubicacion del token", compute="_compute_yaml_details")
    auth_hash_field_yaml = fields.Char(string="Campo del hash", compute="_compute_yaml_details")
    auth_hash_location_yaml = fields.Char(string="Ubicacion del hash", compute="_compute_yaml_details")
    supports_session_authorization_yaml = fields.Boolean(string="Soporta autorizacion de sesion", compute="_compute_yaml_details")
    supports_balance_check_yaml = fields.Boolean(string="Soporta consulta de saldo", compute="_compute_yaml_details")
    supports_operation_status_yaml = fields.Boolean(string="Soporta estado de operacion", compute="_compute_yaml_details")
    supports_wallet_operation_yaml = fields.Boolean(string="Soporta operaciones de wallet", compute="_compute_yaml_details")
    supports_round_close_yaml = fields.Boolean(string="Soporta cierre de ronda", compute="_compute_yaml_details")
    supports_reversal_yaml = fields.Boolean(string="Soporta reversa", compute="_compute_yaml_details")
    timeout_connect_ms_yaml = fields.Integer(string="Timeout de conexion (ms)", compute="_compute_yaml_details")
    timeout_read_ms_yaml = fields.Integer(string="Timeout de lectura (ms)", compute="_compute_yaml_details")
    retry_max_attempts_yaml = fields.Integer(string="Maximo de reintentos", compute="_compute_yaml_details")
    retry_on_yaml = fields.Text(string="Reintentar en", compute="_compute_yaml_details")
    require_currency_yaml = fields.Boolean(string="Requiere moneda", compute="_compute_yaml_details")
    require_hash_yaml = fields.Boolean(string="Requiere hash", compute="_compute_yaml_details")
    require_remote_player_id_yaml = fields.Boolean(string="Requiere remote player ID", compute="_compute_yaml_details")
    require_operation_id_yaml = fields.Boolean(string="Requiere operation ID", compute="_compute_yaml_details")
    require_round_id_for_stake_yaml = fields.Boolean(string="Requiere round ID para stake", compute="_compute_yaml_details")
    require_round_id_for_payout_yaml = fields.Boolean(string="Requiere round ID para payout", compute="_compute_yaml_details")
    amount_min_yaml = fields.Float(string="Monto minimo", compute="_compute_yaml_details")
    transaction_id_max_length_yaml = fields.Integer(string="Largo maximo de transaction ID", compute="_compute_yaml_details")
    status_mapping_yaml = fields.Text(string="Mapeo de estados", compute="_compute_yaml_details")
    error_mapping_yaml = fields.Text(string="Mapeo de errores", compute="_compute_yaml_details")
    provider_metadata_yaml = fields.Text(string="Metadata del proveedor", compute="_compute_yaml_details")
    operation_names_yaml = fields.Char(string="Operaciones", compute="_compute_yaml_details")
    operations_detail_yaml = fields.Text(string="Detalle de operaciones", compute="_compute_yaml_details")

    _sql_constraints = [
        ("casino_provider_config_code_uniq", "unique(provider_code)", "El provider_code debe ser unico."),
        ("casino_provider_config_file_name_uniq", "unique(file_name)", "El file_name debe ser unico."),
    ]

    @api.depends("yaml_content")
    def _compute_yaml_details(self):
        for record in self:
            values = record._empty_yaml_detail_values()
            parsed = record._parse_yaml_content()
            if parsed.get("__parse_error__"):
                values["yaml_parse_error"] = parsed["__parse_error__"]
            else:
                record._fill_yaml_detail_values(values, parsed)
            for field_name, value in values.items():
                record[field_name] = value

    @api.constrains("file_name")
    def _check_file_name(self):
        for record in self:
            if not record.file_name:
                continue
            file_name = record.file_name.strip()
            if "/" in file_name or "\\" in file_name:
                raise ValidationError(_("El nombre de archivo no puede contener rutas."))
            if not file_name.endswith((".yaml", ".yml")):
                raise ValidationError(_("El archivo debe terminar en .yaml o .yml."))

    @api.onchange("provider_code")
    def _onchange_provider_code(self):
        for record in self:
            if record.provider_code and (not record.file_name or record.file_name == "new_provider.yaml"):
                record.file_name = f"{record.provider_code}.yaml"
            if record.provider_code and not record.name:
                record.name = record.provider_code

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            provider_code = (vals.get("provider_code") or "").strip()
            if provider_code:
                vals.setdefault("name", provider_code)
                vals.setdefault("file_name", f"{provider_code}.yaml")
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("provider_code") and not vals.get("file_name"):
            vals["file_name"] = f"{vals['provider_code']}.yaml"
        return super().write(vals)

    def _service(self):
        return self.env["casino.api.provider.config.service"].sudo()

    @staticmethod
    def _empty_yaml_detail_values():
        return {
            "yaml_parse_error": False,
            "provider_name_yaml": False,
            "provider_type_yaml": False,
            "base_url_yaml": False,
            "agency_id_yaml": False,
            "agency_code_yaml": False,
            "auth_mode_yaml": False,
            "auth_session_operation_yaml": False,
            "auth_token_field_yaml": False,
            "auth_token_location_yaml": False,
            "auth_hash_field_yaml": False,
            "auth_hash_location_yaml": False,
            "supports_session_authorization_yaml": False,
            "supports_balance_check_yaml": False,
            "supports_operation_status_yaml": False,
            "supports_wallet_operation_yaml": False,
            "supports_round_close_yaml": False,
            "supports_reversal_yaml": False,
            "timeout_connect_ms_yaml": 0,
            "timeout_read_ms_yaml": 0,
            "retry_max_attempts_yaml": 0,
            "retry_on_yaml": False,
            "require_currency_yaml": False,
            "require_hash_yaml": False,
            "require_remote_player_id_yaml": False,
            "require_operation_id_yaml": False,
            "require_round_id_for_stake_yaml": False,
            "require_round_id_for_payout_yaml": False,
            "amount_min_yaml": 0.0,
            "transaction_id_max_length_yaml": 0,
            "status_mapping_yaml": False,
            "error_mapping_yaml": False,
            "provider_metadata_yaml": False,
            "operation_names_yaml": False,
            "operations_detail_yaml": False,
        }

    def _parse_yaml_content(self):
        self.ensure_one()
        if not self.yaml_content or not self.yaml_content.strip():
            return {}
        if yaml is None:
            return {"__parse_error__": _("PyYAML no esta disponible en el entorno de Odoo.")}
        try:
            parsed = yaml.safe_load(self.yaml_content) or {}
        except Exception as exc:
            return {"__parse_error__": _("Error de parseo YAML: %s") % exc}
        if not isinstance(parsed, dict):
            return {"__parse_error__": _("La raiz del YAML debe ser un objeto.")}
        return parsed

    def _fill_yaml_detail_values(self, values, parsed):
        agency = parsed.get("agency") or {}
        authentication = parsed.get("authentication") or {}
        capabilities = parsed.get("capabilities") or {}
        timeouts = parsed.get("timeouts") or {}
        retries = parsed.get("retries") or {}
        validations = parsed.get("validations") or {}
        status_mapping = parsed.get("status_mapping") or {}
        error_mapping = parsed.get("error_mapping") or {}
        provider_metadata = parsed.get("provider_metadata") or {}
        operations = parsed.get("operations") or parsed.get("endpoints") or {}

        values.update(
            {
                "provider_name_yaml": self._text_value(parsed.get("provider_name")),
                "provider_type_yaml": self._text_value(parsed.get("provider_type")),
                "base_url_yaml": self._text_value(parsed.get("base_url")),
                "agency_id_yaml": self._text_value(agency.get("id")),
                "agency_code_yaml": self._text_value(agency.get("code")),
                "auth_mode_yaml": self._text_value(authentication.get("mode")),
                "auth_session_operation_yaml": self._text_value(authentication.get("session_operation")),
                "auth_token_field_yaml": self._text_value(authentication.get("token_field")),
                "auth_token_location_yaml": self._text_value(authentication.get("token_location")),
                "auth_hash_field_yaml": self._text_value(authentication.get("hash_field")),
                "auth_hash_location_yaml": self._text_value(authentication.get("hash_location")),
                "supports_session_authorization_yaml": bool(capabilities.get("supports_session_authorization")),
                "supports_balance_check_yaml": bool(capabilities.get("supports_balance_check")),
                "supports_operation_status_yaml": bool(capabilities.get("supports_operation_status")),
                "supports_wallet_operation_yaml": bool(capabilities.get("supports_wallet_operation")),
                "supports_round_close_yaml": bool(capabilities.get("supports_round_close")),
                "supports_reversal_yaml": bool(capabilities.get("supports_reversal")),
                "timeout_connect_ms_yaml": self._int_value(timeouts.get("connect_ms")),
                "timeout_read_ms_yaml": self._int_value(timeouts.get("read_ms")),
                "retry_max_attempts_yaml": self._int_value(retries.get("max_attempts")),
                "retry_on_yaml": self._format_list(retries.get("retry_on")),
                "require_currency_yaml": bool(validations.get("require_currency")),
                "require_hash_yaml": bool(validations.get("require_hash")),
                "require_remote_player_id_yaml": bool(validations.get("require_remote_player_id")),
                "require_operation_id_yaml": bool(validations.get("require_operation_id")),
                "require_round_id_for_stake_yaml": bool(validations.get("require_round_id_for_stake")),
                "require_round_id_for_payout_yaml": bool(validations.get("require_round_id_for_payout")),
                "amount_min_yaml": self._float_value(validations.get("amount_min")),
                "transaction_id_max_length_yaml": self._int_value(validations.get("transaction_id_max_length")),
                "status_mapping_yaml": self._format_yaml_block(status_mapping),
                "error_mapping_yaml": self._format_yaml_block(error_mapping),
                "provider_metadata_yaml": self._format_yaml_block(provider_metadata),
                "operation_names_yaml": self._format_operation_names(operations),
                "operations_detail_yaml": self._format_operations(operations),
            }
        )

    @staticmethod
    def _text_value(value):
        return False if value in (None, "") else str(value)

    @staticmethod
    def _int_value(value):
        try:
            return int(value)
        except Exception:
            return 0

    @staticmethod
    def _float_value(value):
        try:
            return float(value)
        except Exception:
            return 0.0

    @staticmethod
    def _format_list(value):
        if not value:
            return False
        if isinstance(value, (list, tuple, set)):
            return ", ".join(str(item) for item in value)
        return str(value)

    @staticmethod
    def _format_yaml_block(value):
        if not value:
            return False
        if yaml is not None:
            return yaml.safe_dump(value, allow_unicode=True, sort_keys=False)
        return str(value)

    @staticmethod
    def _format_operation_names(operations):
        if not isinstance(operations, dict) or not operations:
            return False
        return ", ".join(sorted(str(key) for key in operations.keys()))

    def _format_operations(self, operations):
        if not isinstance(operations, dict) or not operations:
            return False

        sections = []
        for operation_name, definition in operations.items():
            if not isinstance(definition, dict):
                sections.append(f"{operation_name}\n  definition: {definition}")
                continue

            lines = [str(operation_name)]
            for key in (
                "description",
                "http_method",
                "endpoint_path",
                "request_format",
                "response_format",
                "provider_method",
                "provider_path",
                "standard_method",
                "standard_path",
            ):
                value = definition.get(key)
                if value not in (None, ""):
                    lines.append(f"  {key}: {value}")

            for key in (
                "inbound",
                "forward",
                "request_mapping",
                "response_mapping",
                "standard_defaults",
                "operation_type_mapping",
                "result_mapping",
                "request_mappings",
                "response_mappings",
            ):
                value = definition.get(key)
                if value:
                    lines.append(f"  {key}:")
                    lines.extend(self._indent_block(value, 4))

            sections.append("\n".join(lines))
        return "\n\n".join(sections)

    @staticmethod
    def _indent_block(value, spaces):
        prefix = " " * spaces
        if yaml is not None:
            formatted = yaml.safe_dump(value, allow_unicode=True, sort_keys=False).rstrip()
        else:
            formatted = str(value)
        return [f"{prefix}{line}" for line in formatted.splitlines()]

    def action_validate_yaml(self):
        for record in self:
            self._service().validate_record(record)
        return self._reload_notification(_("Validacion YAML completada."))

    def action_write_to_disk(self):
        for record in self:
            self._service().write_record(record, replace=False)
        return self._reload_notification(_("Configuracion guardada en disco."))

    def action_overwrite_file(self):
        for record in self:
            self._service().write_record(record, replace=True)
        return self._reload_notification(_("Archivo sobrescrito correctamente."))

    @api.model
    def action_sync_from_disk(self):
        result = self._service().sync_from_disk()
        return self._reload_notification(
            _("Sincronizacion completada. Procesados: %(processed)s, creados: %(created)s, actualizados: %(updated)s, errores: %(errors)s")
            % result
        )

    def action_create_template(self):
        for record in self:
            template = self._service().build_template_yaml(record.provider_code or "new_provider")
            if not record.yaml_content:
                record.yaml_content = template
            if not record.file_name:
                record.file_name = f"{record.provider_code or 'new_provider'}.yaml"
            if not record.name:
                record.name = record.provider_code or _("Nuevo proveedor")
        return self._reload_notification(_("Plantilla YAML cargada."))

    @staticmethod
    def _reload_notification(message):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Casino API Gateway"),
                "message": message,
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.client", "tag": "reload"},
            },
        }
