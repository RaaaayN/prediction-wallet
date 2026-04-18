# Security and Authentication

This document outlines the security architecture and authentication mechanisms introduced in the **Fondation** phase.

## API Authentication

The Prediction Wallet API uses a header-based authentication system. It supports both **Persistent DB-backed Users** and **Static Environment Keys**.

### User Management (Persistent)

The system maintains a `users` table in the database, allowing for multiple users and service accounts.

- **Storage**: Keys are stored in the `users` table.
- **Service Accounts**: Users can be flagged as `is_service_account` for programmatic access.
- **Bootstrapping**: The `python main.py init` command prompts to create an initial Admin user if the database is empty.

### Role-Based Access Control (RBAC)

Three roles are supported:

| Role | Permissions |
|------|-------------|
| **ADMIN** | Full access to all endpoints (Read + Write + Execute). |
| **TRADER** | Access to research, idea book, and trade execution. |
| **VIEWER** | Read-only access to portfolio, positions, and analytics. |

### Configuration (Backward Compatibility)

Static API keys in the `.env` file are still supported for backward compatibility and simple deployments:

```env
# Static API Keys (fallback if not found in DB)
API_KEY_ADMIN=your-admin-secret-key
API_KEY_TRADER=your-trader-secret-key
API_KEY_VIEWER=your-viewer-secret-key
```

If no keys are configured in the environment AND the database has no users, the API defaults to an **"Opt-in mode"** where all requests are permitted with Super Admin privileges.

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
