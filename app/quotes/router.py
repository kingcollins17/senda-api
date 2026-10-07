from fastapi import APIRouter

router = APIRouter(
    prefix="/api/v1/quotes",
    tags=["quotes"]
)

@router.post("")
async def create_quote():
    return {"message": "Not implemented"}

@router.get("/{quote_id}")
async def get_quote(quote_id: str):
    return {"message": "Not implemented"}
