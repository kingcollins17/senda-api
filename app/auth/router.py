from fastapi import APIRouter

router = APIRouter(
    prefix="/api/v1/auth",
    tags=["auth"]
)

@router.post("/register")
async def register():
    return {"message": "Not implemented"}

@router.post("/login")
async def login():
    return {"message": "Not implemented"}

@router.post("/refresh")
async def refresh():
    return {"message": "Not implemented"}

@router.post("/logout")
async def logout():
    return {"message": "Not implemented"}

@router.get("/me")
async def get_me():
    return {"message": "Not implemented"}
