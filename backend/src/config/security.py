import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from src.config import settings
from src.deps import get_db_session
from src.models.user import User

logger = logging.getLogger(__name__)

# Security configuration
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_STR}/auth/login",
    scopes={
        "me": "Read information about the current user",
        "admin": "Admin privileges",
    },
)

pwd_context = CryptContext(
    schemes=["argon2", "bcrypt"],
    deprecated="auto",
    argon2__memory_cost=10240,
    argon2__parallelism=8,
)


def create_access_token(
    subject: str, expires_delta: Optional[timedelta] = None, scopes: list[str] = []
) -> str:
    """Create JWT with proper security claims and validation"""
    now = datetime.now(timezone.utc)
    expire = now + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRES_MINUTES)
    )

    payload = {
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "iat": now,
        "exp": expire,
        "sub": str(subject),
        "scp": scopes,
        "jti": os.urandom(16).hex(),
    }

    try:
        return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    except Exception as e:
        logger.error(f"Token creation error: {str(e)}")
        raise


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: AsyncSession = Depends(get_db_session),
) -> User:
    """Dependency for authenticated users with token validation"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            audience=settings.JWT_AUDIENCE,
            issuer=settings.JWT_ISSUER,
        )
        user_id: str = payload.get("sub")
        if not user_id:
            raise credentials_exception
    except (JWTError, ValidationError) as e:
        logger.warning(f"JWT validation failed: {str(e)}")
        raise credentials_exception

    user = await session.get(User, user_id)
    if not user or not user.is_active:
        logger.warning(f"Invalid user ID in token: {user_id}")
        raise credentials_exception

    return user


def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    Validates password against required criteria:
    - 8-30 characters
    - At least 1 uppercase letter
    - At least 1 lowercase letter
    - At least 1 number
    - At least 1 special character
    """
    if len(password) < 8 or len(password) > 30:
        return False, "Password must be between 8 and 30 characters"

    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter"

    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter"

    if not re.search(r"\d", password):
        return False, "Password must contain at least one number"

    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False, "Password must contain at least one special character"

    return True, "Password is valid"


def verify_and_update_password(
    plain_password: str, hashed_password: str
) -> tuple[bool, str]:
    """Verify password and return (valid, new_hash) tuple"""
    return pwd_context.verify_and_update(plain_password, hashed_password)
