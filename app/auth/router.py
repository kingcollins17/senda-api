import logging
from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
import jwt

from app.auth.schemas import (
    AppleLoginRequest,
    AuthResponse,
    GoogleLoginRequest,
    RefreshTokenRequest,
    SendOtpRequest,
    SendOtpResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
    VerifyEmailRequest,
    VerifyOtpRequest,
    VerifyOtpResponse,
)
from app.core.database import get_session
from app.core.dependencies import get_current_user
from app.core.models.enums import AuthProvider, UserStatus
from app.core.models.user import User
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_email_verification_token,
    hash_password,
    verify_email_token,
    verify_password,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/auth",
    tags=["auth"]
)


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: UserRegisterRequest,
    session: AsyncSession = Depends(get_session),
) -> AuthResponse:
    """
    Register a new user account. Supports NORMAL (password), GOOGLE, and APPLE sign in methods.
    """
    try:
        # 1. Check if user already exists
        statement = select(User).where(User.email == payload.email)
        existing_user = (await session.exec(statement)).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this email address already exists",
            )

        # 2. Hash password for normal email signup
        pwd_hash = None
        if payload.auth_provider == AuthProvider.NORMAL:
            if not payload.password:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Password is required for standard email registration",
                )
            pwd_hash = hash_password(payload.password)

        # 3. Create user record
        is_oauth = payload.auth_provider in (AuthProvider.GOOGLE, AuthProvider.APPLE)
        user = User(
            email=payload.email,
            password_hash=pwd_hash,
            name=payload.name,
            phone=payload.phone,
            avatar_url=payload.avatar_url,
            status=UserStatus.ACTIVE,
            auth_provider=payload.auth_provider,
            email_verified=is_oauth,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        # 4. Generate JWT tokens
        token_payload = {"sub": user.id, "email": user.email}
        access_token = create_access_token(token_payload)
        refresh_token = create_refresh_token(token_payload)
        verification_token = generate_email_verification_token(user.email, user.id) if not is_oauth else None

        return AuthResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            user=UserResponse.model_validate(user),
            verification_token=verification_token,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error during user registration: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(exc)}",
        ) from exc


@router.post("/login", response_model=AuthResponse)
async def login(
    payload: UserLoginRequest,
    session: AsyncSession = Depends(get_session),
) -> AuthResponse:
    """
    Authenticate an existing user and return access & refresh tokens.
    """
    try:
        statement = select(User).where(User.email == payload.email)
        user = (await session.exec(statement)).first()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        if user.status != UserStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User account is {user.status.value.lower()}",
            )

        # For standard email/password login, verify password
        if payload.auth_provider == AuthProvider.NORMAL:
            if not payload.password or not user.password_hash or not verify_password(payload.password, user.password_hash):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid email or password",
                )
        else:
            if user.auth_provider != payload.auth_provider:
                user.auth_provider = payload.auth_provider
                session.add(user)
                await session.commit()
                await session.refresh(user)

        token_payload = {"sub": user.id, "email": user.email}
        access_token = create_access_token(token_payload)
        refresh_token = create_refresh_token(token_payload)

        return AuthResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            user=UserResponse.model_validate(user),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error during user login: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {str(exc)}",
        ) from exc


@router.post("/google", response_model=AuthResponse)
async def google_login(
    payload: GoogleLoginRequest,
    session: AsyncSession = Depends(get_session),
) -> AuthResponse:
    """
    Authenticate or register a user using Google Sign-In.
    Automatically links or provisions an account and returns JWT tokens.
    """
    try:
        statement = select(User).where(User.email == payload.email)
        user = (await session.exec(statement)).first()

        if not user:
            display_name = payload.name.strip() if payload.name else str(payload.email).split("@")[0]
            user = User(
                email=payload.email,
                name=display_name,
                avatar_url=payload.avatar_url,
                status=UserStatus.ACTIVE,
                auth_provider=AuthProvider.GOOGLE,
                email_verified=True,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
        else:
            if user.status != UserStatus.ACTIVE:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"User account is {user.status.value.lower()}",
                )
            updated = False
            if not user.email_verified:
                user.email_verified = True
                updated = True
            if payload.avatar_url and not user.avatar_url:
                user.avatar_url = payload.avatar_url
                updated = True
            if updated:
                session.add(user)
                await session.commit()
                await session.refresh(user)

        token_payload = {"sub": user.id, "email": user.email}
        access_token = create_access_token(token_payload)
        refresh_token = create_refresh_token(token_payload)

        return AuthResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            user=UserResponse.model_validate(user),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error during Google login: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Google sign-in failed: {str(exc)}",
        ) from exc


