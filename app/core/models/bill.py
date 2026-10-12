from typing import Any, Dict, Optional
from sqlmodel import SQLModel, Field, Column
import sqlalchemy as sa
from .base import TimestampMixin, generate_uuid
from .enums import BillCategory, BillOrderStatus, Network


class BillOrder(TimestampMixin, SQLModel, table=True):
    """A bill payment order (airtime, data, electricity, TV)."""
    __tablename__ = "bill_orders"

    id: str = Field(default_factory=generate_uuid, primary_key=True)
    user_id: str = Field(foreign_key="users.id", nullable=False, index=True)

    category: BillCategory = Field(nullable=False)
    status: BillOrderStatus = Field(default=BillOrderStatus.CREATED)

    # Fiat side
    fiat_currency: str = Field(default="NGN")
    fiat_amount: float = Field(nullable=False)

    # Crypto side
    crypto_asset: str = Field(default="USDC")
    crypto_amount: float = Field(nullable=False)
    network: Network = Field(nullable=False)

    # Bill details
    customer_id: Optional[str] = Field(default=None)  # phone number / meter number
    product_id: Optional[str] = Field(default=None)

    # Provider details
    provider: Optional[str] = Field(default=None)
    provider_order_id: Optional[str] = Field(default=None)
    provider_reference: Optional[str] = Field(default=None)

    meta_data: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(sa.JSON, nullable=True),
    )

    failure_reason: Optional[str] = Field(default=None)

