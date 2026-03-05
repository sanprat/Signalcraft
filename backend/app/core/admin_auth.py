"""
Admin authentication and authorization helpers.
Provides role-based access control for admin panel.
"""

from functools import wraps
from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from jose import jwt
from datetime import datetime

from app.core.config import settings
from app.core.database import get_user_by_id, log_admin_action


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")


class AdminUser:
    """Represents an authenticated admin user."""
    
    def __init__(self, user_id: int, email: str, full_name: str = None, role: str = "user"):
        self.id = user_id
        self.email = email
        self.full_name = full_name
        self.role = role
    
    @property
    def is_admin(self) -> bool:
        return self.role == "admin"
    
    @property
    def is_active(self) -> bool:
        return True  # Can be extended to check is_active flag


async def get_current_admin_user(token: str = Depends(oauth2_scheme)) -> AdminUser:
    """
    Get current authenticated admin user from JWT token.
    Raises 403 if user is not an admin.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(
            token, 
            settings.JWT_SECRET_KEY, 
            algorithms=[settings.JWT_ALGORITHM]
        )
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except jwt.JWTError:
        raise credentials_exception
    
    user = get_user_by_id(int(user_id))
    if user is None:
        raise credentials_exception
    
    admin_user = AdminUser(
        user_id=user["id"],
        email=user["email"],
        full_name=user.get("full_name"),
        role=user.get("role", "user")
    )
    
    if not admin_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    return admin_user


def require_admin():
    """
    Dependency that requires admin authentication.
    Use this to protect admin-only endpoints.
    """
    return Depends(get_current_admin_user)
