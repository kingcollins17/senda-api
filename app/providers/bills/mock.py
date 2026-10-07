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
