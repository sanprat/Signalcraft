"""
Admin panel API endpoints.
All endpoints require admin authentication.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from app.core.admin_auth import require_admin, AdminUser
from app.core.database import (
    get_all_users,
    get_user_by_id,
    update_user,
    delete_user,
    get_admin_logs,
    get_user_stats,
    log_admin_action,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ── Response Models ────────────────────────────────────────────────────────────

class UserResponse(BaseModel):
    id: int
    email: str
    full_name: Optional[str]
    role: str
    is_active: bool
    created_at: Optional[str]


class AdminStatsResponse(BaseModel):
    total_users: int
    active_users: int
    admin_users: int
    inactive_users: int
    total_strategies: int
    live_strategies: int


class AdminLogResponse(BaseModel):
    id: int
    admin_id: int
    action: str
    target_user_id: Optional[int]
    details: Optional[str]
    created_at: str


class UpdateUserRequest(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


# ── Helper Functions ──────────────────────────────────────────────────────────

def get_user_from_db(user_id: int) -> Optional[dict]:
    """Get user by ID including role and is_active fields."""
    return get_user_by_id(user_id)


def get_all_users_from_db(limit: int = 100, offset: int = 0) -> List[dict]:
    """Get all users with pagination."""
    return get_all_users(limit, offset)


def get_admin_logs_from_db(limit: int = 50) -> List[dict]:
    """Get recent admin logs."""
    return get_admin_logs(limit)


# ── Admin Endpoints ───────────────────────────────────────────────────────────

@router.get("/stats", response_model=AdminStatsResponse)
async def get_admin_stats(current_admin: AdminUser = require_admin()):
    """Get platform statistics for admin dashboard."""
    stats = get_user_stats()
    
    # Strategy stats (placeholder - implement when strategy table exists)
    stats["total_strategies"] = 0
    stats["live_strategies"] = 0
    
    return AdminStatsResponse(**stats)


@router.get("/users", response_model=List[UserResponse])
async def list_users(
    limit: int = 100,
    offset: int = 0,
    current_admin: AdminUser = require_admin()
):
    """List all users with pagination."""
    users = get_all_users_from_db(limit, offset)
    return [UserResponse(**user) for user in users]


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    current_admin: AdminUser = require_admin()
):
    """Get details of a specific user."""
    user = get_user_from_db(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(**user)


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    update_data: UpdateUserRequest,
    current_admin: AdminUser = require_admin()
):
    """
    Update user details (role, active status, name).
    Logs the action to admin audit log.
    """
    user = get_user_from_db(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prevent admin from modifying their own role/status
    if user_id == current_admin.id:
        if update_data.role or update_data.is_active is not None:
            raise HTTPException(
                status_code=403, 
                detail="Cannot modify your own role or status"
            )
    
    # Update user
    update_fields = {}
    if update_data.full_name is not None:
        update_fields["full_name"] = update_data.full_name
    if update_data.role is not None:
        update_fields["role"] = update_data.role
    if update_data.is_active is not None:
        update_fields["is_active"] = update_data.is_active
    
    if update_fields:
        success = update_user(user_id, **update_fields)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update user")
        
        # Log admin action
        log_admin_action(
            admin_id=current_admin.id,
            action="USER_UPDATED",
            target_user_id=user_id,
            details=f"Updated: {update_data.dict(exclude_none=True)}"
        )
    
    # Return updated user
    updated_user = get_user_from_db(user_id)
    return UserResponse(**updated_user)


@router.delete("/users/{user_id}")
async def remove_user_endpoint(
    user_id: int,
    current_admin: AdminUser = require_admin()
):
    """
    Delete a user account.
    Logs the action to admin audit log.
    """
    user = get_user_from_db(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prevent admin from deleting themselves
    if user_id == current_admin.id:
        raise HTTPException(
            status_code=403, 
            detail="Cannot delete your own account"
        )
    
    # Delete user
    success = delete_user(user_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete user")
    
    # Log admin action
    log_admin_action(
        admin_id=current_admin.id,
        action="USER_DELETED",
        target_user_id=user_id,
        details=f"Deleted user: {user['email']}"
    )
    
    return {"message": "User deleted successfully"}


@router.get("/logs", response_model=List[AdminLogResponse])
async def get_admin_logs(
    limit: int = 50,
    current_admin: AdminUser = require_admin()
):
    """Get recent admin activity logs."""
    logs = get_admin_logs_from_db(limit)
    return [AdminLogResponse(**log) for log in logs]
