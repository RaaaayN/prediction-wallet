# Institutional Security & Compliance

Prediction Wallet is built with a "Security-First" architecture, ensuring that every action is authenticated, every decision is audited, and all sensitive data is protected according to institutional standards.

---

## 🔐 Authentication & Access Control (RBAC)

The platform enforces strict **Role-Based Access Control (RBAC)** across all API and CLI interfaces.

### Role Hierarchy
| Role | Permissions |
|------|-------------|
| **ADMIN** | Full system control, user management, and configuration. |
| **QUANT** | Access to research, backtesting, model promotion, and DVC/MLflow. |
| **TRADER** | Access to execution, OMS, and rebalancing cycles. |
| **VIEWER** | Read-only access to analytics, reports, and portfolio state. |

### Authentication Mechanisms
- **Bearer Tokens**: API requests require an `X-API-KEY` header validated against the persistent PostgreSQL/SQLite `users` table.
- **Service Accounts**: Dedicated identities for automated CI/CD and monitoring agents.
- **RBAC Enforcement**: Middleware validates role requirements for every endpoint (e.g., `RequiresRole("QUANT")`).

---

## 📝 Immutable Audit Trails

Every action within the platform leaves a permanent, non-repudiable trace.

- **Decision Traces**: Every governed cycle stage (Observe, Decide, Validate, Execute, Audit) is logged with its full payload and justification.
- **Order Events**: Every state transition in the OMS (Pending → Filled) is recorded.
- **MLflow Lineage**: Every research experiment is linked to the specific user and code version that executed it.
- **Access Logs**: All API requests are logged in structured JSON format, including client IP, duration, and status.

---

## 🛡️ Secrets & Data Privacy

We follow industry best practices for protecting sensitive information:

- **Zero-Secret Repository**: No API keys or credentials are ever committed to the repository. We use `.env` files and environment variables managed via `Pydantic Settings`.
- **Data Encryption**: Recommended use of encrypted volumes for **Parquet Gold** data and database backups.
- **PII Protection**: The system is designed to handle only financial and operational data; no Personal Identifiable Information (PII) of clients is stored in the core engine.

---

## 🏛️ Compliance Framework (In Spirit)

While this is an open-source project, the architecture is designed to align with the spirit of institutional compliance:

- **SOC2 Alignment**: Focused on Security, Availability, and Confidentiality through rigorous logging and RBAC.
- **Basel III / FRTB**: Risk models and tail-risk reporting are designed to meet modern banking regulatory standards.
- **Auditability**: The combination of **DVC**, **MLflow**, and **Event Sourcing** provides a "Compliance-Ready" audit trail for regulators.
