"""Authentication and RBAC logic for the Prediction Wallet API."""

from __future__ import annotations
from enum import Enum
from fastapi import Header, HTTPException, Depends
from pydantic import BaseModel
from config import API_KEY_ADMIN, API_KEY_TRADER, API_KEY_VIEWER

class Role(str, Enum):
    ADMIN = "admin"
    TRADER = "trader"
    VIEWER = "viewer"

class User(BaseModel):
    role: Role

async def get_current_user(x_api_key: str | None = Header(None)) -> User:
    # If no keys are configured, everyone is a Super Admin (Opt-in mode)
    if not API_KEY_ADMIN and not API_KEY_TRADER and not API_KEY_VIEWER:
        return User(role=Role.ADMIN)
    
    if not x_api_key:
        raise HTTPException(status_code=401, detail="X-API-KEY header missing")
    
    if API_KEY_ADMIN and x_api_key == API_KEY_ADMIN:
        return User(role=Role.ADMIN)
    if API_KEY_TRADER and x_api_key == API_KEY_TRADER:
        return User(role=Role.TRADER)
    if API_KEY_VIEWER and x_api_key == API_KEY_VIEWER:
        return User(role=Role.VIEWER)
    
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
