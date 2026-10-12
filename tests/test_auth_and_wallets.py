import unittest
import uuid
from httpx import AsyncClient, ASGITransport
from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core.database import get_session
from app.core.models.enums import AuthProvider, Network

# In-memory SQLite engine for tests - fast, isolated, zero network overhead
test_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


async def override_get_session():
    async with AsyncSession(test_engine, expire_on_commit=False) as session:
        yield session



app.dependency_overrides[get_session] = override_get_session


class TestAuthAndWallets(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        async with test_engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

        self.transport = ASGITransport(app=app)
        self.client = AsyncClient(transport=self.transport, base_url="http://test")
        self.run_id = uuid.uuid4().hex[:8]

    async def asyncTearDown(self):
        await self.client.aclose()
        async with test_engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.drop_all)

    async def test_full_auth_and_wallet_lifecycle(self):
        email = f"user_{self.run_id}@example.com"
        password = "strongpassword123"
        name = "Test User"

        # 1. Register User (Normal Email/Password)
        reg_payload = {
            "email": email,
            "password": password,
            "name": name,
            "auth_provider": "NORMAL",
        }
        res_reg = await self.client.post("/api/v1/auth/register", json=reg_payload)
        self.assertEqual(res_reg.status_code, 201, res_reg.text)
        reg_data = res_reg.json()

        self.assertIn("access_token", reg_data)
        self.assertIn("refresh_token", reg_data)
        self.assertIn("verification_token", reg_data)
        self.assertEqual(reg_data["user"]["email"], email)
        self.assertEqual(reg_data["user"]["name"], name)
        self.assertEqual(reg_data["user"]["auth_provider"], "NORMAL")
        self.assertFalse(reg_data["user"]["email_verified"])

        access_token = reg_data["access_token"]
        refresh_token = reg_data["refresh_token"]
        verification_token = reg_data["verification_token"]
        auth_headers = {"Authorization": f"Bearer {access_token}"}

        # 2. Duplicate Registration Rejection
        res_dup = await self.client.post("/api/v1/auth/register", json=reg_payload)
        self.assertEqual(res_dup.status_code, 400)

        # 3. Verify Email
        res_verify = await self.client.post("/api/v1/auth/verify-email", json={"token": verification_token})
        self.assertEqual(res_verify.status_code, 200, res_verify.text)
        self.assertTrue(res_verify.json()["email_verified"])

        # 4. Get Current User (/users/me wrapped in BaseResponse[UserResponse])
        res_me = await self.client.get("/api/v1/users/me", headers=auth_headers)
        self.assertEqual(res_me.status_code, 200)
        self.assertTrue(res_me.json()["data"]["email_verified"])

        # 5. Login
        res_login = await self.client.post("/api/v1/auth/login", json={
            "email": email,
            "password": password,
            "auth_provider": "NORMAL",
        })
        self.assertEqual(res_login.status_code, 200)
        login_data = res_login.json()
        self.assertIn("access_token", login_data)

        # Login failure (wrong password)
        res_bad_login = await self.client.post("/api/v1/auth/login", json={
            "email": email,
            "password": "wrongpassword",
            "auth_provider": "NORMAL",
        })
        self.assertEqual(res_bad_login.status_code, 401)

        # 6. Refresh Token
        res_refresh = await self.client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        self.assertEqual(res_refresh.status_code, 200)
        new_access_token = res_refresh.json()["access_token"]
        new_auth_headers = {"Authorization": f"Bearer {new_access_token}"}

        # 7. Connect Wallet & Accounts (wrapped in BaseResponse[WalletResponse])
        connect_payload = {
            "provider": "phantom",
            "accounts": [
                {
                    "network": "SOLANA",
                    "address": "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
                },
                {
                    "network": "POLYGON",
                    "address": "0x71C845A00755a9562725832a8A406df7a00f8623",
                },
            ],
        }
        res_wallet = await self.client.post("/api/v1/wallets/connect", json=connect_payload, headers=new_auth_headers)
        self.assertEqual(res_wallet.status_code, 201, res_wallet.text)
        wallet_envelope = res_wallet.json()
        self.assertEqual(wallet_envelope["detail"], "Wallet and accounts connected successfully")
        wallet_data = wallet_envelope["data"]
        wallet_id = wallet_data["id"]

        self.assertEqual(wallet_data["provider"], "phantom")
        self.assertEqual(len(wallet_data["accounts"]), 2)
        first_account_id = wallet_data["accounts"][0]["id"]

        # 8. Get Connected Wallets (wrapped in BaseResponse[List[WalletResponse]])
        res_get_wallets = await self.client.get("/api/v1/wallets", headers=new_auth_headers)
        self.assertEqual(res_get_wallets.status_code, 200)
        user_wallets = res_get_wallets.json()["data"]
        self.assertGreaterEqual(len(user_wallets), 1)
        self.assertTrue(any(w["id"] == wallet_id for w in user_wallets))

        # 9. Get Specific Wallet Accounts (wrapped in BaseResponse[List[WalletAccountResponse]])
        res_accs = await self.client.get(f"/api/v1/wallets/{wallet_id}/accounts", headers=new_auth_headers)
        self.assertEqual(res_accs.status_code, 200)
        accounts_list = res_accs.json()["data"]
        self.assertEqual(len(accounts_list), 2)

        # 10. Get Single Wallet Account (wrapped in BaseResponse[WalletAccountResponse])
        res_single_acc = await self.client.get(
            f"/api/v1/wallets/{wallet_id}/accounts/{first_account_id}",
            headers=new_auth_headers,
        )
        self.assertEqual(res_single_acc.status_code, 200)
        single_acc_env = res_single_acc.json()
        self.assertEqual(single_acc_env["detail"], "Wallet account retrieved successfully")
        self.assertEqual(single_acc_env["data"]["id"], first_account_id)

        # 11. Disconnect Wallet (wrapped in BaseResponse[Dict[str, str]])
        res_disconnect = await self.client.delete(f"/api/v1/wallets/{wallet_id}", headers=new_auth_headers)
        self.assertEqual(res_disconnect.status_code, 200)
        self.assertEqual(res_disconnect.json()["data"]["wallet_id"], wallet_id)

        # 12. Verify Wallet is Disconnected
        res_check_wallet = await self.client.get(f"/api/v1/wallets/{wallet_id}", headers=new_auth_headers)
        self.assertEqual(res_check_wallet.status_code, 404)

        # 13. Logout
        res_logout = await self.client.post("/api/v1/auth/logout", headers=new_auth_headers)
        self.assertEqual(res_logout.status_code, 200)

    async def test_google_and_apple_login(self):
        # 1. Google Sign-In (First time creates account automatically)
        google_email = f"google_{self.run_id}@example.com"
        google_payload = {
            "email": google_email,
            "name": "Jane Google",
            "avatar_url": "https://example.com/avatar.png",
        }
        res_g1 = await self.client.post("/api/v1/auth/google", json=google_payload)
        self.assertEqual(res_g1.status_code, 200, res_g1.text)
        g1_data = res_g1.json()
        self.assertIn("access_token", g1_data)
        self.assertEqual(g1_data["user"]["email"], google_email)
        self.assertEqual(g1_data["user"]["auth_provider"], "GOOGLE")
        self.assertTrue(g1_data["user"]["email_verified"])

        # Subsequent Google Sign-In logs back in
        res_g2 = await self.client.post("/api/v1/auth/google", json=google_payload)
        self.assertEqual(res_g2.status_code, 200)
        self.assertEqual(res_g2.json()["user"]["id"], g1_data["user"]["id"])

        # 2. Apple Sign-In (First time creates account automatically)
        apple_email = f"apple_{self.run_id}@example.com"
        apple_payload = {
            "email": apple_email,
            "name": "John Apple",
        }
        res_a1 = await self.client.post("/api/v1/auth/apple", json=apple_payload)
        self.assertEqual(res_a1.status_code, 200, res_a1.text)
        a1_data = res_a1.json()
        self.assertIn("access_token", a1_data)
        self.assertEqual(a1_data["user"]["email"], apple_email)
        self.assertEqual(a1_data["user"]["auth_provider"], "APPLE")
        self.assertTrue(a1_data["user"]["email_verified"])


if __name__ == "__main__":
    unittest.main()
