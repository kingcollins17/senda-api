from datetime import datetime, timedelta
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.common.schemas import BaseResponse
from app.core.database import get_session
from app.core.dependencies import get_user
from app.core.models.base import generate_uuid
from app.core.models.enums import Network, OffRampOrderStatus
from app.core.models.quote import Quote
from app.core.models.ramp import OffRampOrder
from app.core.models.user import User
from app.quotes.dependencies import get_quote_service
from app.quotes.quote_service import QuoteServiceImpl, QuoteValidationError
from app.ramp.schemas import (
    BankResponse,
    FeesBreakdown,
    InitiateTransferRequest,
    InitiateTransferResponse,
    RecipientInfo,
    VerifyAccountRequest,
    VerifyAccountResponse,
)
from app.utils.time import now

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/ramp",
    tags=["ramp"]
)

NIGERIAN_BANKS_DATA = [
    {
        "name": "Access Bank",
        "code": "044",
        "slug": "access-bank",
        "logo_url": "https://assets.senda.finance/banks/044.png",
    },
    {
        "name": "Access Bank (Diamond)",
        "code": "014",
        "slug": "access-bank-diamond",
        "logo_url": "https://assets.senda.finance/banks/014.png",
    },
    {
        "name": "Citibank",
        "code": "023",
        "slug": "citibank",
        "logo_url": "https://assets.senda.finance/banks/023.png",
    },
    {
        "name": "Ecobank Nigeria",
        "code": "050",
        "slug": "ecobank-nigeria",
        "logo_url": "https://assets.senda.finance/banks/050.png",
    },
    {
        "name": "Fidelity Bank",
        "code": "070",
        "slug": "fidelity-bank",
        "logo_url": "https://assets.senda.finance/banks/070.png",
    },
    {
        "name": "First Bank of Nigeria",
        "code": "011",
        "slug": "first-bank-of-nigeria",
        "logo_url": "https://assets.senda.finance/banks/011.png",
    },
    {
        "name": "First City Monument Bank",
        "code": "214",
        "slug": "first-city-monument-bank",
        "logo_url": "https://assets.senda.finance/banks/214.png",
    },
    {
        "name": "Guaranty Trust Bank",
        "code": "058",
        "slug": "guaranty-trust-bank",
        "logo_url": "https://assets.senda.finance/banks/058.png",
    },
    {
        "name": "Heritage Bank",
        "code": "030",
        "slug": "heritage-bank",
        "logo_url": "https://assets.senda.finance/banks/030.png",
    },
    {
        "name": "Jaiz Bank",
        "code": "301",
        "slug": "jaiz-bank",
        "logo_url": "https://assets.senda.finance/banks/301.png",
    },
    {
        "name": "Keystone Bank",
        "code": "082",
        "slug": "keystone-bank",
        "logo_url": "https://assets.senda.finance/banks/082.png",
    },
    {
        "name": "Kuda Bank",
        "code": "50211",
        "slug": "kuda-bank",
        "logo_url": "https://assets.senda.finance/banks/50211.png",
    },
    {
        "name": "Moniepoint MFB",
        "code": "561",
        "slug": "moniepoint-mfb",
        "logo_url": "https://assets.senda.finance/banks/561.png",
    },
    {
        "name": "OPay",
        "code": "999992",
        "slug": "opay",
        "logo_url": "https://assets.senda.finance/banks/999992.png",
    },
    {
        "name": "Parallex Bank",
        "code": "526",
        "slug": "parallex-bank",
        "logo_url": "https://assets.senda.finance/banks/526.png",
    },
    {
        "name": "Polaris Bank",
        "code": "076",
        "slug": "polaris-bank",
        "logo_url": "https://assets.senda.finance/banks/076.png",
    },
    {
        "name": "Providus Bank",
        "code": "101",
        "slug": "providus-bank",
        "logo_url": "https://assets.senda.finance/banks/101.png",
    },
    {
        "name": "Stanbic IBTC Bank",
        "code": "221",
        "slug": "stanbic-ibtc-bank",
        "logo_url": "https://assets.senda.finance/banks/221.png",
    },
    {
        "name": "Standard Chartered Bank",
        "code": "068",
        "slug": "standard-chartered-bank",
        "logo_url": "https://assets.senda.finance/banks/068.png",
    },
    {
        "name": "Sterling Bank",
        "code": "232",
        "slug": "sterling-bank",
        "logo_url": "https://assets.senda.finance/banks/232.png",
    },
    {
        "name": "Suntrust Bank",
        "code": "100",
        "slug": "suntrust-bank",
        "logo_url": "https://assets.senda.finance/banks/100.png",
    },
    {
        "name": "TAJ Bank",
        "code": "302",
        "slug": "taj-bank",
        "logo_url": "https://assets.senda.finance/banks/302.png",
    },
    {
        "name": "Union Bank of Nigeria",
        "code": "032",
        "slug": "union-bank-of-nigeria",
        "logo_url": "https://assets.senda.finance/banks/032.png",
    },
    {
        "name": "United Bank for Africa",
        "code": "033",
        "slug": "united-bank-for-africa",
        "logo_url": "https://assets.senda.finance/banks/033.png",
    },
    {
        "name": "Unity Bank",
        "code": "215",
        "slug": "unity-bank",
        "logo_url": "https://assets.senda.finance/banks/215.png",
    },
    {
        "name": "Wema Bank",
        "code": "035",
        "slug": "wema-bank",
        "logo_url": "https://assets.senda.finance/banks/035.png",
    },
    {
        "name": "Zenith Bank",
        "code": "057",
        "slug": "zenith-bank",
        "logo_url": "https://assets.senda.finance/banks/057.png",
    },
]

