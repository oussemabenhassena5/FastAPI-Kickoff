from datetime import timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError
from pydantic import ValidationError
from src import crud
from src.config import security, settings
from src.deps import CurrentUser, SessionDep
from src.models.user import (
    PasswordResetConfirm,
    PasswordResetRequest,
    TokenPair,
    UserCreate,
    UserLogin,
    UserPublic,
    UserRegister,
)
from src.utils.email import send_password_reset_email, send_verification_email

router = APIRouter()


@router.post(
    "/register",
    response_model=UserPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Register new user",
    responses={
        409: {"description": "User with this email already exists"},
        429: {"description": "Too many requests"},
    },
)
async def register_user(
    request: Request,
    session: SessionDep,
    user_in: UserRegister,
    background_tasks: BackgroundTasks,
) -> UserPublic:
    """
    Register a new user account. Requires email verification to activate.
    """
    # Check existing user
    existing_user = await crud.get_user_by_email(session, user_in.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
        )

    # Create user
    user = await crud.create_user(session, UserCreate(**user_in.model_dump()))

    # Generate verification token with email claim
    verification_token = security.create_token(
        subject=str(user.id),
        expires_delta=timedelta(hours=settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS),
        token_type="verify",
    )

    # Queue verification email
    background_tasks.add_task(
        send_verification_email,
        email=user.email,
        verification_link=f"{settings.FRONTEND_URL}/verify-email?token={verification_token}",
    )

    return UserPublic.model_validate(user)


@router.post(
    "/login",
    response_model=TokenPair,
    summary="User login",
    responses={
        400: {"description": "Invalid credentials or inactive account"},
        429: {"description": "Too many requests"},
    },
)
async def login(session: SessionDep, credentials: UserLogin) -> TokenPair:
    """
    Authenticate user and return access/refresh token pair.
    """
    user = await crud.authenticate_user(
        session, credentials.email, credentials.password
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid credentials"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Account deactivated"
        )

    if not user.email_verified and settings.REQUIRE_EMAIL_VERIFICATION:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Email verification required"
        )

    # Generate token pair
    access_token = security.create_token(
        subject=str(user.id),
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRES_MINUTES),
        scopes=["auth:login"],
    )

    refresh_token = security.create_token(
        subject=str(user.id),
        expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRES_DAYS),
        token_type="refresh",
    )

    return TokenPair(
        access_token=access_token, refresh_token=refresh_token, token_type="bearer"
    )


@router.post(
    "/token",
    response_model=TokenPair,
    include_in_schema=False,  # For OAuth2 compliance but hidden from public docs
)
async def login_oauth2(
    session: SessionDep, form_data: OAuth2PasswordRequestForm = Depends()
) -> TokenPair:
    """
    OAuth2-compatible token endpoint (for client authentication flows)
    """
    user = await crud.authenticate_user(session, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid credentials"
        )

    return await login(
        session, UserLogin(email=form_data.username, password=form_data.password)
    )


@router.post(
    "/verify-email",
    response_model=TokenPair,
    summary="Verify email address",
    responses={
        400: {"description": "Invalid or expired verification token"},
        404: {"description": "User not found"},
    },
)
async def verify_email(session: SessionDep, token: str) -> TokenPair:
    """
    Confirm email address using verification token
    """
    try:
        payload = security.decode_token(token)
        if payload.get("type") != "verify":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token type"
            )

        user_id = payload.get("sub")
        user = await crud.get_user(session, user_id)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        if user.email_verified:
            return await login(session, UserLogin(email=user.email, password=None))

        user.email_verified = True
        await session.commit()

        # Generate new token pair after verification
        return await login(session, UserLogin(email=user.email, password=None))

    except (JWTError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token",
        )


@router.post(
    "/refresh",
    response_model=TokenPair,
    summary="Refresh access token",
    responses={401: {"description": "Invalid or expired refresh token"}},
)
async def refresh_token(session: SessionDep, refresh_token: str) -> TokenPair:
    """
    Generate new access token using valid refresh token
    """
    try:
        payload = security.decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type"
            )

        user_id = payload.get("sub")
        user = await crud.get_user(session, user_id)

        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
            )

        # Generate new access token
        access_token = security.create_token(
            subject=str(user.id),
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRES_MINUTES),
            scopes=payload.get("scp", []),
        )

        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,  # Refresh token remains valid until expiration
            token_type="bearer",
        )

    except (JWTError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )


@router.post(
    "/password-reset",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Request password reset",
    responses={202: {"description": "Password reset email sent if account exists"}},
)
async def request_password_reset(
    request: Request,
    session: SessionDep,
    reset_data: PasswordResetRequest,
    background_tasks: BackgroundTasks,
) -> dict:
    """
    Initiate password reset process (always returns 202 to prevent email enumeration)
    """
    user = await crud.get_user_by_email(session, reset_data.email)
    if user and user.is_active:
        reset_token = security.create_token(
            subject=str(user.id),
            expires_delta=timedelta(hours=settings.PASSWORD_RESET_TOKEN_EXPIRE_HOURS),
            token_type="reset",
        )

        background_tasks.add_task(
            send_password_reset_email,
            email=user.email,
            reset_link=f"{settings.FRONTEND_URL}/reset-password?token={reset_token}",
        )

    return {"detail": "If account exists, reset instructions have been sent"}


@router.post(
    "/password-reset/confirm",
    status_code=status.HTTP_200_OK,
    summary="Confirm password reset",
    responses={
        400: {"description": "Invalid or expired reset token"},
        404: {"description": "User not found"},
    },
)
async def confirm_password_reset(
    session: SessionDep, reset_data: PasswordResetConfirm
) -> dict:
    """
    Complete password reset process using valid token
    """
    try:
        payload = security.decode_token(reset_data.token)
        if payload.get("type") != "reset":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token type"
            )

        user_id = payload.get("sub")
        user = await crud.get_user(session, user_id)

        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        await crud.update_user_password(session, user, reset_data.new_password)

        return {"detail": "Password updated successfully"}

    except (JWTError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )


@router.get(
    "/me",
    response_model=UserPublic,
    summary="Get current user details",
    responses={401: {"description": "Missing or invalid credentials"}},
)
async def get_current_user_profile(current_user: CurrentUser) -> UserPublic:
    """
    Get details for currently authenticated user
    """
    return UserPublic.model_validate(current_user)
