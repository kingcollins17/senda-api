"""
Pydantic schemas for Wallet endpoints.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

from app.core.models.enums import Network


class WalletAccountCreate(BaseModel):
    network: Network
    address: str = Field(min_length=10)


class WalletConnectRequest(BaseModel):
    provider: str = Field(min_length=2, description="Wallet provider name e.g. phantom, metamask")
    accounts: List[WalletAccountCreate] = Field(default_factory=list, description="Associated blockchain accounts")


class WalletAccountResponse(BaseModel):
    id: str
    wallet_id: str
    network: Network
    address: str
    created_at: Optional[datetime] = None

    model_config = {
        "from_attributes": True,
    }


class WalletResponse(BaseModel):
    id: str
    user_id: str
    provider: str
    accounts: List[WalletAccountResponse] = []
    created_at: Optional[datetime] = None

    model_config = {
        "from_attributes": True,
    }