NIGERIAN_BANKS = {b["code"]: b["name"] for b in NIGERIAN_BANKS_DATA}



def _format_payment_response(
    order: OffRampOrder,
    quote: Optional[Quote] = None,
    quote_payload: Optional[Dict[str, Any]] = None,
) -> InitiateTransferResponse:
    """Helper to assemble standard InitiateTransferResponse model for user payment."""
    network_val = order.network.value if hasattr(order.network, "value") else str(order.network)
    status_val = order.status.value if hasattr(order.status, "value") else str(order.status)

    rate = quote.exchange_rate if quote else (quote_payload.get("rate") if quote_payload else None)
    platform_fee = quote.platform_fee if quote else (
        quote_payload.get("fees", {}).get("platform_fee_ngn", 0.0) if quote_payload else 0.0
    )
    provider_fee = quote.provider_fee if quote else (
        quote_payload.get("fees", {}).get("provider_fee_ngn", 0.0) if quote_payload else 0.0
    )
    total_fee = platform_fee + provider_fee
    total_fiat = order.fiat_amount + total_fee

    expires_at_str = None
    if quote and quote.expires_at:
        expires_at_str = quote.expires_at.isoformat()
    elif quote_payload and quote_payload.get("expires_at"):
        expires_at_str = str(quote_payload["expires_at"])

    is_expired = False
    if quote:
        is_expired = quote.is_expired or (quote.expires_at < now())

    blockchain_meta = {}
    if quote_payload and "blockchain_metadata" in quote_payload:
        blockchain_meta = quote_payload["blockchain_metadata"]

    fees = FeesBreakdown(
        platform_fee_ngn=platform_fee,
        provider_fee_ngn=provider_fee,
        total_fee_ngn=total_fee,
        total_fiat_amount=total_fiat,
    )

    recipient = RecipientInfo(
        account_number=order.recipient_account_number,
        bank_code=order.recipient_bank_code,
        bank_name=order.recipient_bank_name,
        account_name=order.recipient_account_name,
    )

    return InitiateTransferResponse(
        order_id=order.id,
        quote_id=order.quote_id or (quote.id if quote else None),
        idempotency_key=order.idempotency_key,
        status=status_val,
        payment_type=quote.type if quote else "BANK_TRANSFER",
        fiat_currency=order.fiat_currency,
        fiat_amount=order.fiat_amount,
        crypto_asset=order.crypto_asset,
        crypto_amount=order.crypto_amount,
        network=network_val,
        wallet_address=order.provider_deposit_address,
        deposit_address=order.provider_deposit_address,
        rate=rate,
        platform_fee=platform_fee,
        provider_fee=provider_fee,
        fees=fees,
        recipient=recipient,
        expires_at=expires_at_str,
        is_expired=is_expired,
        blockchain_metadata=blockchain_meta,
        created_at=order.created_at.isoformat() if order.created_at else None,
        meta_data=order.meta_data,
    )


# =============================================================================
# Banks Listing Endpoint
# =============================================================================

