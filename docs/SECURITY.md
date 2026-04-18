# Security and Authentication

This document outlines the security architecture and authentication mechanisms introduced in the **Fondation** phase.

## API Authentication (Opt-in)

The Prediction Wallet API uses a header-based API Key authentication system. It is designed to be **opt-in**: if no API keys are configured in the environment, the API defaults to a "Super Admin" mode where all requests are permitted.

### Role-Based Access Control (RBAC)

Three roles are supported:

| Role | Environment Variable | Permissions |
|------|----------------------|-------------|
| **ADMIN** | `API_KEY_ADMIN` | Full access to all endpoints (Read + Write + Execute). |
| **TRADER** | `API_KEY_TRADER` | Access to research, idea book, and trade execution. |
| **VIEWER** | `API_KEY_VIEWER` | Read-only access to portfolio, positions, and analytics. |

### Configuration

Add the following to your `.env` file to enable authentication:

```env
# API Keys (leave empty to disable auth)
API_KEY_ADMIN=your-admin-secret-key
API_KEY_TRADER=your-trader-secret-key
API_KEY_VIEWER=your-viewer-secret-key

# CORS (comma-separated origins)
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:8000
```

### Usage

#### API Headers
All authenticated requests must include the `X-API-KEY` header:
```bash
curl -H "X-API-KEY: your-admin-secret-key" http://localhost:8000/api/portfolio
```

#### Web UI
To use the Web UI with authentication enabled, store your API key in the browser's `localStorage` under the key `prediction_wallet_api_key`. You can do this via the browser console:
```javascript
localStorage.setItem('prediction_wallet_api_key', 'your-admin-secret-key');
location.reload();
```

## Observability

The platform includes structured access logging. Every request is logged in JSON format to `stdout`:

```json
{"type": "access", "method": "GET", "path": "/api/portfolio", "status": 200, "duration_ms": 12.45, "client": "127.0.0.1"}
```

If OpenTelemetry is enabled (`OTEL_EXPORTER_OTLP_ENDPOINT` or `OTEL_CONSOLE_EXPORTER=1`), requests are also traced as server spans.

## CORS Policy

By default, the API allows all origins (`*`) if `ALLOWED_ORIGINS` is not set or set to `*`. In production, it is highly recommended to restrict this to your specific frontend domain.

## Secrets Management

- **No Secrets in Code**: All sensitive keys (AI providers, API keys) are managed via `pydantic-settings` and `.env` files.
- **Redaction**: Future updates will include automatic redaction of secrets in logs and traces.
