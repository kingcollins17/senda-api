import unittest
import uuid
from httpx import AsyncClient, ASGITransport
from sqlmodel import SQLModel, select
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core.database import get_session
from app.core.dependencies import get_user, get_current_user
from app.core.models.enums import AuthProvider, Network, UserStatus
from app.core.models.quote import Quote
from app.core.models.user import User
from app.quotes.dependencies import (
    get_quote_service,
    get_ts,
    get_bs,
    get_transfer_service,
    get_bill_service,
    quote_service,
    transfer_service,
    bill_service,
)
from app.quotes.quote_service import QuoteServiceImpl

test_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


async def override_get_session():
    async with AsyncSession(test_engine, expire_on_commit=False) as session:
        yield session


class TestQuotesAndOtp(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        async with test_engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

        app.dependency_overrides[get_session] = override_get_session
        self.transport = ASGITransport(app=app)
        self.client = AsyncClient(transport=self.transport, base_url="http://test")
        self.run_id = uuid.uuid4().hex[:8]

    async def asyncTearDown(self):
        app.dependency_overrides.clear()
        await self.client.aclose()
        async with test_engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.drop_all)

    # =========================================================================
    # Dependency Injection Functions Tests
    # =========================================================================

    def test_quote_dependency_providers(self):
        """Verify get_quote_service, get_ts, get_bs, get_transfer_service, and get_bill_service return QuoteServiceImpl instances."""
        qs = get_quote_service()
        self.assertIsInstance(qs, QuoteServiceImpl)

        ts = get_ts()
        self.assertIsInstance(ts, QuoteServiceImpl)

        bs = get_bs()
        self.assertIsInstance(bs, QuoteServiceImpl)

        ts_full = get_transfer_service()
        self.assertIsInstance(ts_full, QuoteServiceImpl)

        bs_full = get_bill_service()
        self.assertIsInstance(bs_full, QuoteServiceImpl)

        self.assertEqual(quote_service, get_quote_service)
        self.assertEqual(transfer_service, get_quote_service)
        self.assertEqual(bill_service, get_quote_service)

    # =========================================================================
    # Quotes Split Endpoints & Authorization Tests
    # =========================================================================

    async def _create_test_user_and_token(self, email_suffix: str = "1") -> tuple[User, dict[str, str]]:
        email = f"quote_user_{self.run_id}_{email_suffix}@example.com"
        reg_payload = {
            "email": email,
            "password": "strongPassword123!",
            "name": "Quote User",
            "auth_provider": "NORMAL",
        }
        res_reg = await self.client.post("/api/v1/auth/register", json=reg_payload)
        self.assertEqual(res_reg.status_code, 201, res_reg.text)
        token = res_reg.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        async with AsyncSession(test_engine) as session:
            stmt = select(User).where(User.email == email)
            user = (await session.exec(stmt)).first()
            self.assertIsNotNone(user)

        return user, headers

    async def test_unauthorized_quote_endpoints_rejection(self):
        """Endpoints /transfer, /bill, and general /quotes must require authorization."""
        res_transfer = await self.client.post("/api/v1/quotes/transfer", json={})
        self.assertEqual(res_transfer.status_code, 401)

        res_bill = await self.client.post("/api/v1/quotes/bill", json={})
        self.assertEqual(res_bill.status_code, 401)

        res_general = await self.client.post("/api/v1/quotes", json={})
        self.assertEqual(res_general.status_code, 401)

        res_get = await self.client.get("/api/v1/quotes/quote_nonexistent")
        self.assertEqual(res_get.status_code, 401)

    async def test_create_transfer_quote_and_database_persistence(self):
        """Test POST /api/v1/quotes/transfer generates quote and records it in DB."""
        user, headers = await self._create_test_user_and_token("transfer")

        payload = {
            "amount_ngn": 30000,
            "network": "SOLANA",
            "token": "USDC",
            "recipient": {
                "account_number": "0123456789",
                "bank_code": "058",
                "bank_name": "Guaranty Trust Bank",
                "account_name": "John Doe",
            },
        }

        res = await self.client.post("/api/v1/quotes/transfer", json=payload, headers=headers)
        self.assertEqual(res.status_code, 200, res.text)
        data = res.json()

        self.assertIn("quote_id", data)
        self.assertEqual(data["payment_type"], "BANK_TRANSFER")
        self.assertEqual(data["fiat_amount"], 30000.0)
        self.assertEqual(data["network"], "SOLANA")
        self.assertEqual(data["token"], "USDC")
        self.assertIn("wallet_address", data)
        self.assertIn("db_id", data)

        quote_id = data["quote_id"]

        # Verify quote is persisted in database with correct user_id
        async with AsyncSession(test_engine) as session:
            stmt = select(Quote).where(Quote.id == quote_id)
            saved_quote = (await session.exec(stmt)).first()
            self.assertIsNotNone(saved_quote)
            self.assertEqual(saved_quote.user_id, user.id)
            self.assertEqual(saved_quote.amount_ngn, 30000.0)
            self.assertEqual(saved_quote.network, Network.SOLANA)
            self.assertEqual(saved_quote.crypto_asset, "USDC")
            self.assertFalse(saved_quote.is_expired)

        # Verify GET /api/v1/quotes/{quote_id}
        res_get = await self.client.get(f"/api/v1/quotes/{quote_id}", headers=headers)
        self.assertEqual(res_get.status_code, 200, res_get.text)
        get_data = res_get.json()
        self.assertEqual(get_data["quote_id"], quote_id)
        self.assertEqual(get_data["user_id"], user.id)
        self.assertEqual(get_data["fiat_amount"], 30000.0)

    async def test_create_bill_quote_and_database_persistence(self):
        """Test POST /api/v1/quotes/bill generates quote and records it in DB."""
        user, headers = await self._create_test_user_and_token("bill")

        payload = {
            "amount_ngn": 5000,
            "network": "POLYGON",
            "token": "USDT",
            "category": "AIRTIME",
            "customer_id": "08012345678",
            "biller_name": "MTN",
        }

        res = await self.client.post("/api/v1/quotes/bill", json=payload, headers=headers)
        self.assertEqual(res.status_code, 200, res.text)
        data = res.json()

        self.assertIn("quote_id", data)
        self.assertEqual(data["payment_type"], "AIRTIME")
        self.assertEqual(data["fiat_amount"], 5000.0)
        self.assertEqual(data["network"], "POLYGON")
        self.assertEqual(data["token"], "USDT")
        self.assertIn("db_id", data)

        quote_id = data["quote_id"]

        # Verify quote persisted in DB
        async with AsyncSession(test_engine) as session:
            stmt = select(Quote).where(Quote.id == quote_id)
            saved_quote = (await session.exec(stmt)).first()
            self.assertIsNotNone(saved_quote)
            self.assertEqual(saved_quote.user_id, user.id)
            self.assertEqual(saved_quote.amount_ngn, 5000.0)
            self.assertEqual(saved_quote.type, "AIRTIME")
            self.assertEqual(saved_quote.network, Network.POLYGON)

    async def test_quote_validation_errors(self):
        """Test validation error handling on transfer and bill endpoints."""
        _, headers = await self._create_test_user_and_token("validation")

        # Invalid transfer (missing recipient)
        res_bad_transfer = await self.client.post(
            "/api/v1/quotes/transfer",
            json={"amount_ngn": 10000, "network": "SOLANA"},
            headers=headers,
        )
        self.assertEqual(res_bad_transfer.status_code, 400)

        # Invalid bill (missing customer_id)
        res_bad_bill = await self.client.post(
            "/api/v1/quotes/bill",
            json={"amount_ngn": 10000, "network": "SOLANA", "category": "ELECTRICITY"},
            headers=headers,
        )
        self.assertEqual(res_bad_bill.status_code, 400)

    async def test_quote_user_isolation(self):
        """User B cannot fetch User A's quote."""
        user_a, headers_a = await self._create_test_user_and_token("user_a")
        user_b, headers_b = await self._create_test_user_and_token("user_b")

        payload = {
            "amount_ngn": 20000,
            "network": "SOLANA",
            "recipient": {
                "account_number": "0123456789",
                "bank_code": "058",
                "bank_name": "Guaranty Trust Bank",
                "account_name": "User A",
            },
        }

        res = await self.client.post("/api/v1/quotes/transfer", json=payload, headers=headers_a)
        self.assertEqual(res.status_code, 200)
        quote_id = res.json()["quote_id"]

        # User A can fetch quote
        res_get_a = await self.client.get(f"/api/v1/quotes/{quote_id}", headers=headers_a)
        self.assertEqual(res_get_a.status_code, 200)

        # User B cannot fetch User A's quote
        res_get_b = await self.client.get(f"/api/v1/quotes/{quote_id}", headers=headers_b)
        self.assertEqual(res_get_b.status_code, 404)

    # =========================================================================
    # Auth OTP Endpoints Tests
    # =========================================================================

    async def test_send_and_verify_otp_flow(self):
        """Test sending OTP and verifying it with '123456' to verify email."""
        email = f"otp_test_{self.run_id}@example.com"
        reg_payload = {
            "email": email,
            "password": "securePassword123!",
            "name": "OTP User",
            "auth_provider": "NORMAL",
        }
        res_reg = await self.client.post("/api/v1/auth/register", json=reg_payload)
        self.assertEqual(res_reg.status_code, 201)
        reg_data = res_reg.json()
        self.assertFalse(reg_data["user"]["email_verified"])

        # 1. Send OTP
        res_send = await self.client.post("/api/v1/auth/send-otp", json={"email": email})
        self.assertEqual(res_send.status_code, 200, res_send.text)
        self.assertIn("OTP sent successfully", res_send.json()["message"])

        # 2. Verify with wrong OTP -> Rejected
        res_wrong = await self.client.post("/api/v1/auth/verify-otp", json={
            "email": email,
            "otp": "999999",
        })
        self.assertEqual(res_wrong.status_code, 400)
        self.assertIn("Invalid OTP", res_wrong.json()["detail"])

        # 3. Verify with valid mock OTP '123456' -> Success
        res_verify = await self.client.post("/api/v1/auth/verify-otp", json={
            "email": email,
            "otp": "123456",
        })
        self.assertEqual(res_verify.status_code, 200, res_verify.text)
        verify_data = res_verify.json()
        self.assertTrue(verify_data["email_verified"])
        self.assertEqual(verify_data["email"], email)

        # 4. Verify user in database is now marked email_verified
        async with AsyncSession(test_engine) as session:
            stmt = select(User).where(User.email == email)
            user = (await session.exec(stmt)).first()
            self.assertIsNotNone(user)
            self.assertTrue(user.email_verified)

    async def test_verify_otp_nonexistent_user(self):
        """Verify OTP for non-existent user returns 404."""
        res = await self.client.post("/api/v1/auth/verify-otp", json={
            "email": "nobody@example.com",
            "otp": "123456",
        })
        self.assertEqual(res.status_code, 404)

    async def test_verify_email_with_123456_code(self):
        """Verify POST /api/v1/auth/verify-email also accepts mock code '123456'."""
        email = f"code_test_{self.run_id}@example.com"
        reg_payload = {
            "email": email,
            "password": "securePassword123!",
            "name": "Code User",
            "auth_provider": "NORMAL",
        }
        await self.client.post("/api/v1/auth/register", json=reg_payload)

        # Wrong code
        res_wrong = await self.client.post("/api/v1/auth/verify-email", json={
            "email": email,
            "code": "888888",
        })
        self.assertEqual(res_wrong.status_code, 400)

        # Correct code 123456
        res_correct = await self.client.post("/api/v1/auth/verify-email", json={
            "email": email,
            "code": "123456",
        })
        self.assertEqual(res_correct.status_code, 200)
        self.assertTrue(res_correct.json()["email_verified"])

    # =========================================================================
    # User Profile Update (PATCH /me) Tests
    # =========================================================================

    async def test_update_user_me_phone_and_avatar_only(self):
        """Test PATCH /api/v1/users/me allows updating phone and avatar_url only."""
        user, headers = await self._create_test_user_and_token("patch_me")

        # 1. Unauthenticated -> 401
        res_unauth = await self.client.patch("/api/v1/users/me", json={"phone": "+2348011112222"})
        self.assertEqual(res_unauth.status_code, 401)

        # 2. Update phone number only
        res_phone = await self.client.patch(
            "/api/v1/users/me",
            json={"phone": "+2348011112222"},
            headers=headers,
        )
        self.assertEqual(res_phone.status_code, 200, res_phone.text)
        data_phone = res_phone.json()
        self.assertEqual(data_phone["detail"], "User profile updated successfully")
        self.assertEqual(data_phone["data"]["phone"], "+2348011112222")
        self.assertIsNone(data_phone["data"]["avatar_url"])

        # 3. Update avatar URL only
        res_avatar = await self.client.patch(
            "/api/v1/users/me",
            json={"avatar_url": "https://example.com/avatar.png"},
            headers=headers,
        )
        self.assertEqual(res_avatar.status_code, 200, res_avatar.text)
        data_avatar = res_avatar.json()
        self.assertEqual(data_avatar["data"]["avatar_url"], "https://example.com/avatar.png")
        self.assertEqual(data_avatar["data"]["phone"], "+2348011112222")

        # 4. Update both phone and avatar URL
        res_both = await self.client.patch(
            "/api/v1/users/me",
            json={
                "phone": "+2349099998888",
                "avatar_url": "https://example.com/new-avatar.jpg",
            },
            headers=headers,
        )
        self.assertEqual(res_both.status_code, 200, res_both.text)
        data_both = res_both.json()
        self.assertEqual(data_both["data"]["phone"], "+2349099998888")
        self.assertEqual(data_both["data"]["avatar_url"], "https://example.com/new-avatar.jpg")

        # Verify persisted in database
        async with AsyncSession(test_engine) as session:
            stmt = select(User).where(User.id == user.id)
            refreshed_user = (await session.exec(stmt)).first()
            self.assertEqual(refreshed_user.phone, "+2349099998888")
            self.assertEqual(refreshed_user.avatar_url, "https://example.com/new-avatar.jpg")

        # 5. Reject updating other fields (extra="forbid") -> 422
        res_invalid = await self.client.patch(
            "/api/v1/users/me",
            json={"name": "Hacker Name"},
            headers=headers,
        )
        self.assertEqual(res_invalid.status_code, 422)

        res_invalid_email = await self.client.patch(
            "/api/v1/users/me",
            json={"email": "hacker@example.com"},
            headers=headers,
        )
        self.assertEqual(res_invalid_email.status_code, 422)


if __name__ == "__main__":
    unittest.main()
