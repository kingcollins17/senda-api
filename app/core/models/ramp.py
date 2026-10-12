from datetime import datetime
from typing import Any, Dict, Optional
from sqlmodel import SQLModel, Field, Column
import sqlalchemy as sa
from .base import TimestampMixin, generate_uuid
from .enums import OnRampOrderStatus, OffRampOrderStatus, Network



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

    meta_data: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(sa.JSON, nullable=True),
    )

    failure_reason: Optional[str] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)


class OffRampOrder(TimestampMixin, SQLModel, table=True):
    """An off-ramp order: user crypto (USDC) → provider → NGN → recipient bank."""
    __tablename__ = "offramp_orders"

    id: str = Field(default_factory=generate_uuid, primary_key=True)
    user_id: str = Field(foreign_key="users.id", nullable=False, index=True)
    quote_id: Optional[str] = Field(default=None, foreign_key="quotes.id")

    status: OffRampOrderStatus = Field(default=OffRampOrderStatus.CREATED)

    # Fiat side (provider delivers NGN to recipient bank)
    fiat_currency: str = Field(default="NGN")
    fiat_amount: float = Field(nullable=False)

    # Crypto side (user pays USDC to provider deposit address)
    crypto_asset: str = Field(default="USDC")
    crypto_amount: float = Field(nullable=False)
    network: Network = Field(nullable=False)

    # Provider deposit details (where user sends crypto)
    provider_deposit_address: Optional[str] = Field(default=None)
    provider_reference: Optional[str] = Field(default=None)

    # Recipient bank details (where NGN is delivered)
    recipient_id: Optional[str] = Field(default=None)
    recipient_bank_name: Optional[str] = Field(default=None)
    recipient_account_number: Optional[str] = Field(default=None)
    recipient_account_name: Optional[str] = Field(default=None)
    recipient_bank_code: Optional[str] = Field(default=None)

    # User's source wallet
    wallet_account_id: Optional[str] = Field(default=None, foreign_key="wallet_accounts.id")
    user_wallet_address: Optional[str] = Field(default=None)

    # Provider details
    provider: Optional[str] = Field(default=None)
    provider_order_id: Optional[str] = Field(default=None)

    # Blockchain transaction details
    blockchain_tx_hash: Optional[str] = Field(default=None)

    # Idempotency
    idempotency_key: Optional[str] = Field(
        default=None,
        sa_column=Column(sa.String, unique=True, nullable=True, index=True),
    )

    meta_data: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(sa.JSON, nullable=True),
    )

    failure_reason: Optional[str] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)

