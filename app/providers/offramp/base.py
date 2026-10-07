from abc import ABC, abstractmethod
from typing import Dict, Any

class OffRampProvider(ABC):
    
    @abstractmethod
    def create_quote(self, request: Dict[str, Any]) -> Dict[str, Any]:
        pass

    @abstractmethod
    def create_order(self, request: Dict[str, Any]) -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_order(self, order_id: str) -> Dict[str, Any]:
        pass
        
    @abstractmethod
    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    def verify_webhook(self, payload: Dict[str, Any], signature: str) -> bool:
        pass
