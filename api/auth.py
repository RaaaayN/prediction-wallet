"""Authentication and RBAC logic for the Prediction Wallet API."""

from __future__ import annotations
from enum import Enum
from fastapi import Header, HTTPException, Depends
from pydantic import BaseModel
import config

class Role(str, Enum):
    ADMIN = "admin"
    TRADER = "trader"
    VIEWER = "viewer"

class User(BaseModel):
    username: str
    role: Role
    is_service_account: bool = False

async def get_current_user(x_api_key: str | None = Header(None)) -> User:
    # 1. Check for "Opt-in / Super Admin" mode: if no keys are configured
    # we allow all requests as ADMIN for ease of initial setup.
    no_keys_configured = not (config.API_KEY_ADMIN or config.API_KEY_TRADER or config.API_KEY_VIEWER)
    
    if no_keys_configured:
        # Check if DB has any users. If no users in DB either, it's Super Admin mode.
        from db.repository import get_connection
        try:
            with get_connection() as conn:
                # Ensure table exists
                conn.execute("CREATE TABLE IF NOT EXISTS users (username TEXT, api_key TEXT, role TEXT, is_active INTEGER, is_service_account INTEGER)")
                user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            if user_count == 0:
                # print("DEBUG: Auth in Super Admin mode (no keys in config, no users in DB)")
                return User(username="super_admin", role=Role.ADMIN)
        except Exception as e:
            # print(f"DEBUG: Auth error checking users, defaulting to Super Admin: {e}")
            return User(username="super_admin", role=Role.ADMIN)

    if not x_api_key:
        # print("DEBUG: Auth failed - X-API-KEY header missing and not in Super Admin mode")
        raise HTTPException(status_code=401, detail="X-API-KEY header missing")
    
    # 2. Check Database for persistent users
    from db.repository import get_user_by_api_key
    db_user = get_user_by_api_key(x_api_key)
    if db_user:
        return User(
            username=db_user["username"],
            role=Role(db_user["role"]),
            is_service_account=bool(db_user["is_service_account"])
        )
    
    # 3. Fallback to static config keys (backward compatibility)
    if config.API_KEY_ADMIN and x_api_key == config.API_KEY_ADMIN:
        return User(username="static_admin", role=Role.ADMIN)
    if config.API_KEY_TRADER and x_api_key == config.API_KEY_TRADER:
        return User(username="static_trader", role=Role.TRADER)
    if config.API_KEY_VIEWER and x_api_key == config.API_KEY_VIEWER:
        return User(username="static_viewer", role=Role.VIEWER)
    
    raise HTTPException(status_code=403, detail="Invalid API Key")

def requires_role(required_roles: list[Role]):
    async def role_checker(user: User = Depends(get_current_user)):
        if user.role not in required_roles:
            raise HTTPException(
                status_code=403, 
                detail=f"Insufficient permissions. Required: {[r.value for r in required_roles]}"
            )
        return user
    return role_checker
