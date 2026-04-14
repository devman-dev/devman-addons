from __future__ import annotations

import os
import tempfile
from pathlib import Path

from odoo import _, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None


class CasinoApiProviderConfigService(models.AbstractModel):
    _name = "casino.api.provider.config.service"
    _description = "Casino Provider Config Service"

    _CONFIG_PARAM = "casino_api_gateway.providers_yaml_directory"
    _ENV_PARAM = "CASINO_PROVIDER_YAML_DIR"

    def _ensure_manager(self):
        if not self.env.user.has_group("casino_api_gateway.group_provider_config_manager") and not self.env.user.has_group("base.group_system"):
            raise AccessError(_("No tiene permisos para administrar configuraciones YAML."))

    def _ensure_yaml(self):
        if yaml is None:
            raise UserError(_("PyYAML no esta disponible en el entorno de Odoo."))

    def _directory_candidates(self):
        icp = self.env["ir.config_parameter"].sudo()
        configured = icp.get_param(self._CONFIG_PARAM)
        env_value = os.getenv(self._ENV_PARAM)
        return [
            configured,
            env_value,
            r"D:\proyectos\odoo\casino\casino_api_traductor\config\providers",
            "/opt/casino_api_traductor/config/providers",
        ]

    def get_yaml_directory(self, create=False) -> Path:
        for candidate in self._directory_candidates():
            if candidate and Path(candidate).is_dir():
                return Path(candidate)
        for candidate in self._directory_candidates():
            if candidate:
                path = Path(candidate)
                if create:
                    path.mkdir(parents=True, exist_ok=True)
                    return path
                return path
        raise UserError(_("No hay directorio de YAML configurado. Configure el parametro %s.") % self._CONFIG_PARAM)

    def build_template_yaml(self, provider_code: str) -> str:
        provider_code = provider_code or "new_provider"
        return "\n".join(
            [
                f"provider_code: {provider_code}",
                f"provider_name: {provider_code}",
                "provider_type: gaming_wallet",
                "base_url: https://provider.example.com",
                "authentication:",
                "  mode: session_token",
                "operations:",
                "  session.authorize:",
                "    http_method: POST",
                "    endpoint_path: /session.authorize",
                "    request_mapping:",
                "      session_token: token",
                "    response_mapping:",
                "      session_token: token",
                "",
            ]
        )

    def validate_yaml_content(self, yaml_content: str):
        self._ensure_yaml()
        if not yaml_content or not yaml_content.strip():
            raise ValidationError(_("El contenido YAML no puede estar vacio."))
        try:
            parsed = yaml.safe_load(yaml_content) or {}
        except Exception as exc:
            raise ValidationError(_("Error de parseo YAML: %s") % exc) from exc

        if not isinstance(parsed, dict):
            raise ValidationError(_("La raiz del YAML debe ser un objeto."))

        provider_code = parsed.get("provider_code") or parsed.get("provider_id") or ((parsed.get("provider") or {}).get("code"))
        if not provider_code:
            raise ValidationError(_("El YAML debe incluir provider_code o provider.code."))

        operations = parsed.get("operations") or parsed.get("endpoints")
        if not isinstance(operations, dict) or not operations:
            raise ValidationError(_("El YAML debe incluir operations o endpoints con al menos una operacion."))

        if not parsed.get("authentication"):
            raise ValidationError(_("El YAML debe incluir el bloque authentication."))

        if not parsed.get("base_url"):
            raise ValidationError(_("El YAML debe incluir base_url."))

        return parsed, str(provider_code)

    def validate_record(self, record):
        _, detected_provider_code = self.validate_yaml_content(record.yaml_content)
        if record.provider_code and record.provider_code != detected_provider_code:
            raise ValidationError(_("El provider_code del registro no coincide con el provider_code del YAML."))
        record.sudo().write(
            {
                "provider_code": detected_provider_code,
                "name": record.name or detected_provider_code,
                "file_name": record.file_name or f"{detected_provider_code}.yaml",
                "last_validation_status": "valid",
                "last_validation_message": _("Validacion correcta."),
            }
        )
        return detected_provider_code

    def sync_from_disk(self):
        self._ensure_manager()
        directory = self.get_yaml_directory(create=False)
        if not directory.exists():
            raise UserError(_("El directorio de YAML no existe: %s") % directory)

        ProviderConfig = self.env["casino.provider.config"].sudo()
        processed = created = updated = errors = 0
        for file_path in sorted(directory.glob("*.y*ml")):
            processed += 1
            yaml_content = file_path.read_text(encoding="utf-8")
            try:
                _, provider_code = self.validate_yaml_content(yaml_content)
                record = ProviderConfig.search([("provider_code", "=", provider_code)], limit=1)
                values = {
                    "name": provider_code,
                    "provider_code": provider_code,
                    "file_name": file_path.name,
                    "file_path": str(file_path),
                    "yaml_content": yaml_content,
                    "loaded_from_disk": True,
                    "last_loaded_at": fields.Datetime.now(),
                    "last_validation_status": "valid",
                    "last_validation_message": _("Cargado desde disco correctamente."),
                }
                if record:
                    record.write(values)
                    updated += 1
                else:
                    ProviderConfig.create(values)
                    created += 1
            except Exception as exc:
                errors += 1
                if not ProviderConfig.search([("file_name", "=", file_path.name)], limit=1):
                    ProviderConfig.create(
                        {
                            "name": file_path.stem,
                            "provider_code": file_path.stem,
                            "file_name": file_path.name,
                            "file_path": str(file_path),
                            "yaml_content": yaml_content,
                            "loaded_from_disk": True,
                            "last_loaded_at": fields.Datetime.now(),
                            "last_validation_status": "invalid",
                            "last_validation_message": str(exc),
                        }
                    )
        return {"processed": processed, "created": created, "updated": updated, "errors": errors}

    def write_record(self, record, replace=False):
        self._ensure_manager()
        self.validate_record(record)
        directory = self.get_yaml_directory(create=True)
        target_path = self._safe_target_path(directory, record.file_name)
        if target_path.exists() and not replace and record.file_path and Path(record.file_path) != target_path:
            raise UserError(_("Ya existe otro archivo con ese nombre. Use Sobrescribir archivo."))
        if target_path.exists() and not replace and not record.file_path:
            raise UserError(_("El archivo ya existe en disco. Use Sobrescribir archivo."))
        self._atomic_write(target_path, record.yaml_content)
        record.sudo().write(
            {
                "file_path": str(target_path),
                "last_written_at": fields.Datetime.now(),
                "loaded_from_disk": True,
                "version": (record.version or 0) + 1,
                "last_validation_status": "valid",
                "last_validation_message": _("Archivo escrito correctamente."),
            }
        )
        return target_path

    def upload_yaml(self, provider_code: str, file_name: str, yaml_content: str, replace=False):
        self._ensure_manager()
        ProviderConfig = self.env["casino.provider.config"].sudo()
        record = ProviderConfig.search([("provider_code", "=", provider_code)], limit=1)
        if record and not replace:
            raise ValidationError(_("Ya existe una configuracion para provider_code=%s.") % provider_code)
        values = {
            "name": provider_code,
            "provider_code": provider_code,
            "file_name": file_name or f"{provider_code}.yaml",
            "yaml_content": yaml_content,
        }
        if record:
            record.write(values)
        else:
            record = ProviderConfig.create(values)
        self.write_record(record, replace=True)
        return record

    def replace_yaml(self, provider_code: str, yaml_content: str):
        self._ensure_manager()
        record = self.env["casino.provider.config"].sudo().search([("provider_code", "=", provider_code)], limit=1)
        if not record:
            raise ValidationError(_("No existe una configuracion para provider_code=%s.") % provider_code)
        record.write({"yaml_content": yaml_content})
        self.write_record(record, replace=True)
        return record

    def serialize_record(self, record):
        return {
            "id": record.id,
            "name": record.name,
            "provider_code": record.provider_code,
            "file_name": record.file_name,
            "file_path": record.file_path,
            "yaml_content": record.yaml_content,
            "is_active": bool(record.is_active),
            "version": record.version,
            "loaded_from_disk": bool(record.loaded_from_disk),
            "last_loaded_at": fields.Datetime.to_string(record.last_loaded_at) if record.last_loaded_at else None,
            "last_written_at": fields.Datetime.to_string(record.last_written_at) if record.last_written_at else None,
            "last_validation_status": record.last_validation_status,
            "last_validation_message": record.last_validation_message,
            "notes": record.notes,
        }

    @staticmethod
    def _safe_target_path(directory: Path, file_name: str) -> Path:
        target = (directory / file_name).resolve()
        directory_resolved = directory.resolve()
        if directory_resolved not in target.parents and target != directory_resolved:
            raise ValidationError(_("Ruta invalida para el archivo YAML."))
        return target

    @staticmethod
    def _atomic_write(target_path: Path, content: str):
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", delete=False, dir=str(target_path.parent), encoding="utf-8") as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)
        os.replace(tmp_path, target_path)
