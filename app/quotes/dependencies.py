"""
FastAPI dependencies for the Quotes module.
Provides dependency injection functions for Bank Transfer and Bill Quote services.
"""

from app.quotes.services import (
    BankTransferQuoteService,
    BillQuoteService,
)


def get_ts() -> BankTransferQuoteService:
    """Dependency injection provider for BankTransferQuoteService (short alias)."""
    return BankTransferQuoteService()


def get_bs() -> BillQuoteService:
    """Dependency injection provider for BillQuoteService (short alias)."""
    return BillQuoteService()


def get_transfer_service() -> BankTransferQuoteService:
    """Dependency injection provider for BankTransferQuoteService (full name)."""
    return get_ts()


def get_bill_service() -> BillQuoteService:
    """Dependency injection provider for BillQuoteService (full name)."""
    return get_bs()


# Function aliases for transfer service and bill service
transfer_service = get_transfer_service
bill_service = get_bill_service

__all__ = [
    "get_ts",
    "get_bs",
    "get_transfer_service",
    "get_bill_service",
    "transfer_service",
    "bill_service",
]
