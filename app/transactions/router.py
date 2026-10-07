from fastapi import APIRouter

router = APIRouter(
    prefix="/api/v1/transactions",
    tags=["transactions"]
)

@router.get("")
async def get_transactions():
    return {"message": "Not implemented"}

@router.get("/{id}")
async def get_transaction(id: str):
    return {"message": "Not implemented"}
