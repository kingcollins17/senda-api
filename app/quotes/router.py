from datetime import datetime, timedelta
import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.database import get_session
from app.core.dependencies import get_user
from app.core.models.base import generate_uuid
from app.core.models.enums import Network
from app.core.models.quote import Quote
from app.core.models.recipient import Recipient
from app.core.models.user import User
from app.quotes.dependencies import (
    get_bs,
    get_bill_service,
    get_ts,
    get_transfer_service,
    bill_service,
    transfer_service,
)
from app.quotes.services import (
    BankTransferQuoteService,
    BillQuoteService,
    QuoteServiceFactory,
    QuoteValidationError,
)
from app.utils.time import now

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/quotes",
    tags=["quotes"]
)


@router.post("/transfer")
@router.post("/bank-transfer", include_in_schema=False)
async def create_transfer_quote(
    payload: Dict[str, Any],
    ts: BankTransferQuoteService = Depends(get_ts),
    current_user: User = Depends(get_user),
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    """
    Generate a price quote for bank transfer off-ramp and save it in the database.
    Requires authentication via Bearer token (get_user).
    """
    try:
        quote = ts.get_quote(payload)
        recipient_id = payload.get("recipient_id")
        if not recipient_id and isinstance(payload.get("recipient"), dict):
            recipient_id = payload["recipient"].get("recipient_id") or payload["recipient"].get("id")

        valid_recipient_id: Optional[str] = None
        if recipient_id:
            stmt = select(Recipient).where(Recipient.id == recipient_id)
            existing_recipient = (await session.exec(stmt)).first()
            if existing_recipient:
                valid_recipient_id = existing_recipient.id

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
                recipient_id=valid_recipient_id,
                expires_at=expires_at_dt,
                is_expired=False,
            )
            session.add(quote_record)
            await session.commit()
            await session.refresh(quote_record)

        quote["db_id"] = quote_record.id
        return quote
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


@router.post("/bill")
@router.post("/bills", include_in_schema=False)
async def create_bill_quote(
    payload: Dict[str, Any],
    bs: BillQuoteService = Depends(get_bs),
    current_user: User = Depends(get_user),
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    """
    Generate a price quote for bill payment (Airtime, Data, Electricity, TV) and save it in the database.
    Requires authentication via Bearer token (get_user).
    """
    try:
        quote = bs.get_quote(payload)

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
                type=str(quote.get("payment_type", "BILL_PAYMENT")),
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


@router.post("")
@router.post("/", include_in_schema=False)
async def create_quote(
    payload: Dict[str, Any],
    ts: BankTransferQuoteService = Depends(get_transfer_service),
    bs: BillQuoteService = Depends(get_bill_service),
    current_user: User = Depends(get_user),
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    """
    Generate a price quote for bank transfer or bill payment (general endpoint).
    Delegates to transfer service or bill service, and records quote in the database.
    Requires authentication via Bearer token (get_user).
    """
    quote_type = str(payload.get("type", payload.get("payment_type", "BANK_TRANSFER"))).upper()
    try:
        recipient_id: Optional[str] = None
        if quote_type in ["BILL", "BILL_PAYMENT", "AIRTIME", "DATA", "ELECTRICITY", "TV"] or "bill_details" in payload or "category" in payload:
            quote = bs.get_quote(payload)
        else:
            quote = ts.get_quote(payload)
            recipient_id = payload.get("recipient_id")
            if not recipient_id and isinstance(payload.get("recipient"), dict):
                recipient_id = payload["recipient"].get("recipient_id") or payload["recipient"].get("id")

        valid_recipient_id: Optional[str] = None
        if recipient_id:
            stmt = select(Recipient).where(Recipient.id == recipient_id)
            existing_recipient = (await session.exec(stmt)).first()
            if existing_recipient:
                valid_recipient_id = existing_recipient.id

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
                recipient_id=valid_recipient_id,
                expires_at=expires_at_dt,
                is_expired=False,
            )
            session.add(quote_record)
            await session.commit()
            await session.refresh(quote_record)

        quote["db_id"] = quote_record.id
        return quote
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

