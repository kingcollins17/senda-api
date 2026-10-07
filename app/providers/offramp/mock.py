from typing import Dict, Any
import uuid
from .base import OffRampProvider

class MockOffRampProvider(OffRampProvider):
    
    def create_quote(self, request: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": f"quote_{uuid.uuid4().hex[:8]}",
            "amount_ngn": request.get("amount_ngn", 0),
            "crypto_asset": "USDC",
            "crypto_amount": request.get("amount_ngn", 0) / 1500, # mock exchange rate
            "network": "SOLANA",
            "platform_fee": 500,
            "provider_fee": 200,
        }

    def create_order(self, request: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "provider_order_id": f"ord_{uuid.uuid4().hex[:8]}",
            "crypto_asset": "USDC",
            "crypto_amount": request.get("crypto_amount", 0),
            "network": "SOLANA",
            "deposit_address": "mock_provider_deposit_address_123",
            "status": "AWAITING_CRYPTO"
        }

    def get_order(self, order_id: str) -> Dict[str, Any]:
        return {
            "provider_order_id": order_id,
            "status": "COMPLETED"
        }
        
    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        return {
            "provider_order_id": order_id,
            "status": "CANCELLED"
        }

    def verify_webhook(self, payload: Dict[str, Any], signature: str) -> bool:
        return True
