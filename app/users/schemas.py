"""
Pydantic schemas for User profile management.
"""

from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class UpdateUserRequest(BaseModel):
    """
    Schema for updating user profile.
    Allows updating phone number and avatar URL only.
    """
    phone: Optional[str] = Field(default=None, max_length=30)
    avatar_url: Optional[str] = Field(default=None, max_length=500)

    model_config = ConfigDict(extra="forbid")
