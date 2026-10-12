from typing import Dict, Any, List
import uuid
from .base import BillProvider

class MockBillProvider(BillProvider):
    
    def verify_customer(self, request: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "customer_name": "John Doe",
            "is_valid": True
        }

    def get_products(self, category: str) -> List[Dict[str, Any]]:
        category_upper = category.upper()
        if category_upper == "DATA":
            from app.bills.mock_data import DATA_PLANS
            return [
                {
                    "id": p["id"],
                    "name": p["name"],
                    "price": p["price_ngn"],
                    "provider": p["provider"],
                    "duration": p["duration"],
                    "data_amount": p["data_amount"],
                }
                for p in DATA_PLANS
            ]
        elif category_upper == "TV":
            from app.bills.mock_data import TV_PLANS
            return [
                {
                    "id": p["id"],
                    "name": p["name"],
                    "price": p["price_ngn"],
                    "provider": p["provider"],
                    "duration": p["duration"],
                }
                for p in TV_PLANS
            ]
        elif category_upper == "BETTING":
            from app.bills.mock_data import BETTING_PROVIDERS
            return [
                {
                    "id": p["id"],
                    "name": p["name"],
                    "provider": p["provider"],
                    "category": p["category"],
                }
                for p in BETTING_PROVIDERS
            ]
        return [
            {
                "id": "prod_1",
                "name": f"Mock {category} Product 1",
                "price": 1000
            }
        ]

    def create_order(self, request: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "provider_order_id": f"bill_{uuid.uuid4().hex[:8]}",
            "status": "PROCESSING"
        }

    def get_order(self, order_id: str) -> Dict[str, Any]:
        return {
            "provider_order_id": order_id,
            "status": "COMPLETED"
        }