@router.post("/apple", response_model=AuthResponse)
async def apple_login(
    payload: AppleLoginRequest,
    session: AsyncSession = Depends(get_session),
) -> AuthResponse:
    """
    Authenticate or register a user using Apple Sign-In.
    Automatically links or provisions an account and returns JWT tokens.
    """
    try:
        statement = select(User).where(User.email == payload.email)
        user = (await session.exec(statement)).first()

        if not user:
            display_name = payload.name.strip() if payload.name else "Apple User"
            user = User(
                email=payload.email,
                name=display_name,
                status=UserStatus.ACTIVE,
                auth_provider=AuthProvider.APPLE,
                email_verified=True,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
        else:
            if user.status != UserStatus.ACTIVE:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"User account is {user.status.value.lower()}",
                )
            if not user.email_verified:
                user.email_verified = True
                session.add(user)
                await session.commit()
                await session.refresh(user)

        token_payload = {"sub": user.id, "email": user.email}
        access_token = create_access_token(token_payload)
        refresh_token = create_refresh_token(token_payload)

        return AuthResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            user=UserResponse.model_validate(user),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error during Apple login: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Apple sign-in failed: {str(exc)}",
        ) from exc


@router.post("/refresh", response_model=Dict[str, str])
async def refresh_token_endpoint(
    payload: RefreshTokenRequest,
    session: AsyncSession = Depends(get_session),
) -> Dict[str, str]:
    """
    Generate a new access token using a valid refresh token.
    """
    try:
        try:
            decoded = decode_token(payload.refresh_token)
            if decoded.get("type") != "refresh":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token type, refresh token required",
                )
            user_id = decoded.get("sub")
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has expired, please log in again",
            )
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )

        statement = select(User).where(User.id == user_id)
        user = (await session.exec(statement)).first()
        if not user or user.status != UserStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive",
            )

        token_payload = {"sub": user.id, "email": user.email}
        new_access_token = create_access_token(token_payload)
        new_refresh_token = create_refresh_token(token_payload)

        return {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error refreshing token: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Token refresh failed: {str(exc)}",
        ) from exc


@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user)) -> Dict[str, str]:
    """
    Logout user and invalidate authentication context.
    """
    try:
        return {"message": "Logged out successfully"}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error during logout: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Logout failed: {str(exc)}",
        ) from exc


@router.post("/send-otp", response_model=SendOtpResponse)
@router.post("/otp/send", response_model=SendOtpResponse, include_in_schema=False)
async def send_otp(
    payload: SendOtpRequest,
    session: AsyncSession = Depends(get_session),
) -> SendOtpResponse:
    """
    Mock send OTP to an email address for verification.
    """
    try:
        statement = select(User).where(User.email == payload.email)
        user = (await session.exec(statement)).first()
        logger.info("Mock OTP '123456' generated for email: %s (user registered: %s)", payload.email, user is not None)

        return SendOtpResponse(
            message="OTP sent successfully to email",
            email=str(payload.email),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error sending OTP: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send OTP: {str(exc)}",
        ) from exc


@router.post("/verify-otp", response_model=VerifyOtpResponse)
@router.post("/otp/verify", response_model=VerifyOtpResponse, include_in_schema=False)
async def verify_otp(
    payload: VerifyOtpRequest,
    session: AsyncSession = Depends(get_session),
) -> VerifyOtpResponse:
    """
    Verify OTP for an email address.
    Mocked OTP check: if OTP is '123456', marks email as verified in the database.
    """
    try:
        otp_code = (payload.otp or payload.code or "").strip()
        if not otp_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OTP code is required",
            )

        if otp_code != "123456":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid OTP",
            )

        statement = select(User).where(User.email == payload.email)
        user = (await session.exec(statement)).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        if not user.email_verified:
            user.email_verified = True
            session.add(user)
            await session.commit()
            await session.refresh(user)

        return VerifyOtpResponse(
            message="Email verified successfully",
            email=user.email,
            email_verified=True,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error verifying OTP: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OTP verification failed: {str(exc)}",
        ) from exc


@router.post("/verify-email")
async def verify_email(
    payload: VerifyEmailRequest,
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    """
    Verify user's email address via token or verification code.
    """
    try:
        user: User | None = None

        if payload.token:
            try:
                token_data = verify_email_token(payload.token)
                statement = select(User).where(User.id == token_data["user_id"])
                user = (await session.exec(statement)).first()
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(exc),
                ) from exc
        elif payload.email and payload.code:
            code_str = payload.code.strip()
            if len(code_str) < 4:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid verification code format",
                )
            if code_str != "123456":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid verification code",
                )
            statement = select(User).where(User.email == payload.email)
            user = (await session.exec(statement)).first()
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either verification 'token' or 'email' and 'code' must be provided",
            )

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        if user.email_verified:
            return {
                "message": "Email is already verified",
                "email": user.email,
                "email_verified": True,
            }

        user.email_verified = True
        session.add(user)
        await session.commit()
        await session.refresh(user)

        return {
            "message": "Email verified successfully",
            "email": user.email,
            "email_verified": True,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error verifying email: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Email verification failed: {str(exc)}",
        ) from exc

