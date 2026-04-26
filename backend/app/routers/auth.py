import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pydantic import BaseModel

from app.core.config import settings
from app.core.database import init_db, create_user, get_user_by_email, get_user_by_id
from app.core.rate_limiter import limiter

router = APIRouter(prefix="/api/auth", tags=["auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")

init_db()
SUBSCRIPTION_PLAN_MONTHLY = "zenalys-monthly-799"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    salt, stored_hash = hashed_password.split("$")
    key = hashlib.pbkdf2_hmac("sha256", plain_password.encode(), salt.encode(), 100000)
    return key.hex() == stored_hash


def get_password_hash(password: str) -> str:
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000)
    return f"{salt}${key.hex()}"


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(
        to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: Optional[str]
    role: str
    is_active: bool
    subscription_plan: Optional[str] = None
    subscription_status: Optional[str] = None
    subscription_started_at: Optional[str] = None
    subscription_expires_at: Optional[str] = None
    created_at: Optional[str]


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class RegisterRequest(BaseModel):
    email: str
    password: str
    full_name: Optional[str] = None
    plan_code: str


class RegisterResponse(BaseModel):
    message: str
    requires_payment: bool
    user: UserResponse


async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserResponse:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = get_user_by_id(int(user_id))
    if user is None:
        raise credentials_exception
    return UserResponse(
        id=user["id"],
        email=user["email"],
        full_name=user.get("full_name"),
        role=user.get("role", "user"),
        is_active=bool(user.get("is_active", True)),
        subscription_plan=user.get("subscription_plan"),
        subscription_status=user.get("subscription_status"),
        subscription_started_at=user.get("subscription_started_at"),
        subscription_expires_at=user.get("subscription_expires_at"),
        created_at=user["created_at"],
    )


@router.post("/register", response_model=RegisterResponse)
@limiter.limit("3/minute")
async def register(request: Request, req: RegisterRequest):
    existing = get_user_by_email(req.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    if req.plan_code != SUBSCRIPTION_PLAN_MONTHLY:
        raise HTTPException(status_code=400, detail="Invalid subscription plan selected")

    password_hash = get_password_hash(req.password)
    user_id = create_user(
        req.email,
        password_hash,
        req.full_name,
        subscription_plan=req.plan_code,
        subscription_status="pending_payment",
    )
    if user_id is None:
        raise HTTPException(status_code=500, detail="Failed to create user")
    user = get_user_by_id(int(user_id))
    if user is None:
        raise HTTPException(status_code=500, detail="Failed to create user")

    return RegisterResponse(
        message="Account created. Complete subscription payment before signing in.",
        requires_payment=True,
        user=UserResponse(
            id=user["id"],
            email=user["email"],
            full_name=user.get("full_name"),
            role=user.get("role", "user"),
            is_active=bool(user.get("is_active", True)),
            subscription_plan=user.get("subscription_plan"),
            subscription_status=user.get("subscription_status"),
            subscription_started_at=user.get("subscription_started_at"),
            subscription_expires_at=user.get("subscription_expires_at"),
            created_at=user["created_at"],
        ),
    )


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    user = get_user_by_email(form_data.username)
    if not user or not verify_password(form_data.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not bool(user.get("is_active", True)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is inactive",
        )
    if user.get("subscription_status") != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Subscription inactive. Choose a plan on /pricing and activate payment before signing in.",
        )

    access_token = create_access_token(data={"sub": str(user["id"])})
    return TokenResponse(
        access_token=access_token,
        user=UserResponse(
            id=user["id"],
            email=user["email"],
            full_name=user["full_name"],
            role=user.get("role", "user"),
            is_active=bool(user.get("is_active", True)),
            subscription_plan=user.get("subscription_plan"),
            subscription_status=user.get("subscription_status"),
            subscription_started_at=user.get("subscription_started_at"),
            subscription_expires_at=user.get("subscription_expires_at"),
            created_at=user["created_at"],
        ),
    )


@router.get("/me", response_model=UserResponse)
async def me(current_user: UserResponse = Depends(get_current_user)):
    return current_user


@router.post("/logout")
async def logout():
    return {"message": "Logged out successfully"}
