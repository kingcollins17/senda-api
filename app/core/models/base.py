import uuid
from datetime import datetime
from typing import Optional
from pydantic import NaiveDatetime
from sqlmodel import SQLModel, Field
from app.utils.time import now


class TimestampMixin(SQLModel):
    """Mixin providing created_at and updated_at timestamps."""
    created_at: NaiveDatetime = Field(default_factory=now)
    updated_at: NaiveDatetime = Field(default_factory=now)



def generate_uuid() -> str:
    return str(uuid.uuid4())
