from fastapi import APIRouter

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
async def quote_bill():
    return {"message": "Not implemented"}

@router.post("/orders")
async def create_bill_order():
    return {"message": "Not implemented"}

@router.get("/orders/{id}")
async def get_bill_order(id: str):
    return {"message": "Not implemented"}
