from datetime import timedelta
from typing import Annotated, Any

import jwt
from fastapi import (APIRouter, BackgroundTasks, Depends, Header,
                     HTTPException, status)
from fastapi.security import OAuth2PasswordRequestForm
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError
from src import crud
from src.config import security
from src.deps import SessionDep, get_current_active_superuser
from src.models.user import (EmailRequestBody, NewPassword, Token,
                             TokenPayload, User, UserCreate, UserLogin,
                             UserPublic, UserRegister, UserUpdate,
                             UserWithToken)

from ..config.security import get_password_hash, verify_refresh_token
from ..config.settings import settings
from ..deps import CurrentUser
from ..utils.email import send_verification_email

router = APIRouter()

ACCESS_TOKEN_EXPIRES_MINUTES = settings.ACCESS_TOKEN_EXPIRES_MINUTES
REFRESH_TOKEN_EXPIRES_DAYS = settings.REFRESH_TOKEN_EXPIRES_DAYS


# Register New User #######################################################################################
@router.post(
    "/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED
)
async def register_user(
    session: SessionDep, user_in: UserRegister, background_tasks: BackgroundTasks
) -> UserPublic:
    # Check if user already exists
    user = crud.get_user_by_email(session=session, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists",
        )
    # Validate user data
    user_create = UserCreate.model_validate(user_in)
    # Create new user
    user = crud.create_user(session=session, user_create=user_create)
    # Generate a verification token
    verification_token = security.create_token(
        user.id, expires_delta=timedelta(hours=1)
    )
    verification_link = (
        f"{settings.FRONTEND_URL}/verify-email?token={verification_token}"
    )

    # Send verification link via email
    background_tasks.add_task(
        send_verification_email, email=user.email, verification_link=verification_link
    )
    return user


# Register New User With Superuser #########################################################################
@router.post(
    "/create",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UserPublic,
    status_code=status.HTTP_201_CREATED,
)
async def super_create_user(
    *, session: SessionDep, user_in: UserCreate, background_tasks: BackgroundTasks
) -> UserPublic:
    # Check if user already exists
    user = crud.get_user_by_email(session=session, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists",
        )
    # Validate user data
    user_create = UserCreate.model_validate(user_in)
    # Create new user
    user = crud.create_user(session=session, user_create=user_create)
    # Generate a verification token
    verification_token = security.create_token(
        user.id, expires_delta=timedelta(hours=1)
    )
    verification_link = (
        f"{settings.FRONTEND_URL}/verify-email?token={verification_token}"
    )

    # Send verification link via email
    background_tasks.add_task(
        send_verification_email, email=user.email, verification_link=verification_link
    )
    return user


# Verify Email #############################################################################################
@router.get(
    "/verify-email", response_model=UserWithToken, status_code=status.HTTP_200_OK
)
async def verify_email(token: str, session: SessionDep) -> UserWithToken:
    # Verify the token
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except (InvalidTokenError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )
    # Find the user by ID
    user = session.get(User, token_data.sub)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    # check if the user is already verified
    if user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already verified",
        )
    # Update the user's is_verified status
    user_update = UserUpdate(is_verified=True)
    user = crud.update_user(session=session, db_user=user, user_in=user_update)
    user_data = UserPublic.from_orm(user)

    # Generate access and refresh tokens
    access_token = security.create_token(
        user.id,
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRES_MINUTES),
    )
    refresh_token = security.create_token(
        user.id,
        expires_delta=timedelta(days=REFRESH_TOKEN_EXPIRES_DAYS),
    )

    return UserWithToken(
        **user_data.dict(),
        refresh_token=refresh_token,
        access_token=access_token,
        token_type="bearer",
    )


# Log In User ##############################################################################################
@router.post("/login", response_model=UserWithToken, status_code=status.HTTP_200_OK)
async def login(session: SessionDep, login_data: UserLogin) -> UserWithToken:
    user = crud.authenticate(
        session=session, email=login_data.email, password=login_data.password
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect email or password",
        )
    elif not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user"
        )
    elif not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="User is not verified"
        )

    user_data = UserPublic.from_orm(user)

    # Generate access and refresh tokens
    access_token = security.create_token(
        user.id,
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRES_MINUTES),
    )
    refresh_token = security.create_token(
        user.id,
        expires_delta=timedelta(days=REFRESH_TOKEN_EXPIRES_DAYS),
    )
    # Create and return UserWithToken response
    return UserWithToken(
        **user_data.dict(),
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
    )


@router.post("/access-token")
def login_access_token(
    session: SessionDep, form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
) -> Token:
    """
    OAuth2 compatible token login, get an access token for future requests
    """
    user = crud.authenticate(
        session=session, email=form_data.username, password=form_data.password
    )
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    elif not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return Token(
        access_token=security.create_token(
            user.id,
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRES_MINUTES),
        )
    )


# Test Access Token ########################################################################################
@router.post("/login/test-token", response_model=UserPublic)
def test_token(current_user: CurrentUser) -> Any:
    """
    Test access token
    """
    return current_user


# Refresh Access Token ######################################################################################
@router.post(
    "/refresh-token",
)
async def refresh_token(
    session: SessionDep, refresh_token_in: str = Header(..., alias="Authorization")
):
    if not refresh_token_in.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token format"
        )
    token = refresh_token_in.split(" ")[1]

    # Verify the refresh token
    payload = verify_refresh_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid refresh token",
        )

    user_id = payload.get("sub")

    # Find the user by ID
    user = crud.get_user_by_id(session=session, id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Create a new access token
    access_token = security.create_token(
        user.id,
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRES_MINUTES),
    )

    # Return the new access token
    return {"access_token": access_token, "token_type": "bearer", "user_id": user.id}


# Request Password Reset ####################################################################################
@router.post("/request-password-reset")
async def request_password_reset(
    session: SessionDep, email_body: EmailRequestBody, background_tasks: BackgroundTasks
):
    # Check if the user exists
    user = crud.get_user_by_email(session=session, email=email_body.email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    reset_token = security.create_token(user.id, expires_delta=timedelta(hours=1))
    reset_link = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"

    # Send password reset link via email
    background_tasks.add_task(
        send_verification_email, email=email_body.email, verification_link=reset_link
    )

    return {"msg": "Password reset email sent."}


# Reset Password ###########################################################################################
@router.put("/reset-password")
async def reset_password(
    new_password: NewPassword,
    session: SessionDep,
    verification_token: str = Header(..., alias="Authorization"),
):
    if not verification_token.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token format"
        )
    token = verification_token.split(" ")[1]
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except (InvalidTokenError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )
    user = session.get(User, token_data.sub)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    new_password = new_password.password
    # Update the user's password
    user.hashed_password = get_password_hash(new_password)
    user_update = UserUpdate(hashed_password=user.hashed_password)
    user = crud.update_user(session=session, db_user=user, user_in=user_update)

    return {"msg": "Password reset successfully."}
