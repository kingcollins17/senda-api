from fastapi import APIRouter

router = APIRouter(
    prefix="/api/v1/wallets",
    tags=["wallets"]
)

@router.post("/connect")
async def connect_wallet():
    return {"message": "Not implemented"}

@router.get("")
async def get_wallets():
    return {"message": "Not implemented"}

@router.get("/balances")
async def get_wallet_balances():
    """
    Returns mocked balances for the prototype.
    """
    return {
        "total_usdc": 450.70,
        "networks": [
            {
                "network": "solana",
                "usdc_balance": 250.00
            },
            {
                "network": "polygon",
                "usdc_balance": 120.50
            },
            {
                "network": "ethereum",
                "usdc_balance": 80.20
            }
        ]
    }

@router.get("/{wallet_id}")
async def get_wallet(wallet_id: str):
    return {"message": "Not implemented"}

@router.delete("/{wallet_id}")
async def disconnect_wallet(wallet_id: str):
    return {"message": "Not implemented"}

@router.get("/{wallet_id}/accounts")
async def get_wallet_accounts(wallet_id: str):
    return {"message": "Not implemented"}
