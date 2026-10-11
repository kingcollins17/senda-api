from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field, Column, UniqueConstraint
import sqlalchemy as sa
from .base import TimestampMixin, generate_uuid
from .enums import WebhookEventStatus


class WebhookEvent(TimestampMixin, SQLModel, table=True):
    """Stores inbound provider webhooks for idempotent processing."""
    __tablename__ = "webhook_events"
    __table_args__ = (
        UniqueConstraint("provider", "event_id", name="uq_provider_event_id"),
    )

    id: str = Field(default_factory=generate_uuid, primary_key=True)
    provider: str = Field(nullable=False)
    event_id: str = Field(nullable=False)
    event_type: str = Field(nullable=False)
    payload: str = Field(nullable=False)  # JSON string
    status: WebhookEventStatus = Field(default=WebhookEventStatus.RECEIVED)
    processed_at: Optional[datetime] = Field(default=None)
