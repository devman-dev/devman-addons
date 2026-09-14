import hashlib
import logging

from odoo import http
from odoo.http import content_disposition, request


_logger = logging.getLogger(__name__)


class PfGatewayTraceabilityReportController(http.Controller):
    @http.route("/pagoflex/traceability/<string:audit_uuid>/xlsx", type="http", auth="user", methods=["GET"])
    def download_xlsx(self, audit_uuid, token=None, **kwargs):
        audit = request.env["pf.gateway.traceability.report.audit"].search([("uuid", "=", audit_uuid)], limit=1)
        if not audit:
            return request.not_found()
        try:
            request.env.cr.execute(
                "SELECT pg_advisory_xact_lock(hashtext(%s), %s)",
                ["pagoflex_traceability_report", request.env.user.id],
            )
            request.env.cr.execute("SELECT pg_advisory_xact_lock(%s)", [audit.id])
            audit.check_download_access(token)
            audit.add_event("started")
            with request.env.cr.savepoint():
                content, row_count = request.env["pf.gateway.chained.traceability.report.service"].generate_xlsx(audit)
            digest = hashlib.sha256(content).hexdigest()
            audit.add_event("completed", row_count=row_count, file_size=len(content), file_hash=digest)
            filename = "trazabilidad_cuit_%s_%s.xlsx" % (
                audit.requested_at.strftime("%Y%m%d_%H%M%S"), audit.uuid
            )
            headers = [
                ("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
                ("Content-Disposition", content_disposition(filename)),
                ("Content-Length", str(len(content))),
                ("Cache-Control", "no-store"),
                ("X-Content-Type-Options", "nosniff"),
            ]
            return request.make_response(content, headers)
        except Exception as exc:
            _logger.exception("Error generating traceability report audit_uuid=%s", audit_uuid)
            audit.add_event("failed", message=str(exc)[:250])
            return request.make_response("No se pudo generar el reporte. Referencia: %s" % audit_uuid, status=500)
