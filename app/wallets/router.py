import logging
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.common.schemas import BaseResponse
from app.core.database import get_session
from app.core.dependencies import get_current_user
from app.core.models.user import User
from app.core.models.wallet import Wallet, WalletAccount
from app.wallets.schemas import (
    WalletAccountResponse,
    WalletConnectRequest,
    WalletResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/wallets",
    tags=["wallets"]
)


@router.post("/connect", response_model=BaseResponse[WalletResponse], status_code=status.HTTP_201_CREATED)
async def connect_wallet(
    payload: WalletConnectRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> BaseResponse[WalletResponse]:
    """
    Attach a wallet (e.g. Phantom, MetaMask) and its associated accounts/addresses to the user.
    """
    try:
        provider_name = payload.provider.strip().lower()

        # 1. Check if user already has this wallet provider connected or create new
        statement = (
            select(Wallet)
            .where(Wallet.user_id == current_user.id)
            .where(Wallet.provider == provider_name)
        )
        wallet = (await session.exec(statement)).first()

        if not wallet:
            wallet = Wallet(
                user_id=current_user.id,
                provider=provider_name,
            )
            session.add(wallet)
            await session.commit()
            await session.refresh(wallet)

        # 2. Attach accounts/addresses to the wallet
        for account_data in payload.accounts:
            acc_stmt = (
                select(WalletAccount)
                .where(WalletAccount.wallet_id == wallet.id)
                .where(WalletAccount.network == account_data.network)
                .where(WalletAccount.address == account_data.address.strip())
            )
            existing_acc = (await session.exec(acc_stmt)).first()
            if not existing_acc:
                new_acc = WalletAccount(
                    wallet_id=wallet.id,
                    network=account_data.network,
                    address=account_data.address.strip(),
                )
                session.add(new_acc)

        await session.commit()

        # 3. Retrieve all accounts for this wallet
        accs_stmt = select(WalletAccount).where(WalletAccount.wallet_id == wallet.id)
        accounts = (await session.exec(accs_stmt)).all()

        wallet_res = WalletResponse(
            id=wallet.id,
            user_id=wallet.user_id,
            provider=wallet.provider,
            accounts=[WalletAccountResponse.model_validate(acc) for acc in accounts],
            created_at=wallet.created_at,
        )

        return BaseResponse[WalletResponse](
            detail="Wallet and accounts connected successfully",
            data=wallet_res,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error connecting wallet: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to connect wallet: {str(exc)}",
        ) from exc


@router.get("", response_model=BaseResponse[List[WalletResponse]])
async def get_wallets(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> BaseResponse[List[WalletResponse]]:
    """
    Retrieve all connected wallets and their blockchain accounts for the current user.
    """
    try:
        wallets_stmt = select(Wallet).where(Wallet.user_id == current_user.id)
        wallets = (await session.exec(wallets_stmt)).all()

        response: List[WalletResponse] = []
        for w in wallets:
            accs_stmt = select(WalletAccount).where(WalletAccount.wallet_id == w.id)
            accounts = (await session.exec(accs_stmt)).all()
            response.append(
                WalletResponse(
                    id=w.id,
                    user_id=w.user_id,
                    provider=w.provider,
                    accounts=[WalletAccountResponse.model_validate(acc) for acc in accounts],
                    created_at=w.created_at,
                )
            )

        return BaseResponse[List[WalletResponse]](
            detail="Connected wallets retrieved successfully",
            data=response,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error fetching wallets: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve wallets: {str(exc)}",
        ) from exc


@router.get("/balances", response_model=BaseResponse[Dict[str, Any]])
async def get_wallet_balances(
    current_user: User = Depends(get_current_user),
) -> BaseResponse[Dict[str, Any]]:
    """
    Returns mocked multi-chain balances for connected wallets.
    """
    try:
        balances = {
            "total_usdc": 450.70,
            "networks": [
                {
                    "network": "solana",
                    "usdc_balance": 250.00,
                },
                {
                    "network": "polygon",
                    "usdc_balance": 120.50,
                },
                {
                    "network": "ethereum",
                    "usdc_balance": 80.20,
                },
            ],
        }
        return BaseResponse[Dict[str, Any]](
            detail="Wallet balances retrieved successfully",
            data=balances,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error fetching wallet balances: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve wallet balances: {str(exc)}",
        ) from exc


@router.get("/{wallet_id}", response_model=BaseResponse[WalletResponse])
async def get_wallet(
    wallet_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> BaseResponse[WalletResponse]:
    """
    Retrieve details and accounts for a specific connected wallet.
    """
    try:
        wallet_stmt = (
            select(Wallet)
            .where(Wallet.id == wallet_id)
            .where(Wallet.user_id == current_user.id)
        )
        wallet = (await session.exec(wallet_stmt)).first()

        if not wallet:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Wallet '{wallet_id}' not found",
            )

        accs_stmt = select(WalletAccount).where(WalletAccount.wallet_id == wallet.id)
        accounts = (await session.exec(accs_stmt)).all()

        wallet_res = WalletResponse(
            id=wallet.id,
            user_id=wallet.user_id,
            provider=wallet.provider,
            accounts=[WalletAccountResponse.model_validate(acc) for acc in accounts],
            created_at=wallet.created_at,
        )

        return BaseResponse[WalletResponse](
            detail="Wallet retrieved successfully",
            data=wallet_res,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error retrieving wallet %s: %s", wallet_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve wallet: {str(exc)}",
        ) from exc


@router.delete("/{wallet_id}", response_model=BaseResponse[Dict[str, str]])
async def disconnect_wallet(
    wallet_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> BaseResponse[Dict[str, str]]:
    """
    Disconnect a wallet from the user account and remove its associated accounts.
    """
    try:
        wallet_stmt = (
            select(Wallet)
            .where(Wallet.id == wallet_id)
            .where(Wallet.user_id == current_user.id)
        )
        wallet = (await session.exec(wallet_stmt)).first()

        if not wallet:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Wallet '{wallet_id}' not found",
            )

        provider_name = wallet.provider

        # 1. Delete associated accounts
        accs_stmt = select(WalletAccount).where(WalletAccount.wallet_id == wallet.id)
        accounts = (await session.exec(accs_stmt)).all()
        for acc in accounts:
            await session.delete(acc)

        # 2. Delete wallet
        await session.delete(wallet)
        await session.commit()

        return BaseResponse[Dict[str, str]](
            detail=f"Wallet '{provider_name}' disconnected successfully",
            data={"wallet_id": wallet_id},
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error disconnecting wallet %s: %s", wallet_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to disconnect wallet: {str(exc)}",
        ) from exc


@router.get("/{wallet_id}/accounts", response_model=BaseResponse[List[WalletAccountResponse]])
async def get_wallet_accounts(
    wallet_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> BaseResponse[List[WalletAccountResponse]]:
    """
    List all blockchain accounts/addresses belonging to a specific wallet.
    """
    try:
        wallet_stmt = (
            select(Wallet)
            .where(Wallet.id == wallet_id)
            .where(Wallet.user_id == current_user.id)
        )
        wallet = (await session.exec(wallet_stmt)).first()

        if not wallet:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Wallet '{wallet_id}' not found",
            )

        accs_stmt = select(WalletAccount).where(WalletAccount.wallet_id == wallet.id)
        accounts = (await session.exec(accs_stmt)).all()

        return BaseResponse[List[WalletAccountResponse]](
            detail="Wallet accounts retrieved successfully",
            data=[WalletAccountResponse.model_validate(acc) for acc in accounts],
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error fetching accounts for wallet %s: %s", wallet_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve wallet accounts: {str(exc)}",
        ) from exc


@router.get("/{wallet_id}/accounts/{account_id}", response_model=BaseResponse[WalletAccountResponse])
async def get_wallet_account(
    wallet_id: str,
    account_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> BaseResponse[WalletAccountResponse]:
    """
    Retrieve a single specific wallet account by its ID.
    """
    try:
        wallet_stmt = (
            select(Wallet)
            .where(Wallet.id == wallet_id)
            .where(Wallet.user_id == current_user.id)
        )
        wallet = (await session.exec(wallet_stmt)).first()

        if not wallet:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Wallet '{wallet_id}' not found",
            )

        acc_stmt = (
            select(WalletAccount)
            .where(WalletAccount.id == account_id)
            .where(WalletAccount.wallet_id == wallet_id)
        )
        account = (await session.exec(acc_stmt)).first()

        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Account '{account_id}' not found in wallet '{wallet_id}'",
            )

        return BaseResponse[WalletAccountResponse](
            detail="Wallet account retrieved successfully",
            data=WalletAccountResponse.model_validate(account),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error fetching account %s for wallet %s: %s", account_id, wallet_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve wallet account: {str(exc)}",
        ) from exc
