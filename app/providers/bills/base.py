from abc import ABC, abstractmethod
from typing import Dict, Any, List

class BillProvider(ABC):
    
    @abstractmethod
    def verify_customer(self, request: Dict[str, Any]) -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_products(self, category: str) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def create_order(self, request: Dict[str, Any]) -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_order(self, order_id: str) -> Dict[str, Any]:
        pass
