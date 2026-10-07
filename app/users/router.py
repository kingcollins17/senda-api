from fastapi import APIRouter

router = APIRouter(
    prefix="/api/v1/users",
    tags=["users"]
)

@router.get("/me")
async def get_user_me():
    return {"message": "Not implemented"}

@router.patch("/me")
async def update_user_me():
    return {"message": "Not implemented"}

@router.delete("/me")
async def delete_user_me():
    return {"message": "Not implemented"}
