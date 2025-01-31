from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from src.config import security, settings
from src.config.database import get_db_session
from src.models.user import TokenPayload, User


# Use async OAuth2 scheme with proper API prefix
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_STR}/auth/login",
    scopes={
        "me": "Read current user information",
        "users:read": "Read user information",
        "users:write": "Modify user information",
    },
)


async def get_current_user(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    token: Annotated[str, Depends(oauth2_scheme)],
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = security.decode_token(token)
        token_data = TokenPayload(**payload)
    except (JWTError, ValidationError) as e:  # noqa: F821
        raise credentials_exception from e

    user = await session.get(User, token_data.sub)
    if not user:
        raise credentials_exception
    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)]
) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


async def verify_admin_access(
    current_user: Annotated[User, Depends(get_current_active_user)]
) -> User:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    return current_user


# Common dependency types
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
CurrentUser = Annotated[User, Depends(get_current_active_user)]
AdminUser = Annotated[User, Depends(verify_admin_access)]
