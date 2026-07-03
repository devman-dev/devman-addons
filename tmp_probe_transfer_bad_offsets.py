from odoo.exceptions import UserError

model = env["pf.gateway.transfer"]
latest = model.search([], order="source_updated_at desc", limit=1).source_updated_at
updated_since = latest.isoformat() if latest else None
for offset in range(45, 55):
    try:
        payload = model._gateway_request_json(
            "GET",
            "/admin/gateway/transfers",
            params={"limit": 1, "offset": offset, "updated_since": updated_since},
        )
        items = payload.get("items") or []
        if items:
            item = items[0]
            print("OK", offset, "id", item.get("id"), "origin", item.get("origin_id"), "connector", item.get("connector_id"), "updated", item.get("updated_at"))
        else:
            print("OK", offset, "empty")
    except UserError as exc:
        print("FAIL", offset, exc)
