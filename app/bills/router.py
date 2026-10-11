from typing import Any, Dict
from fastapi import APIRouter, HTTPException, status
from app.quotes.services import BillQuoteService, QuoteValidationError

router = APIRouter(
    prefix="/api/v1/bills",
    tags=["bills"]
)

@router.get("/services")
async def get_services():
    return {"message": "Not implemented"}

@router.post("/verify")
async def verify_bill():
    return {"message": "Not implemented"}

@router.post("/quote")
async def quote_bill(payload: Dict[str, Any]):
    """
    Generate a price quote for a bill payment (airtime, data, electricity, TV).
    """
    try:
        service = BillQuoteService()
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

@router.post("/orders")
async def create_bill_order():
    return {"message": "Not implemented"}

@router.get("/orders/{id}")
async def get_bill_order(id: str):
    return {"message": "Not implemented"}
