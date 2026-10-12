"""
FastAPI dependencies for the Quotes module.
Provides dependency injection functions for QuoteServiceImpl.
"""

from app.quotes.quote_service import QuoteServiceImpl

_quote_service = QuoteServiceImpl()


def get_quote_service() -> QuoteServiceImpl:
    """Dependency injection provider for unified QuoteServiceImpl."""
    return _quote_service


# Backwards compatibility providers and aliases
def get_ts() -> QuoteServiceImpl:
    return _quote_service


def get_bs() -> QuoteServiceImpl:
    return _quote_service


def get_transfer_service() -> QuoteServiceImpl:
    return _quote_service


def get_bill_service() -> QuoteServiceImpl:
    return _quote_service


quote_service = get_quote_service
transfer_service = get_quote_service
bill_service = get_quote_service

__all__ = [
    "get_quote_service",
    "get_ts",
    "get_bs",
    "get_transfer_service",
    "get_bill_service",
    "quote_service",
    "transfer_service",
    "bill_service",
]
