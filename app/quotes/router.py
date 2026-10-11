from typing import Any, Dict
from fastapi import APIRouter, HTTPException, status
from app.quotes.services import (
    QuoteServiceFactory,
    QuoteValidationError,
)

router = APIRouter(
    prefix="/api/v1/quotes",
    tags=["quotes"]
)

@router.post("")
async def create_quote(payload: Dict[str, Any]):
    """
    Generate a price quote for bank transfer or bill payment.
    Returns destination wallet address, network, amount, rate, token, and blockchain payment metadata.
    """
    quote_type = payload.get("type", payload.get("payment_type", "BANK_TRANSFER"))
    try:
        service = QuoteServiceFactory.create(str(quote_type))
        return service.get_quote(payload)
    except QuoteValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Quote calculation failed: {str(exc)}",
        ) from exc

@router.get("/{quote_id}")
async def get_quote(quote_id: str):
    try:
        return {"message": f"Quote {quote_id} fetched successfully"}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch quote: {str(exc)}",
        ) from exc

