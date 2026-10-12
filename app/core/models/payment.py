from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field, Column
import sqlalchemy as sa
from .base import TimestampMixin, generate_uuid
from .enums import PaymentType, PaymentStatus, Network


class Payment(TimestampMixin, SQLModel, table=True):
    """
    Core payment record. Tracks the full lifecycle from quote
    through provider order to settlement.
    """
    __tablename__ = "payments"

    id: str = Field(default_factory=generate_uuid, primary_key=True)
    user_id: str = Field(foreign_key="users.id", nullable=False, index=True)
    quote_id: Optional[str] = Field(default=None, foreign_key="quotes.id")
    recipient_id: Optional[str] = Field(default=None)

    type: PaymentType = Field(nullable=False)
    status: PaymentStatus = Field(default=PaymentStatus.CREATED)

    fiat_currency: str = Field(default="NGN")
    fiat_amount: float = Field(nullable=False)

    crypto_asset: str = Field(default="USDC")
    crypto_amount: float = Field(nullable=False)
    network: Network = Field(nullable=False)

    wallet_account_id: Optional[str] = Field(default=None, foreign_key="wallet_accounts.id")
    user_wallet_address: Optional[str] = Field(default=None)

    # Provider details
    provider: Optional[str] = Field(default=None)
    provider_order_id: Optional[str] = Field(default=None)
    provider_deposit_address: Optional[str] = Field(default=None)
    provider_reference: Optional[str] = Field(default=None)

    failure_reason: Optional[str] = Field(default=None)

    # Idempotency
    idempotency_key: Optional[str] = Field(
        default=None,
        sa_column=Column(sa.String, unique=True, nullable=True),
    )

    completed_at: Optional[datetime] = Field(default=None)


class PaymentAttempt(TimestampMixin, SQLModel, table=True):
    """Tracks individual provider-level attempts for a payment."""
    __tablename__ = "payment_attempts"

    id: str = Field(default_factory=generate_uuid, primary_key=True)
    payment_id: str = Field(foreign_key="payments.id", nullable=False, index=True)
    provider: str = Field(nullable=False)
    provider_order_id: Optional[str] = Field(default=None)
    status: str = Field(nullable=False)
    request_reference: Optional[str] = Field(default=None)
    error_code: Optional[str] = Field(default=None)
    error_message: Optional[str] = Field(default=None)
