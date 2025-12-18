# bdc_conecta (Odoo 17)

Scaffold module to integrate Banco de Comercio / BDC Conecta endpoints.

## What you get
- Settings (Company): Base URL, auth settings, client id/secret.
- Endpoint registry (`bdc.endpoint`) to maintain API methods and paths.
- OpenAPI importer wizard: paste an OpenAPI JSON URL to automatically populate endpoints.
- Test Console wizard: pick an endpoint, send params/body, and review response.
- Request logging (`bdc.request.log`) with headers/payloads and durations.

## Typical setup
1. Install the module.
2. Go to **Settings → BDC Conecta** and set:
   - Base URL (Sandbox)
   - Client ID / Client Secret (if required by BDC)
3. Import endpoints:
   - **BDC Conecta → Configuration → Import OpenAPI**
   - Paste the OpenAPI JSON URL from Swagger UI (Download JSON / openapi.json).
4. Use **BDC Conecta → Operations → Test Console** to execute calls.

## Notes
- The token refresh cron is a placeholder. Implement token acquisition according to BDC's Swagger definition.
- Extend `bdc.api.service` with business flows (payments, reconciliation, etc.) once the exact endpoints are confirmed.
