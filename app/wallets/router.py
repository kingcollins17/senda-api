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

        # A user may connect only one wallet provider at a time.
        statement = (
            select(Wallet)
            .where(Wallet.user_id == current_user.id)
        )
        wallet = (await session.exec(statement)).first()

        if wallet and wallet.provider != provider_name:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A wallet is already connected. Disconnect it before connecting another provider.",
            )

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


@router.get("", response_model=BaseResponse[WalletResponse])
async def get_wallet(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> BaseResponse[WalletResponse]:
    """
    Retrieve connected wallet and their blockchain accounts for the current user.
    """
    try:
        wallets_stmt = select(Wallet).where(Wallet.user_id == current_user.id)
        wallet = (await session.exec(wallets_stmt)).first()

        if not wallet:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No wallets found for this user",
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
            detail="Connected wallet retrieved successfully",
            data=wallet_res,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error fetching wallet: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve wallet: {str(exc)}",
        ) from exc
                   
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


@router.get("/accounts", response_model=BaseResponse[WalletResponse])
async def get_wallet_accounts(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> BaseResponse[WalletResponse]:
    """
    Retrieve the current user's wallet and all accounts associated with it.
    """
    try:
        wallet_stmt = select(Wallet).where(Wallet.user_id == current_user.id)
        wallet = (await session.exec(wallet_stmt)).first()

        if not wallet:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No wallet is connected to this user",
            )

        accounts_stmt = select(WalletAccount).where(WalletAccount.wallet_id == wallet.id)
        accounts = (await session.exec(accounts_stmt)).all()
        wallet_res = WalletResponse(
            id=wallet.id,
            user_id=wallet.user_id,
            provider=wallet.provider,
            accounts=[WalletAccountResponse.model_validate(account) for account in accounts],
            created_at=wallet.created_at,
        )

        return BaseResponse[WalletResponse](
            detail="Wallet and accounts retrieved successfully",
            data=wallet_res,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error fetching wallet accounts for user %s: %s", current_user.id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve wallet accounts: {str(exc)}",
        ) from exc


@router.delete("", response_model=BaseResponse[Dict[str, str]])
async def disconnect_wallet(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> BaseResponse[Dict[str, str]]:
    """
    Disconnect a wallet from the user account and remove its associated accounts.
    """
    try:
        wallet_stmt = (
            select(Wallet)
            .where(Wallet.user_id == current_user.id)
        )
        wallet = (await session.exec(wallet_stmt)).first()

        if not wallet:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No wallet is connected to this user",
            )

        wallet_id = wallet.id
        provider_name = wallet.provider

        # Wallet accounts are removed by the wallet_id foreign key's ON DELETE CASCADE.
        await session.delete(wallet)
        await session.commit()

        return BaseResponse[Dict[str, str]](
            detail=f"Wallet '{provider_name}' disconnected successfully",
            data={"wallet_id": wallet_id},
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error disconnecting wallet for user %s: %s", current_user.id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to disconnect wallet: {str(exc)}",
        ) from exc

