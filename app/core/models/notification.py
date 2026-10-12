from typing import List, Optional
from sqlmodel import SQLModel, Field, Column
import sqlalchemy as sa
from .base import TimestampMixin, generate_uuid
from .enums import NotificationStatus


class Notification(TimestampMixin, SQLModel, table=True):
    """In-app notification for the user."""
    __tablename__ = "notifications"

    id: str = Field(default_factory=generate_uuid, primary_key=True)
    user_id: str = Field(foreign_key="users.id", nullable=False, index=True)
    title: str = Field(nullable=False)
    body: str = Field(nullable=False)
    status: NotificationStatus = Field(default=NotificationStatus.UNREAD)
    channels: List[str] = Field(
        default_factory=list,
        sa_column=Column(sa.JSON, nullable=False, default=[]),
    )

    # Optional link to the source entity
    payment_id: Optional[str] = Field(default=None, foreign_key="payments.id")
    bill_order_id: Optional[str] = Field(default=None, foreign_key="bill_orders.id")
    onramp_order_id: Optional[str] = Field(default=None, foreign_key="onramp_orders.id")
    offramp_order_id: Optional[str] = Field(default=None, foreign_key="offramp_orders.id")

