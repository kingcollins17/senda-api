from fastapi import APIRouter

router = APIRouter(
    prefix="/api/v1/onramp",
    tags=["onramp"]
)

@router.post("/quotes")
async def create_onramp_quote():
    return {"message": "Not implemented"}

@router.post("/orders")
async def create_onramp_order():
    return {"message": "Not implemented"}

@router.get("/orders/{id}")
async def get_onramp_order(id: str):
    return {"message": "Not implemented"}

@router.post("/orders/{id}/cancel")
async def cancel_onramp_order(id: str):
    return {"message": "Not implemented"}
