"""
Pydantic schemas for Authentication endpoints.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field

from app.core.models.enums import AuthProvider, UserStatus
from app.wallets.schemas import WalletResponse


class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: Optional[str] = Field(default=None, min_length=6)
    name: str = Field(min_length=2)
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    auth_provider: AuthProvider = Field(default=AuthProvider.NORMAL)


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: Optional[str] = None
    auth_provider: AuthProvider = Field(default=AuthProvider.NORMAL)


class GoogleLoginRequest(BaseModel):
    id_token: Optional[str] = None
    email: EmailStr
    name: Optional[str] = None
    avatar_url: Optional[str] = None


class AppleLoginRequest(BaseModel):
    id_token: Optional[str] = None
    code: Optional[str] = None
    email: EmailStr
    name: Optional[str] = None



class RefreshTokenRequest(BaseModel):
    refresh_token: str


class VerifyEmailRequest(BaseModel):
    token: Optional[str] = None
    email: Optional[EmailStr] = None
    code: Optional[str] = None


class SendOtpRequest(BaseModel):
    email: EmailStr


class SendOtpResponse(BaseModel):
    message: str
    email: str


class VerifyOtpRequest(BaseModel):
    email: EmailStr
    otp: Optional[str] = None
    code: Optional[str] = None


class VerifyOtpResponse(BaseModel):
    message: str
    email: str
    email_verified: bool


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    status: UserStatus
    auth_provider: AuthProvider
    email_verified: bool
    created_at: Optional[datetime] = None
    wallet: Optional[WalletResponse] = None

    model_config = {
        "from_attributes": True,
    }


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse
    verification_token: Optional[str] = None
