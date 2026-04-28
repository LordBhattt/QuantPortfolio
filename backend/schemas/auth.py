import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: uuid.UUID


class UserCreate(BaseModel):
    email: str
    password: str
    full_name: str | None = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not EMAIL_RE.match(normalized):
            raise ValueError("invalid email address")
        return normalized

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("password must be at least 8 characters")
        return value


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str | None = None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class UserInDB(UserOut):
    hashed_password: str
