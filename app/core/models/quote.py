from datetime import datetime
from typing import Optional
from pydantic import NaiveDatetime
from sqlmodel import SQLModel, Field
from .base import TimestampMixin, generate_uuid
from .enums import Network


class Quote(TimestampMixin, SQLModel, table=True):
    """A price quote for converting fiat to crypto."""
    __tablename__ = "quotes"

    id: str = Field(default_factory=generate_uuid, primary_key=True)
    user_id: str = Field(foreign_key="users.id", nullable=False, index=True)
    type: str = Field(nullable=False)  # e.g. BANK_TRANSFER, AIRTIME

    amount_ngn: float = Field(nullable=False)
    crypto_asset: str = Field(default="USDC")
    crypto_amount: float = Field(nullable=False)
    network: Network = Field(nullable=False)
    exchange_rate: float = Field(nullable=False)

    platform_fee: float = Field(default=0.0)
    provider_fee: float = Field(default=0.0)

    recipient_id: Optional[str] = Field(default=None, foreign_key="recipients.id")

    expires_at: NaiveDatetime = Field(nullable=False)
    is_expired: bool = Field(default=False)
