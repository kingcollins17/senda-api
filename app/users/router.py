import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.auth.schemas import UserResponse
from app.common.schemas import BaseResponse
from app.core.database import get_session
from app.core.dependencies import get_current_user
from app.core.models.user import User
from app.core.models.wallet import Wallet, WalletAccount
from app.users.schemas import UpdateUserRequest
from app.wallets.schemas import WalletAccountResponse, WalletResponse
from sqlmodel import select

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/users",
    tags=["users"]
)


async def _user_response_with_wallet(user: User, session: AsyncSession) -> UserResponse:
    wallet_stmt = select(Wallet).where(Wallet.user_id == user.id)
    wallet = (await session.exec(wallet_stmt)).first()

    user_response = UserResponse.model_validate(user)
    if wallet:
        accounts_stmt = select(WalletAccount).where(WalletAccount.wallet_id == wallet.id)
        accounts = (await session.exec(accounts_stmt)).all()
        user_response.wallet = WalletResponse(
            id=wallet.id,
            user_id=wallet.user_id,
            provider=wallet.provider,
            accounts=[WalletAccountResponse.model_validate(account) for account in accounts],
            created_at=wallet.created_at,
        )
    return user_response


@router.get("/me", response_model=BaseResponse[UserResponse])
async def get_user_me(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> BaseResponse[UserResponse]:
    """
    Returns the profile of the currently authenticated user.
    """
    try:
        user_response = await _user_response_with_wallet(current_user, session)
        return BaseResponse[UserResponse](
            detail="User profile retrieved successfully",
            data=user_response,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error retrieving user profile: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve user profile: {str(exc)}",
        ) from exc


@router.patch("/me", response_model=BaseResponse[UserResponse])
async def update_user_me(
    payload: UpdateUserRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> BaseResponse[UserResponse]:
    """
    Update the authenticated user's profile.
    Allows updating phone number and avatar URL only.
    """
    try:
        updated = False
        payload_dict = payload.model_dump(exclude_unset=True)

        if "phone" in payload_dict:
            current_user.phone = payload_dict["phone"]
            updated = True

        if "avatar_url" in payload_dict:
            current_user.avatar_url = payload_dict["avatar_url"]
            updated = True

        if updated:
            session.add(current_user)
            await session.commit()
            await session.refresh(current_user)

        user_response = await _user_response_with_wallet(current_user, session)
        return BaseResponse[UserResponse](
            detail="User profile updated successfully",
            data=user_response,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error updating user profile: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update user profile: {str(exc)}",
        ) from exc

