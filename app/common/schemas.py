"""
Common generic schemas for standardized API responses.
"""

from typing import Generic, Optional, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class BaseResponse(BaseModel, Generic[T]):
    """
    Standardized API response wrapper.
    Contains a human-readable detail message and generic data payload.
    """
    detail: str = "Success"
    data: Optional[T] = None
