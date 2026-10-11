from typing import Optional
from sqlmodel import SQLModel, Field, Column
import sqlalchemy as sa
from .base import TimestampMixin, generate_uuid
from .enums import Network


class Wallet(TimestampMixin, SQLModel, table=True):
    """A wallet connection (e.g. Phantom, MetaMask) linked to a user."""
    __tablename__ = "wallets"

    id: str = Field(default_factory=generate_uuid, primary_key=True)
    user_id: str = Field(foreign_key="users.id", nullable=False, index=True)
    provider: str = Field(nullable=False)  # e.g. "phantom", "metamask"


class WalletAccount(TimestampMixin, SQLModel, table=True):
    """An individual account/address within a wallet, per network."""
    __tablename__ = "wallet_accounts"

    id: str = Field(default_factory=generate_uuid, primary_key=True)
    wallet_id: str = Field(foreign_key="wallets.id", nullable=False, index=True)
    network: Network = Field(nullable=False)
    address: str = Field(nullable=False)
