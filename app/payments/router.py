from fastapi import APIRouter

router = APIRouter(
    prefix="/api/v1/payments",
    tags=["payments"]
)

@router.post("")
async def create_payment():
    return {"message": "Not implemented"}

@router.get("")
async def get_payments():
    return {"message": "Not implemented"}

@router.get("/{payment_id}")
async def get_payment(payment_id: str):
    return {"message": "Not implemented"}

@router.post("/{payment_id}/cancel")
async def cancel_payment(payment_id: str):
    return {"message": "Not implemented"}
