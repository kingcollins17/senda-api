"""
FastAPI dependency injection providers for bills module.
"""

from app.bills.bill_service import BillCatalogService

_catalog_service = BillCatalogService()


def get_bill_catalog_service() -> BillCatalogService:
    """Dependency provider returning singleton BillCatalogService instance."""
    return _catalog_service
