from typing import Optional
from sqlmodel import SQLModel, Field
from .base import TimestampMixin, generate_uuid
from .enums import RecipientType


class Recipient(TimestampMixin, SQLModel, table=True):
    """A bank account recipient that the user can send money to."""
    __tablename__ = "recipients"

    id: str = Field(default_factory=generate_uuid, primary_key=True)
    user_id: str = Field(foreign_key="users.id", nullable=False, index=True)
    type: RecipientType = Field(default=RecipientType.BANK_ACCOUNT)
    bank_code: str = Field(nullable=False)
    bank_name: str = Field(nullable=False)
    account_number: str = Field(nullable=False)
    account_name: str = Field(nullable=False)
