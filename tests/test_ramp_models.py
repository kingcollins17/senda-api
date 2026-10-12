import unittest
import uuid
from httpx import AsyncClient, ASGITransport
from sqlmodel import SQLModel, select
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core.database import get_session
from app.core.dependencies import get_user
from app.core.models.enums import BillCategory, Network, OffRampOrderStatus, OnRampOrderStatus, TransactionType, TransactionStatus
from app.core.models.user import User
from app.core.models.bill import BillOrder
from app.core.models.ramp import OnRampOrder, OffRampOrder
from app.core.models.quote import Quote
from app.core.models.transaction import Transaction
from app.core.models.notification import Notification

test_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


async def override_get_session():
    async with AsyncSession(test_engine, expire_on_commit=False) as session:
        yield session


class TestRampModelsAndEndpoints(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        async with test_engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

        app.dependency_overrides[get_session] = override_get_session
        self.transport = ASGITransport(app=app)
        self.client = AsyncClient(transport=self.transport, base_url="http://test")

    async def asyncTearDown(self):
        app.dependency_overrides.clear()
        await self.client.aclose()
        async with test_engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.drop_all)

    async def _create_test_user(self) -> User:
        async with AsyncSession(test_engine, expire_on_commit=False) as session:
            user = User(
                email=f"user_{uuid.uuid4().hex[:6]}@example.com",
                phone="+2348012345678",
                name="Test User",
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return user

    # =========================================================================
    # Model Tests
    # =========================================================================

    async def test_meta_data_json_fields_on_models(self):
        async with AsyncSession(test_engine, expire_on_commit=False) as session:
            user = await self._create_test_user()

            # BillOrder meta_data
            bill = BillOrder(
                user_id=user.id,
                category=BillCategory.AIRTIME,
                fiat_amount=1000.0,
                crypto_amount=0.67,
                network=Network.SOLANA,
                meta_data={"biller": "MTN", "extra_notes": "Bonus applied"},
            )
            session.add(bill)

            # OnRampOrder meta_data
            onramp = OnRampOrder(
                user_id=user.id,
                fiat_amount=25000.0,
                crypto_amount=16.67,
                network=Network.SOLANA,
                meta_data={"channel": "direct_transfer", "user_tier": 2},
            )
            session.add(onramp)

            # OffRampOrder meta_data
            offramp = OffRampOrder(
                user_id=user.id,
                fiat_amount=50000.0,
                crypto_amount=33.33,
                network=Network.SOLANA,
                meta_data={"source": "mobile_app", "tags": ["salary", "quick"]},
            )
            session.add(offramp)

            # Transaction meta_data
            tx = Transaction(
                user_id=user.id,
                type=TransactionType.OFFRAMP,
                status=TransactionStatus.COMPLETED,
                fiat_amount=50000.0,
                crypto_amount=33.33,
                network=Network.SOLANA,
                exchange_rate=1500.0,
                meta_data={"ip_address": "127.0.0.1", "device": "iPhone 15"},
            )
            session.add(tx)

            # Notification channels
            notif = Notification(
                user_id=user.id,
                title="Transfer update",
                body="Your transfer is processing",
                channels=["push", "email", "sms"],
            )
            session.add(notif)

            await session.commit()

            await session.refresh(bill)
            await session.refresh(onramp)
            await session.refresh(offramp)
            await session.refresh(tx)
            await session.refresh(notif)

            self.assertEqual(bill.meta_data, {"biller": "MTN", "extra_notes": "Bonus applied"})
            self.assertEqual(onramp.meta_data, {"channel": "direct_transfer", "user_tier": 2})
            self.assertEqual(offramp.meta_data, {"source": "mobile_app", "tags": ["salary", "quick"]})
            self.assertEqual(tx.meta_data, {"ip_address": "127.0.0.1", "device": "iPhone 15"})
            self.assertEqual(notif.channels, ["push", "email", "sms"])

    # =========================================================================
    # Banks Listing Endpoint Tests
    # =========================================================================

    async def test_list_banks_success(self):
        res = await self.client.get("/api/v1/ramp/banks")
        self.assertEqual(res.status_code, 200, res.text)
        res_json = res.json()
        self.assertEqual(res_json["detail"], "Banks retrieved successfully")
        banks = res_json["data"]
        self.assertIsInstance(banks, list)
        self.assertGreater(len(banks), 20)

        # Verify bank structure
        gtb = next((b for b in banks if b["code"] == "058"), None)
        self.assertIsNotNone(gtb)
        self.assertEqual(gtb["name"], "Guaranty Trust Bank")
        self.assertEqual(gtb["bank_code"], "058")
        self.assertTrue(gtb["logo_url"].startswith("http"))
        self.assertEqual(gtb["slug"], "guaranty-trust-bank")

    async def test_list_banks_query_filter(self):
        res = await self.client.get("/api/v1/ramp/banks?q=zenith")
        self.assertEqual(res.status_code, 200, res.text)
        banks = res.json()["data"]
        self.assertEqual(len(banks), 1)
        self.assertEqual(banks[0]["code"], "057")
        self.assertEqual(banks[0]["name"], "Zenith Bank")

    # =========================================================================
    # Account Verification Endpoint Tests
    # =========================================================================


    async def test_verify_account_success(self):
        payload = {
            "account_number": "0123456789",
            "bank_code": "058",
        }
        res = await self.client.post("/api/v1/ramp/verify", json=payload)
        self.assertEqual(res.status_code, 200, res.text)
        res_json = res.json()
        self.assertEqual(res_json["detail"], "Account verified successfully")
        data = res_json["data"]
        self.assertEqual(data["account_number"], "0123456789")
        self.assertEqual(data["bank_code"], "058")
        self.assertEqual(data["bank_name"], "Guaranty Trust Bank")
        self.assertEqual(data["fullname"], "John Doe")
        self.assertEqual(data["account_name"], "John Doe")

    async def test_verify_account_validation(self):
        # Invalid 9-digit account number
        res = await self.client.post("/api/v1/ramp/verify", json={"account_number": "123456789", "bank_code": "058"})
        self.assertEqual(res.status_code, 400)
        self.assertIn("10 digits", res.json()["detail"])

        # Missing bank_code
        res_no_bank = await self.client.post("/api/v1/ramp/verify", json={"account_number": "0123456789", "bank_code": ""})
        self.assertEqual(res_no_bank.status_code, 400)
        self.assertIn("Bank code is required", res_no_bank.json()["detail"])


    # =========================================================================
    # Transfer Initiation Endpoint Tests
    # =========================================================================

    async def test_initiate_transfer_flow_and_db_persistence(self):
        test_user = await self._create_test_user()
        app.dependency_overrides[get_user] = lambda: test_user

        payload = {
            "amount": 45000,
            "currency": "NGN",
            "token": "USDC",
            "network": "SOLANA",
            "recipient": {
                "account_number": "0123456789",
                "bank_code": "058",
                "bank_name": "Guaranty Trust Bank",
                "account_name": "Alice Smith",
            },
        }

        res = await self.client.post("/api/v1/ramp/transfer", json=payload)
        self.assertEqual(res.status_code, 200, res.text)
        res_json = res.json()
        self.assertEqual(res_json["detail"], "Transfer initiated successfully")
        data = res_json["data"]

        self.assertIn("order_id", data)
        self.assertIn("quote_id", data)
        self.assertIn("wallet_address", data)
        self.assertEqual(data["fiat_amount"], 45000.0)
        self.assertEqual(data["fiat_currency"], "NGN")
        self.assertEqual(data["network"], "SOLANA")
        self.assertEqual(data["crypto_asset"], "USDC")
        self.assertGreater(data["crypto_amount"], 0)
        self.assertEqual(data["recipient"]["account_number"], "0123456789")
        self.assertEqual(data["recipient"]["bank_code"], "058")

        # Verify quote and order in DB
        async with AsyncSession(test_engine, expire_on_commit=False) as session:
            quote = (await session.exec(select(Quote).where(Quote.id == data["quote_id"]))).first()
            self.assertIsNotNone(quote)
            self.assertEqual(quote.user_id, test_user.id)
            self.assertEqual(quote.amount_ngn, 45000.0)

            order = (await session.exec(select(OffRampOrder).where(OffRampOrder.id == data["order_id"]))).first()
            self.assertIsNotNone(order)
            self.assertEqual(order.user_id, test_user.id)
            self.assertEqual(order.quote_id, quote.id)
            self.assertEqual(order.fiat_amount, 45000.0)
            self.assertEqual(order.recipient_bank_code, "058")

    async def test_initiate_transfer_idempotency(self):
        test_user = await self._create_test_user()
        app.dependency_overrides[get_user] = lambda: test_user

        payload = {
            "amount": 25000,
            "currency": "NGN",
            "token": "USDC",
            "network": "SOLANA",
            "recipient": {
                "account_number": "0123456789",
                "bank_code": "044",
            },
        }
        headers = {"Idempotency-Key": "idem_unique_key_123"}

        # 1. First call
        res1 = await self.client.post("/api/v1/ramp/transfer", json=payload, headers=headers)
        self.assertEqual(res1.status_code, 200, res1.text)
        res1_json = res1.json()
        self.assertEqual(res1_json["detail"], "Transfer initiated successfully")
        data1 = res1_json["data"]

        # 2. Second call with same idempotency key
        res2 = await self.client.post("/api/v1/ramp/transfer", json=payload, headers=headers)
        self.assertEqual(res2.status_code, 200, res2.text)
        res2_json = res2.json()
        self.assertEqual(res2_json["detail"], "Transfer fetched from existing idempotent order")
        data2 = res2_json["data"]

        # Must return the same order and quote
        self.assertEqual(data1["order_id"], data2["order_id"])
        self.assertEqual(data1["quote_id"], data2["quote_id"])
        self.assertEqual(data1["wallet_address"], data2["wallet_address"])

        # Check DB only has 1 OffRampOrder with that key
        async with AsyncSession(test_engine, expire_on_commit=False) as session:
            orders = (await session.exec(select(OffRampOrder).where(OffRampOrder.idempotency_key == "idem_unique_key_123"))).all()
            self.assertEqual(len(orders), 1)

    async def test_initiate_transfer_currency_conversion(self):
        test_user = await self._create_test_user()
        app.dependency_overrides[get_user] = lambda: test_user

        payload = {
            "amount": 20,
            "currency": "USD",
            "token": "USDC",
            "network": "SOLANA",
            "recipient": {
                "account_number": "0123456789",
                "bank_code": "058",
            },
        }

        res = await self.client.post("/api/v1/ramp/transfer", json=payload)
        self.assertEqual(res.status_code, 200, res.text)
        data = res.json()["data"]
        # 20 USD at 1500 NGN/USDC = 30000 NGN
        self.assertEqual(data["fiat_amount"], 30000.0)

    async def test_initiate_transfer_validation_rejections(self):
        test_user = await self._create_test_user()
        app.dependency_overrides[get_user] = lambda: test_user

        # 1. Missing recipient
        res1 = await self.client.post("/api/v1/ramp/transfer", json={
            "amount": 1000,
            "currency": "NGN",
            "token": "USDC",
            "network": "SOLANA",
        })
        self.assertEqual(res1.status_code, 422)

        # 2. Invalid account number (< 10 digits)
        res2 = await self.client.post("/api/v1/ramp/transfer", json={
            "amount": 1000,
            "currency": "NGN",
            "token": "USDC",
            "network": "SOLANA",
            "recipient": {
                "account_number": "12345",
                "bank_code": "058",
            },
        })
        self.assertEqual(res2.status_code, 422)

        # 3. Invalid amount (<= 0)
        res3 = await self.client.post("/api/v1/ramp/transfer", json={
            "amount": -50,
            "currency": "NGN",
            "token": "USDC",
            "network": "SOLANA",
            "recipient": {
                "account_number": "0123456789",
                "bank_code": "058",
            },
        })
        self.assertEqual(res3.status_code, 422)


