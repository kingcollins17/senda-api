from datetime import datetime, timedelta
import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.database import get_session
from app.core.dependencies import get_user
from app.core.models.base import generate_uuid
from app.core.models.enums import Network
from app.core.models.quote import Quote
from app.core.models.user import User
from app.quotes.dependencies import get_quote_service
from app.quotes.quote_service import QuoteServiceImpl, QuoteValidationError
from app.utils.time import now

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/quotes",
    tags=["quotes"]
)


async def _persist_quote(
    quote: Dict[str, Any],
    current_user: User,
    session: AsyncSession,
) -> Dict[str, Any]:
    """
    Saves or updates quote record in database and attaches db_id to response.
    """
    raw_expires = quote.get("expires_at")
    if isinstance(raw_expires, str):
        expires_at_dt = datetime.fromisoformat(raw_expires)
        if expires_at_dt.tzinfo is not None:
            expires_at_dt = expires_at_dt.replace(tzinfo=None)
    elif isinstance(raw_expires, datetime):
        expires_at_dt = raw_expires.replace(tzinfo=None) if raw_expires.tzinfo else raw_expires
    else:
        validity = int(quote.get("validity_seconds", 900))
        expires_at_dt = now() + timedelta(seconds=validity)

    network_str = str(quote.get("network", "SOLANA")).upper()
    try:
        network_enum = Network(network_str)
    except ValueError:
        network_enum = Network.SOLANA

    fees = quote.get("fees", {})
    platform_fee = float(fees.get("platform_fee_ngn", 0.0))
    provider_fee = float(fees.get("provider_fee_ngn", 0.0))

    quote_id = str(quote.get("quote_id") or generate_uuid())

    existing_stmt = select(Quote).where(Quote.id == quote_id)
    existing_quote = (await session.exec(existing_stmt)).first()
    if existing_quote:
        quote_record = existing_quote
    else:
        quote_record = Quote(
            id=quote_id,
            user_id=current_user.id,
            type=str(quote.get("payment_type", "BANK_TRANSFER")),
            amount_ngn=float(quote.get("fiat_amount", 0.0)),
            crypto_asset=str(quote.get("token", "USDC")),
            crypto_amount=float(quote.get("amount", 0.0)),
            network=network_enum,
            exchange_rate=float(quote.get("rate", 1500.0)),
            platform_fee=platform_fee,
            provider_fee=provider_fee,
            recipient_id=None,
            expires_at=expires_at_dt,
            is_expired=False,
        )
        session.add(quote_record)
        await session.commit()
        await session.refresh(quote_record)

    quote["db_id"] = quote_record.id
    return quote


# =============================================================================
# Bank Transfer / Off-Ramp Quote
# =============================================================================

