from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field
from .base import TimestampMixin, generate_uuid
from .enums import OnRampOrderStatus, Network


class OnRampOrder(TimestampMixin, SQLModel, table=True):
    """An on-ramp order: NGN → provider → USDC → user's wallet."""
    __tablename__ = "onramp_orders"

    id: str = Field(default_factory=generate_uuid, primary_key=True)
    user_id: str = Field(foreign_key="users.id", nullable=False, index=True)

    status: OnRampOrderStatus = Field(default=OnRampOrderStatus.CREATED)

    # Fiat side (user pays NGN into provider's bank)
    fiat_currency: str = Field(default="NGN")
    fiat_amount: float = Field(nullable=False)

    # Crypto side (provider delivers USDC to user's wallet)
    crypto_asset: str = Field(default="USDC")
    crypto_amount: float = Field(nullable=False)
    network: Network = Field(nullable=False)

    # Provider bank details (where user sends NGN)
    provider_bank_name: Optional[str] = Field(default=None)
    provider_account_number: Optional[str] = Field(default=None)
    provider_account_name: Optional[str] = Field(default=None)
    provider_reference: Optional[str] = Field(default=None)

    # User's destination wallet
    destination_wallet_address: Optional[str] = Field(default=None)
    wallet_account_id: Optional[str] = Field(default=None, foreign_key="wallet_accounts.id")

    # Provider details
    provider: Optional[str] = Field(default=None)
    provider_order_id: Optional[str] = Field(default=None)

    failure_reason: Optional[str] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)
