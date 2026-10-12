"""
Pydantic schemas for bills catalog, data plans, and TV subscription plans.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DataProviderEnum(str, Enum):
    AIRTEL = "airtel"
    GLO = "glo"
    MTN = "mtn"
    NINE_MOBILE = "9mobile"


class PlanDurationEnum(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    NIGHT = "night"
    WEEKEND = "weekend"


class TVProviderEnum(str, Enum):
    DSTV = "dstv"
    GOTV = "gotv"
    STARTIMES = "startimes"
    SHOWMAX = "showmax"


class TVDurationEnum(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    ANNUAL = "annual"


class DataPlanResponse(BaseModel):
    id: str = Field(..., description="Unique identifier for the data plan")
    provider: str = Field(..., description="Provider slug (airtel, glo, mtn, 9mobile)")
    provider_name: str = Field(..., description="Formatted provider name (e.g. MTN, Airtel, Glo, 9mobile)")
    name: str = Field(..., description="Display name of the data plan")
    data_amount: str = Field(..., description="Data allowance (e.g. 1GB, 10GB)")
    duration: str = Field(..., description="Duration classification: daily, weekly, monthly, night, weekend")
    validity: str = Field(..., description="Human-readable validity duration (e.g. 1 Day, 7 Days, 30 Days)")
    price_ngn: float = Field(..., description="Price in Nigerian Naira (NGN)")
    category: str = Field(default="DATA", description="Bill category")


class TVPlanResponse(BaseModel):
    id: str = Field(..., description="Unique identifier for the TV subscription plan/bouquet")
    provider: str = Field(..., description="Provider slug (dstv, gotv, startimes, showmax)")
    provider_name: str = Field(..., description="Formatted provider name (e.g. DStv, GOtv, StarTimes, Showmax)")
    name: str = Field(..., description="Bouquet / Package name (e.g. DStv Compact, GOtv Max)")
    duration: str = Field(..., description="Duration classification: daily, weekly, monthly, annual")
    validity: str = Field(..., description="Human-readable validity duration (e.g. 30 Days, 365 Days)")
    price_ngn: float = Field(..., description="Price in Nigerian Naira (NGN)")
    channels_count: Optional[int] = Field(default=None, description="Number of channels included")
    description: Optional[str] = Field(default=None, description="Package description / highlights")
    category: str = Field(default="TV", description="Bill category")


class DataPlansResponse(BaseModel):
    detail: str = "Data plans retrieved successfully"
    provider: Optional[str] = None
    duration: Optional[str] = None
    total: int
    plans: List[DataPlanResponse]
    data: List[DataPlanResponse]


class TVPlansResponse(BaseModel):
    detail: str = "TV subscription plans retrieved successfully"
    provider: Optional[str] = None
    duration: Optional[str] = None
    total: int
    plans: List[TVPlanResponse]
    data: List[TVPlanResponse]


class BillServiceCategoryResponse(BaseModel):
    category: str
    name: str
    providers: List[str]
    description: str


class BillServicesResponse(BaseModel):
    detail: str = "Bill services retrieved successfully"
    services: List[BillServiceCategoryResponse]


class BettingProviderResponse(BaseModel):
    id: str = Field(..., description="Provider slug (e.g. sportybet, bet9ja)")
    provider: str = Field(..., description="Provider identifier")
    name: str = Field(..., description="Betting platform name")
    category: str = Field(default="BETTING", description="Bill category")
    description: Optional[str] = Field(default=None, description="Brief description")


class BettingProvidersResponse(BaseModel):
    detail: str = "Betting providers retrieved successfully"
    total: int
    providers: List[BettingProviderResponse]
    data: List[BettingProviderResponse]
