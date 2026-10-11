from typing import Optional
from sqlmodel import SQLModel, Field
from .base import TimestampMixin, generate_uuid
from .enums import TransactionType, TransactionStatus, Network


class Transaction(TimestampMixin, SQLModel, table=True):
    """Unified transaction history record shown to the user."""
    __tablename__ = "transactions"

    id: str = Field(default_factory=generate_uuid, primary_key=True)
    user_id: str = Field(foreign_key="users.id", nullable=False, index=True)

    type: TransactionType = Field(nullable=False)
    status: TransactionStatus = Field(default=TransactionStatus.PENDING)

    fiat_currency: str = Field(default="NGN")
    fiat_amount: float = Field(nullable=False)

    crypto_asset: str = Field(default="USDC")
    crypto_amount: float = Field(nullable=False)
    network: Network = Field(nullable=False)
    exchange_rate: float = Field(nullable=False)

    fees: float = Field(default=0.0)

    # Reference to the underlying domain object
    payment_id: Optional[str] = Field(default=None, foreign_key="payments.id")
    bill_order_id: Optional[str] = Field(default=None, foreign_key="bill_orders.id")
    onramp_order_id: Optional[str] = Field(default=None, foreign_key="onramp_orders.id")

    # Recipient info (for bank transfers)
    recipient_id: Optional[str] = Field(default=None, foreign_key="recipients.id")

    # Provider / blockchain metadata
    provider_reference: Optional[str] = Field(default=None)
    blockchain_tx_hash: Optional[str] = Field(default=None)

    description: Optional[str] = Field(default=None)
