from fastapi import APIRouter

router = APIRouter(
    prefix="/api/v1/recipients",
    tags=["recipients"]
)

@router.post("")
async def create_recipient():
    return {"message": "Not implemented"}

@router.get("")
async def get_recipients():
    return {"message": "Not implemented"}

@router.get("/{id}")
async def get_recipient(id: str):
    return {"message": "Not implemented"}

@router.patch("/{id}")
async def update_recipient(id: str):
    return {"message": "Not implemented"}

@router.delete("/{id}")
async def delete_recipient(id: str):
    return {"message": "Not implemented"}

@router.post("/verify")
async def verify_recipient():
    return {"message": "Not implemented"}