@router.get(
    "/banks",
    response_model=BaseResponse[List[BankResponse]],
    status_code=status.HTTP_200_OK,
)
@router.get(
    "/banks/list",
    response_model=BaseResponse[List[BankResponse]],
    include_in_schema=False,
    status_code=status.HTTP_200_OK,
)
async def list_banks(
    q: Optional[str] = Query(None, description="Optional search query to filter banks by name or code"),
) -> BaseResponse[List[BankResponse]]:
    """
    List supported Nigerian banks with their bank code and logo URL.
    Optionally filter by name or code.
    """
    banks = [
        BankResponse(
            name=b["name"],
            code=b["code"],
            bank_code=b["code"],
            logo_url=b["logo_url"],
            slug=b.get("slug"),
        )
        for b in NIGERIAN_BANKS_DATA
    ]
    if q:
        query_str = q.strip().lower()
        banks = [
            b for b in banks
            if query_str in b.name.lower() or query_str in b.code.lower() or (b.slug and query_str in b.slug.lower())
        ]
    return BaseResponse[List[BankResponse]](
        detail="Banks retrieved successfully",
        data=banks,
    )


# =============================================================================
# Account Verification Endpoint
# =============================================================================


@router.post(
    "/verify",
    response_model=BaseResponse[VerifyAccountResponse],
    status_code=status.HTTP_200_OK,
)
@router.post(
    "/verify-account",
    response_model=BaseResponse[VerifyAccountResponse],
    include_in_schema=False,
    status_code=status.HTTP_200_OK,
)
async def verify_account(
    payload: VerifyAccountRequest,
) -> BaseResponse[VerifyAccountResponse]:
    """
    Verify a recipient's Nigerian bank account by account number and bank code.
    Returns full account information including fullname, bank_code, bank_name, and account_number.
    """
    account_number = payload.account_number.strip()
    bank_code = payload.bank_code.strip()

    if not (account_number.isdigit() and len(account_number) == 10):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid bank account number '{account_number}'. Nigerian NUBAN account number must be 10 digits.",
        )

    if not bank_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bank code is required",
        )

    bank_name = NIGERIAN_BANKS.get(bank_code, f"Bank ({bank_code})")
    fullname = "John Doe"

    result_data = VerifyAccountResponse(
        fullname=fullname,
        account_name=fullname,
        bank_code=bank_code,
        bank_name=bank_name,
        account_number=account_number,
    )

    return BaseResponse[VerifyAccountResponse](
        detail="Account verified successfully",
        data=result_data,
    )


# =============================================================================
# Transfer Initiation Endpoint
# =============================================================================

