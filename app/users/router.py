import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.auth.schemas import UserResponse
from app.common.schemas import BaseResponse
from app.core.database import get_session
from app.core.dependencies import get_current_user
from app.core.models.user import User
from app.users.schemas import UpdateUserRequest

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/users",
    tags=["users"]
)


@router.get("/me", response_model=BaseResponse[UserResponse])
async def get_user_me(current_user: User = Depends(get_current_user)) -> BaseResponse[UserResponse]:
    """
    Returns the profile of the currently authenticated user.
    """
    try:
        user_response = UserResponse.model_validate(current_user)
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

        user_response = UserResponse.model_validate(current_user)
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

