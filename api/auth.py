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
    # 1. Fallback to static config keys (highest priority for dev/override)
    if x_api_key:
        if config.API_KEY_ADMIN and x_api_key == config.API_KEY_ADMIN:
            return User(username="static_admin", role=Role.ADMIN)
        if config.API_KEY_TRADER and x_api_key == config.API_KEY_TRADER:
            return User(username="static_trader", role=Role.TRADER)
        if config.API_KEY_VIEWER and x_api_key == config.API_KEY_VIEWER:
            return User(username="static_viewer", role=Role.VIEWER)
        
        # 2. Check Database for persistent users
        from db.repository import get_user_by_api_key
        try:
            db_user = get_user_by_api_key(x_api_key)
        except Exception:
            db_user = None
            
        if db_user:
            return User(
                username=db_user["username"],
                role=Role(db_user["role"]),
                is_service_account=bool(db_user["is_service_account"])
            )

    # 3. Check for "Opt-in / Super Admin" mode: 
    # If no keys are configured in environment, allow all requests as ADMIN.
    no_keys_in_config = not (config.API_KEY_ADMIN or config.API_KEY_TRADER or config.API_KEY_VIEWER)
    if no_keys_in_config:
        return User(username="super_admin", role=Role.ADMIN)

    if not x_api_key:
        raise HTTPException(status_code=401, detail="X-API-KEY header missing")
    
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