@router.post("/transfer")
@router.post("/bank-transfer", include_in_schema=False)
async def create_transfer_quote(
    payload: Dict[str, Any],
    service: QuoteServiceImpl = Depends(get_quote_service),
    current_user: User = Depends(get_user),
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    """
    Generate a price quote for bank transfer off-ramp and save it in the database.
    Requires recipient bank details in payload (account_number, bank_code, bank_name, account_name).
    """
    try:
        body = dict(payload)
        if not body.get("payment_type") and not body.get("type"):
            body["payment_type"] = "BANK_TRANSFER"
        quote = service.get_quote(body)
        return await _persist_quote(quote, current_user, session)
    except (QuoteValidationError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Bank transfer quote calculation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Quote calculation failed: {str(exc)}",
        ) from exc


# =============================================================================
# Bill Quotes: Package / Plan Specific & Service-Specific Endpoints
# =============================================================================

@router.post("/bill/plan/{plan_id}")
async def create_bill_quote_by_plan_id(
    plan_id: str = Path(..., description="Unique ID of the data plan or TV bouquet (e.g. mtn-daily-1gb, dstv-compact-monthly)"),
    payload: Optional[Dict[str, Any]] = None,
    service: QuoteServiceImpl = Depends(get_quote_service),
    current_user: User = Depends(get_user),
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    """
    Generate a price quote for a bill given the specific plan or bouquet package ID.
    Automatically retrieves the plan price, provider, category, and metadata from the catalog.
    """
    body = dict(payload or {})
    plan = service.find_plan(plan_id)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan or package with ID '{plan_id}' not found",
        )

    body["plan_id"] = plan_id
    if "amount_ngn" not in body or body["amount_ngn"] is None:
        body["amount_ngn"] = plan["price_ngn"]
    if not body.get("category"):
        body["category"] = plan.get("category", "DATA")
    if not body.get("provider") and not body.get("biller_name"):
        body["biller_name"] = plan.get("provider_name", plan.get("provider"))

    try:
        quote = service.get_quote(body)
        return await _persist_quote(quote, current_user, session)
    except (QuoteValidationError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Bill quote by plan failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Quote calculation failed: {str(exc)}",
        ) from exc


@router.post("/bill/plan", include_in_schema=False)
async def create_bill_quote_by_plan_body(
    payload: Dict[str, Any],
    service: QuoteServiceImpl = Depends(get_quote_service),
    current_user: User = Depends(get_user),
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    """Alias allowing plan_id in the JSON body."""
    plan_id = payload.get("plan_id") or payload.get("package_id")
    if not plan_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing 'plan_id' in request body",
        )
    return await create_bill_quote_by_plan_id(
        plan_id=str(plan_id),
        payload=payload,
        service=service,
        current_user=current_user,
        session=session,
    )


@router.post("/bill/data")
@router.post("/data", include_in_schema=False)
async def create_data_quote(
    payload: Dict[str, Any],
    service: QuoteServiceImpl = Depends(get_quote_service),
    current_user: User = Depends(get_user),
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    """
    Generate a price quote for mobile data bundle (MTN, Airtel, Glo, 9mobile).
    Provide 'plan_id' (e.g. mtn-daily-1gb) or ('provider' + 'amount_ngn'), and 'phone_number'.
    """
    body = dict(payload)
    body["category"] = "DATA"
    if "phone_number" in body and not body.get("customer_id"):
        body["customer_id"] = body["phone_number"]

    try:
        quote = service.get_quote(body)
        return await _persist_quote(quote, current_user, session)
    except (QuoteValidationError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post("/bill/tv")
@router.post("/tv", include_in_schema=False)
async def create_tv_quote(
    payload: Dict[str, Any],
    service: QuoteServiceImpl = Depends(get_quote_service),
    current_user: User = Depends(get_user),
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    """
    Generate a price quote for TV subscription (DStv, GOtv, StarTimes, Showmax).
    Provide 'plan_id' (e.g. dstv-compact-monthly) or ('provider' + 'amount_ngn'), and 'smartcard_number'.
    """
    body = dict(payload)
    body["category"] = "TV"
    if "smartcard_number" in body and not body.get("customer_id"):
        body["customer_id"] = body["smartcard_number"]

    try:
        quote = service.get_quote(body)
        return await _persist_quote(quote, current_user, session)
    except (QuoteValidationError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post("/bill/airtime")
@router.post("/airtime", include_in_schema=False)
async def create_airtime_quote(
    payload: Dict[str, Any],
    service: QuoteServiceImpl = Depends(get_quote_service),
    current_user: User = Depends(get_user),
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    """
    Generate a price quote for airtime top-up.
    Provide 'phone_number', 'provider' (MTN, Airtel, Glo, 9mobile), and 'amount_ngn'.
    """
    body = dict(payload)
    body["category"] = "AIRTIME"
    if "phone_number" in body and not body.get("customer_id"):
        body["customer_id"] = body["phone_number"]

    try:
        quote = service.get_quote(body)
        return await _persist_quote(quote, current_user, session)
    except (QuoteValidationError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post("/bill/electricity")
@router.post("/electricity", include_in_schema=False)
async def create_electricity_quote(
    payload: Dict[str, Any],
    service: QuoteServiceImpl = Depends(get_quote_service),
    current_user: User = Depends(get_user),
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    """
    Generate a price quote for electricity tokens.
    Provide 'meter_number', 'provider' / 'disco' (IKEDC, EKEDC, AEDC, etc.), and 'amount_ngn'.
    """
    body = dict(payload)
    body["category"] = "ELECTRICITY"
    if "meter_number" in body and not body.get("customer_id"):
        body["customer_id"] = body["meter_number"]

    try:
        quote = service.get_quote(body)
        return await _persist_quote(quote, current_user, session)
    except (QuoteValidationError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post("/bill/betting")
@router.post("/betting", include_in_schema=False)
async def create_betting_quote(
    payload: Dict[str, Any],
    service: QuoteServiceImpl = Depends(get_quote_service),
    current_user: User = Depends(get_user),
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    """
    Generate a price quote for betting wallet funding.
    Provide 'customer_id' / 'user_id', 'provider' (SportyBet, Bet9ja, etc.), and 'amount_ngn'.
    """
    body = dict(payload)
    body["category"] = "BETTING"
    if "user_id" in body and not body.get("customer_id"):
        body["customer_id"] = body["user_id"]

    try:
        quote = service.get_quote(body)
        return await _persist_quote(quote, current_user, session)
    except (QuoteValidationError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post("/bill")
@router.post("/bills", include_in_schema=False)
async def create_bill_quote(
    payload: Dict[str, Any],
    service: QuoteServiceImpl = Depends(get_quote_service),
    current_user: User = Depends(get_user),
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    """
    Generate a price quote for bill payment (Data, Airtime, Electricity, TV, Betting).
    """
    try:
        quote = service.get_quote(payload)
        return await _persist_quote(quote, current_user, session)
    except (QuoteValidationError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Bill quote calculation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Quote calculation failed: {str(exc)}",
        ) from exc


# =============================================================================
# Unified Quote Endpoint
# =============================================================================

@router.post("")
@router.post("/", include_in_schema=False)
async def create_quote(
    payload: Dict[str, Any],
    service: QuoteServiceImpl = Depends(get_quote_service),
    current_user: User = Depends(get_user),
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    """
    Generate a price quote for bank transfer or bill payment (general unified endpoint).
    Routes payment through QuoteServiceImpl, differentiating by payload metadata.
    """
    try:
        quote = service.get_quote(payload)
        return await _persist_quote(quote, current_user, session)
    except (QuoteValidationError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Quote calculation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Quote calculation failed: {str(exc)}",
        ) from exc


# =============================================================================
# Get Quote by ID
# =============================================================================

@router.get("/{quote_id}")
async def get_quote(
    quote_id: str,
    current_user: User = Depends(get_user),
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    """
    Fetch quote details from database by quote ID.
    Requires authentication via Bearer token (get_user).
    """
    try:
        statement = select(Quote).where(Quote.id == quote_id, Quote.user_id == current_user.id)
        quote = (await session.exec(statement)).first()
        if not quote:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Quote '{quote_id}' not found",
            )

        # Update expiration status if expired
        if quote.expires_at < now() and not quote.is_expired:
            quote.is_expired = True
            session.add(quote)
            await session.commit()
            await session.refresh(quote)

        return {
            "quote_id": quote.id,
            "user_id": quote.user_id,
            "payment_type": quote.type,
            "fiat_amount": quote.amount_ngn,
            "crypto_asset": quote.crypto_asset,
            "crypto_amount": quote.crypto_amount,
            "network": quote.network.value if hasattr(quote.network, "value") else str(quote.network),
            "rate": quote.exchange_rate,
            "platform_fee": quote.platform_fee,
            "provider_fee": quote.provider_fee,
            "recipient_id": quote.recipient_id,
            "expires_at": quote.expires_at.isoformat(),
            "is_expired": quote.is_expired,
            "created_at": quote.created_at.isoformat() if quote.created_at else None,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to fetch quote %s: %s", quote_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch quote: {str(exc)}",
        ) from exc
