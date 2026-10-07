from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.router import router as auth_router
from app.users.router import router as users_router
from app.wallets.router import router as wallets_router
from app.quotes.router import router as quotes_router
from app.payments.router import router as payments_router
from app.recipients.router import router as recipients_router
from app.bills.router import router as bills_router
from app.transactions.router import router as transactions_router
from app.notifications.router import router as notifications_router
from app.webhooks.router import router as webhooks_router
from app.onramp.router import router as onramp_router

app = FastAPI(
    title="Senda API",
    description="Backend API for Senda, orchestrating payments and crypto-to-fiat settlement.",
    version="0.1.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(wallets_router)
app.include_router(quotes_router)
app.include_router(payments_router)
app.include_router(recipients_router)
app.include_router(bills_router)
app.include_router(transactions_router)
app.include_router(notifications_router)
app.include_router(webhooks_router)
app.include_router(onramp_router)

@app.get("/api/v1/config", tags=["config"])
async def get_config():
    """
    Returns supported assets and networks.
    """
    return {
        "networks": [
            "ethereum",
            "polygon",
            "solana"
        ],
        "assets": [
            "USDC"
        ]
    }

@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "ok"}
