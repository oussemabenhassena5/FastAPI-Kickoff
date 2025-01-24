import re
import uuid
from typing import List

from pydantic import BaseModel, EmailStr, validator
from sqlmodel import Field, Relationship, SQLModel


def validate_password(password: str) -> tuple[bool, str]:
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


# Shared properties
class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    is_verified: bool = False


# Database model, database table inferred from class name
class User(UserBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str


class UserRegister(SQLModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=30)

    @validator("password")
    def validate_password_requirements(cls, v):
        is_valid, error_message = validate_password(v)
        if not is_valid:
            raise ValueError(error_message)
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=30)


# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=30)

    @validator("password")
    def validate_password_requirements(cls, v):
        is_valid, error_message = validate_password(v)
        if not is_valid:
            raise ValueError(error_message)
        return v


# Properties to receive via API on update, all are optional
class UserUpdate(UserBase):
    email: EmailStr | None = Field(default=None, max_length=255)  # type: ignore
    password: str | None = Field(default=None, min_length=8, max_length=30)
    is_verified: bool | None = None

    @validator("password")
    def validate_password_requirements(cls, v):
        is_valid, error_message = validate_password(v)
        if not is_valid:
            raise ValueError(error_message)
        return v


# Properties to return via API, id is always required
class UserPublic(UserBase):
    id: uuid.UUID


# JSON payload containing refrech/access token
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


#################################################################################


class RefreshTokenSchema(BaseModel):
    refresh_token: str


class UserUpdateMe(SQLModel):
    email: EmailStr | None = Field(default=None, max_length=255)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=30)
    new_password: str = Field(min_length=8, max_length=30)

    @validator("new_password")
    def validate_password_requirements(cls, v):
        is_valid, error_message = validate_password(v)
        if not is_valid:
            raise ValueError(error_message)
        return v


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int


# Generic message
class Message(SQLModel):
    message: str


# Contents of JWT token
class TokenPayload(SQLModel):
    sub: str | None = None


class NewPassword(SQLModel):
    password: str = Field(min_length=8, max_length=30)

    @validator("password")
    def validate_password_requirements(cls, v):
        is_valid, error_message = validate_password(v)
        if not is_valid:
            raise ValueError(error_message)
        return v


# Response model that wraps both the User and the Token models
class UserWithToken(UserPublic):
    refresh_token: str
    access_token: str
    token_type: str = "bearer"


class EmailRequestBody(BaseModel):
    email: EmailStr
