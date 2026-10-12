from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.bills.dependencies import get_bill_catalog_service
from app.bills.schemas import (
    BettingProvidersResponse,
    BillServicesResponse,
    DataPlansResponse,
    TVPlansResponse,
)
from app.bills.bill_service import BillCatalogService
from app.quotes.quote_service import QuoteServiceImpl, QuoteValidationError

router = APIRouter(
    prefix="/api/v1/bills",
    tags=["bills"]
)


@router.get("/services", response_model=BillServicesResponse)
async def get_services(
    catalog: BillCatalogService = Depends(get_bill_catalog_service),
) -> BillServicesResponse:
    """
    List all supported bill payment service categories and their providers.
    """
    services = catalog.get_services()
    return BillServicesResponse(
        detail="Bill services retrieved successfully",
        services=services,
    )


@router.get("/data-plans", response_model=DataPlansResponse)
@router.get("/data/plans", response_model=DataPlansResponse, include_in_schema=False)
@router.get("/plans/data", response_model=DataPlansResponse, include_in_schema=False)
@router.get("/data", response_model=DataPlansResponse, include_in_schema=False)
async def get_data_plans(
    provider: Optional[str] = Query(
        None,
        description="Filter by telco provider: airtel, glo, mtn, 9mobile (optional)",
    ),
    duration: Optional[str] = Query(
        None,
        description="Filter by plan duration: daily, weekly, monthly, night, weekend (optional)",
    ),
    catalog: BillCatalogService = Depends(get_bill_catalog_service),
) -> DataPlansResponse:
    """
    List mobile data plans for MTN, Airtel, Glo, and 9mobile.
    
    Supports filtering by provider (optional) and duration (daily, weekly, monthly, night, weekend).
    """
    try:
        plans = catalog.get_data_plans(provider=provider, duration=duration)
        norm_provider = catalog.normalize_data_provider(provider) if provider else None
        norm_duration = catalog.normalize_data_duration(duration) if duration else None

        return DataPlansResponse(
            detail="Data plans retrieved successfully",
            provider=norm_provider,
            duration=norm_duration,
            total=len(plans),
            plans=plans,
            data=plans,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get("/tv-plans", response_model=TVPlansResponse)
@router.get("/tv/plans", response_model=TVPlansResponse, include_in_schema=False)
@router.get("/plans/tv", response_model=TVPlansResponse, include_in_schema=False)
@router.get("/tv-subscriptions", response_model=TVPlansResponse, include_in_schema=False)
@router.get("/tv", response_model=TVPlansResponse, include_in_schema=False)
async def get_tv_plans(
    provider: Optional[str] = Query(
        None,
        description="Filter by TV provider: dstv, gotv, startimes, showmax (optional)",
    ),
    duration: Optional[str] = Query(
        None,
        description="Filter by subscription duration: daily, weekly, monthly, annual (optional)",
    ),
    catalog: BillCatalogService = Depends(get_bill_catalog_service),
) -> TVPlansResponse:
    """
    List TV subscription packages and streaming plans for DStv, GOtv, StarTimes, and Showmax.
    
    Supports filtering by provider (optional) and duration (daily, weekly, monthly, annual).
    """
    try:
        plans = catalog.get_tv_plans(provider=provider, duration=duration)
        norm_provider = catalog.normalize_tv_provider(provider) if provider else None
        norm_duration = catalog.normalize_tv_duration(duration) if duration else None

        return TVPlansResponse(
            detail="TV subscription plans retrieved successfully",
            provider=norm_provider,
            duration=norm_duration,
            total=len(plans),
            plans=plans,
            data=plans,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get("/betting-providers", response_model=BettingProvidersResponse)
@router.get("/betting/providers", response_model=BettingProvidersResponse, include_in_schema=False)
@router.get("/betting", response_model=BettingProvidersResponse, include_in_schema=False)
async def get_betting_providers(
    catalog: BillCatalogService = Depends(get_bill_catalog_service),
) -> BettingProvidersResponse:
    """
    List supported sports betting platforms (SportyBet, Bet9ja, 1xBet, BetKing, etc.).
    """
    providers = catalog.get_betting_providers()
    return BettingProvidersResponse(
        detail="Betting providers retrieved successfully",
        total=len(providers),
        providers=providers,
        data=providers,
    )


@router.post("/verify")
async def verify_bill():
    return {"message": "Not implemented"}


@router.post("/quote")
async def quote_bill(payload: Dict[str, Any]):
    """
    Generate a price quote for a bill payment (airtime, data, electricity, TV, betting).
    """
    try:
        service = QuoteServiceImpl()
        return service.get_quote(payload)
    except QuoteValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post("/orders")
async def create_bill_order():
    return {"message": "Not implemented"}


@router.get("/orders/{id}")
async def get_bill_order(id: str):
    return {"message": "Not implemented"}