@router.post(
    "/transfer",
    response_model=BaseResponse[InitiateTransferResponse],
    status_code=status.HTTP_200_OK,
)
@router.post(
    "/initiate-transfer",
    response_model=BaseResponse[InitiateTransferResponse],
    include_in_schema=False,
    status_code=status.HTTP_200_OK,
)
async def initiate_transfer(
    payload: InitiateTransferRequest,
    idempotency_key_header: Optional[str] = Header(None, alias="Idempotency-Key"),
    x_idempotency_key_header: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    current_user: User = Depends(get_user),
    service: QuoteServiceImpl = Depends(get_quote_service),
    session: AsyncSession = Depends(get_session),
) -> BaseResponse[InitiateTransferResponse]:
    """
    Initiate an off-ramp bank transfer.
    
    Flow:
    1. Check idempotency: If order exists for idempotency key, fetch the associated quote from DB and return payment details.
    2. Convert amount if in a non-NGN currency (default is NGN).
    3. Call get_quote from quote service.
    4. Store the quote in DB.
    5. Create an off ramp order.
    6. Return relevant details from quote for the user to make crypto payment.
    """
    try:
        # 1. Resolve idempotency key from header
        idempotency_key = idempotency_key_header or x_idempotency_key_header
        if idempotency_key:
            idempotency_key = str(idempotency_key).strip()
            # Check if order already exists for this idempotency key
            stmt = select(OffRampOrder).where(
                OffRampOrder.idempotency_key == idempotency_key,
                OffRampOrder.user_id == current_user.id,
            )
            existing_order = (await session.exec(stmt)).first()
            if existing_order:
                # Order exists: fetch associated quote from DB
                quote_stmt = select(Quote).where(Quote.id == existing_order.quote_id)
                existing_quote = (await session.exec(quote_stmt)).first()
                resp_data = _format_payment_response(order=existing_order, quote=existing_quote)
                return BaseResponse[InitiateTransferResponse](
                    detail="Transfer fetched from existing idempotent order",
                    data=resp_data,
                )

        # 2. Extract amount and currency (default NGN)
        currency = payload.currency.upper().strip()
        effective_amount = payload.amount
        if effective_amount <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Amount must be a positive number",
            )

        crypto_asset = payload.token.upper().strip()
        network_enum = payload.network

        # Currency conversion to NGN if specified in USD/USDC
        if currency == "NGN":
            amount_ngn = effective_amount
        elif currency in ["USD", "USDC"]:
            rate_getter = getattr(service, "get_exchange_rate", getattr(service, "_get_exchange_rate", None))
            rate = rate_getter(token=crypto_asset, network=network_enum.value) if rate_getter else 1500.0
            amount_ngn = effective_amount * rate
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported currency '{currency}'. Supported currencies: NGN, USD, USDC.",
            )

        # 3. Resolve recipient details
        acc_num_str = payload.recipient.account_number.strip()
        bank_code_str = payload.recipient.bank_code.strip()
        bank_name = payload.recipient.bank_name or NIGERIAN_BANKS.get(bank_code_str, f"Bank ({bank_code_str})")
        account_name = payload.recipient.account_name or payload.recipient.fullname or "John Doe"
        recipient_id = payload.recipient.recipient_id

        # 4. Call get_quote from quote service
        quote_request = {
            "amount_ngn": amount_ngn,
            "network": network_enum.value,
            "token": crypto_asset,
            "payment_type": "BANK_TRANSFER",
            "account_number": acc_num_str,
            "bank_code": bank_code_str,
            "bank_name": bank_name,
            "account_name": account_name,
            "recipient_id": recipient_id,
        }
        quote_dict = service.get_quote(quote_request)

        # 5. Store the quote in DB
        raw_expires = quote_dict.get("expires_at")
        if isinstance(raw_expires, str):
            expires_at_dt = datetime.fromisoformat(raw_expires)
            if expires_at_dt.tzinfo is not None:
                expires_at_dt = expires_at_dt.replace(tzinfo=None)
        elif isinstance(raw_expires, datetime):
            expires_at_dt = raw_expires.replace(tzinfo=None) if raw_expires.tzinfo else raw_expires
        else:
            expires_at_dt = now() + timedelta(seconds=int(quote_dict.get("validity_seconds", 900)))

        fees_dict = quote_dict.get("fees", {})
        platform_fee = float(fees_dict.get("platform_fee_ngn", 0.0))
        provider_fee = float(fees_dict.get("provider_fee_ngn", 0.0))

        quote_id = str(quote_dict.get("quote_id") or generate_uuid())
        quote_record = Quote(
            id=quote_id,
            user_id=current_user.id,
            type=str(quote_dict.get("payment_type", "BANK_TRANSFER")),
            amount_ngn=float(quote_dict.get("fiat_amount", amount_ngn)),
            crypto_asset=str(quote_dict.get("token", crypto_asset)),
            crypto_amount=float(quote_dict.get("amount", 0.0)),
            network=network_enum,
            exchange_rate=float(quote_dict.get("rate", 1500.0)),
            platform_fee=platform_fee,
            provider_fee=provider_fee,
            recipient_id=recipient_id,
            expires_at=expires_at_dt,
            is_expired=False,
        )
        session.add(quote_record)
        await session.commit()
        await session.refresh(quote_record)

        # 6. Create off-ramp order
        order = OffRampOrder(
            user_id=current_user.id,
            quote_id=quote_record.id,
            status=OffRampOrderStatus.CREATED,
            fiat_currency=currency,
            fiat_amount=amount_ngn,
            crypto_asset=quote_record.crypto_asset,
            crypto_amount=quote_record.crypto_amount,
            network=network_enum,
            provider_deposit_address=quote_dict.get("wallet_address"),
            provider_reference=quote_dict.get("provider_reference"),
            recipient_id=recipient_id,
            recipient_bank_name=bank_name,
            recipient_account_number=acc_num_str,
            recipient_account_name=account_name,
            recipient_bank_code=bank_code_str,
            wallet_account_id=None,
            user_wallet_address=None,
            idempotency_key=idempotency_key,
            meta_data=None,
        )
        session.add(order)
        await session.commit()
        await session.refresh(order)

        # 7. Return relevant details from quote endpoint wrapped in BaseResponse
        resp_data = _format_payment_response(order=order, quote=quote_record, quote_payload=quote_dict)
        return BaseResponse[InitiateTransferResponse](
            detail="Transfer initiated successfully",
            data=resp_data,
        )

    except HTTPException:
        raise
    except QuoteValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Failed to initiate transfer: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Transfer initiation failed: {str(exc)}",
        ) from exc
