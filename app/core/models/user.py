from typing import Optional
from sqlmodel import SQLModel, Field, Column
import sqlalchemy as sa
from .base import TimestampMixin, generate_uuid
from .enums import UserStatus, AuthProvider


class User(TimestampMixin, SQLModel, table=True):
    """Application user account."""
    __tablename__ = "users"

    id: str = Field(default_factory=generate_uuid, primary_key=True)
    email: str = Field(sa_column=Column(sa.String, unique=True, nullable=False, index=True))
    password_hash: Optional[str] = Field(default=None, nullable=True)
    name: str = Field(nullable=False)
    phone: Optional[str] = Field(default=None)
    avatar_url: Optional[str] = Field(default=None)
    status: UserStatus = Field(default=UserStatus.ACTIVE)
    auth_provider: AuthProvider = Field(default=AuthProvider.NORMAL)
    email_verified: bool = Field(default=False)

