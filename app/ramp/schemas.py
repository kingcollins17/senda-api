"""
Pydantic schemas for Ramp endpoints.
"""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, field_validator

from app.core.models.enums import Network


class VerifyAccountRequest(BaseModel):
    account_number: str = Field(..., description="10-digit Nigerian NUBAN account number")
    bank_code: str = Field(..., description="Bank code e.g. 058 for GTBank, 044 for Access Bank")


class VerifyAccountResponse(BaseModel):
    fullname: str
    account_name: str
    bank_code: str
    bank_name: str
    account_number: str


class BankResponse(BaseModel):
    name: str = Field(..., description="Name of the bank")
    code: str = Field(..., description="Bank code")
    bank_code: str = Field(..., description="Bank code alias")
    logo_url: str = Field(..., description="URL to the bank logo image")
    slug: Optional[str] = Field(default=None, description="Slugified bank identifier")



class TransferRecipient(BaseModel):
    account_number: str = Field(..., description="10-digit Nigerian NUBAN account number")
    bank_code: str = Field(..., description="Bank code")
    bank_name: Optional[str] = Field(default=None, description="Optional bank name")
    account_name: Optional[str] = Field(default=None, description="Optional account name")
    fullname: Optional[str] = Field(default=None, description="Optional recipient fullname")
    recipient_id: Optional[str] = Field(default=None, description="Optional recipient ID")

    @field_validator("account_number")
    @classmethod
    def validate_account_number(cls, v: str) -> str:
        acc_str = str(v).strip()
        if not (acc_str.isdigit() and len(acc_str) == 10):
            raise ValueError(f"Invalid bank account number '{v}'. Nigerian NUBAN account number must be 10 digits.")
        return acc_str

    @field_validator("bank_code")
    @classmethod
    def validate_bank_code(cls, v: str) -> str:
        code_str = str(v).strip()
        if not code_str:
            raise ValueError("Recipient bank code is required")
        return code_str


class InitiateTransferRequest(BaseModel):
    amount: float = Field(..., gt=0, description="Amount to transfer in selected currency")
    currency: str = Field(default="NGN", description="Currency of choice, defaults to NGN")
    token: str = Field(default="USDC", description="Crypto token to pay with, defaults to USDC")
    network: Network = Field(default=Network.SOLANA, description="Blockchain network")
    recipient: TransferRecipient = Field(..., description="Recipient bank account details")


class FeesBreakdown(BaseModel):
    platform_fee_ngn: float = 0.0
    provider_fee_ngn: float = 0.0
    total_fee_ngn: float = 0.0
    total_fiat_amount: float = 0.0


class RecipientInfo(BaseModel):
    account_number: Optional[str] = None
    bank_code: Optional[str] = None
    bank_name: Optional[str] = None
    account_name: Optional[str] = None


class InitiateTransferResponse(BaseModel):
    order_id: str
    quote_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    status: str
    payment_type: str = "BANK_TRANSFER"
    fiat_currency: str = "NGN"
    fiat_amount: float
    crypto_asset: str = "USDC"
    crypto_amount: float
    network: str
    wallet_address: Optional[str] = None
    deposit_address: Optional[str] = None
    rate: Optional[float] = None
    platform_fee: float = 0.0
    provider_fee: float = 0.0
    fees: FeesBreakdown
    recipient: RecipientInfo
    expires_at: Optional[str] = None
    is_expired: bool = False
    blockchain_metadata: Dict[str, Any] = {}
    created_at: Optional[str] = None
    meta_data: Optional[Dict[str, Any]] = None
