import json
import unittest
from app.quotes.services import (
    BaseQuoteService,
    BankTransferQuoteService,
    BillQuoteService,
    QuoteServiceFactory,
    QuoteValidationError,
)


class TestQuoteService(unittest.TestCase):

    def test_base_quote_service_cannot_be_instantiated(self):
        """Verify that BaseQuoteService is an abstract base class."""
        with self.assertRaises(TypeError):
            # pyrefly: ignore [bad-instantiation]
            BaseQuoteService()

    def test_bank_transfer_quote_with_dict(self):
        """Test generating a bank transfer quote using a Python dictionary."""
        service = BankTransferQuoteService()
        request_data = {
            "amount_ngn": 50000,
            "network": "SOLANA",
            "token": "USDC",
            "recipient": {
                "account_number": "0123456789",
                "bank_code": "058",
                "bank_name": "Guaranty Trust Bank",
                "account_name": "Tunde Bakare",
            },
        }

        quote = service.get_quote(request_data)

        # Required top-level fields
        self.assertIn("wallet_address", quote)
        self.assertEqual(quote["network"], "SOLANA")
        self.assertEqual(quote["token"], "USDC")
        self.assertEqual(quote["rate"], 1500.0)
        self.assertEqual(quote["payment_type"], "BANK_TRANSFER")
        self.assertEqual(quote["fiat_amount"], 50000.0)

        # Total fiat is amount + platform fee (500) + provider fee (200) = 50700
        expected_crypto = round(50700 / 1500.0, 6)
        self.assertEqual(quote["amount"], expected_crypto)

        # Blockchain metadata
        meta = quote["blockchain_metadata"]
        self.assertEqual(meta["wallet_address"], quote["wallet_address"])
        self.assertEqual(meta["network"], "SOLANA")
        self.assertEqual(meta["chain_id"], 101)
        self.assertIn("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", meta["token_contract_address"])
        self.assertTrue(meta["payment_uri"].startswith("solana:"))
        self.assertIn("reference=", meta["payment_uri"])

        # Recipient bank details
        recipient = quote["recipient"]
        self.assertEqual(recipient["account_number"], "0123456789")
        self.assertEqual(recipient["bank_code"], "058")
        self.assertEqual(recipient["bank_name"], "Guaranty Trust Bank")
        self.assertEqual(recipient["account_name"], "Tunde Bakare")

    def test_bank_transfer_quote_with_flat_keys_and_json_str(self):
        """Test bank transfer quote with flat recipient keys and JSON string input."""
        service = BankTransferQuoteService()
        json_payload = json.dumps({
            "amount_ngn": 15000,
            "network": "POLYGON",
            "token": "USDC",
            "account_number": "0098765432",
            "bank_code": "044",
            "bank_name": "Access Bank",
            "account_name": "Chidinma Eze",
        })

        quote = service.get_quote(json_payload)

        self.assertEqual(quote["network"], "POLYGON")
        self.assertEqual(quote["recipient"]["account_number"], "0098765432")
        self.assertEqual(quote["recipient"]["bank_name"], "Access Bank")
        self.assertEqual(quote["blockchain_metadata"]["chain_id"], 137)
        self.assertTrue(quote["blockchain_metadata"]["payment_uri"].startswith("ethereum:"))

    def test_bank_transfer_validation_errors(self):
        """Test validation errors for bank transfer quote requests."""
        service = BankTransferQuoteService()

        # Missing amount_ngn
        with self.assertRaises(QuoteValidationError):
            service.get_quote({"network": "SOLANA"})

        # Negative amount
        with self.assertRaises(QuoteValidationError):
            service.get_quote({"amount_ngn": -100})

        # Missing bank info
        with self.assertRaises(QuoteValidationError):
            service.get_quote({"amount_ngn": 10000})

        # Invalid account number (not 10 digits)
        with self.assertRaises(QuoteValidationError):
            service.get_quote({
                "amount_ngn": 10000,
                "recipient": {
                    "account_number": "12345",
                    "bank_code": "058",
                    "bank_name": "GTB",
                    "account_name": "Test",
                },
            })

    def test_bill_quote_airtime(self):
        """Test generating a bill quote for airtime."""
        service = BillQuoteService()
        payload = {
            "amount_ngn": 2000,
            "network": "ETHEREUM",
            "token": "USDC",
            "category": "AIRTIME",
            "customer_id": "08031234567",
            "biller_name": "MTN",
        }

        quote = service.get_quote(payload)

        self.assertEqual(quote["payment_type"], "AIRTIME")
        self.assertEqual(quote["network"], "ETHEREUM")
        self.assertEqual(quote["blockchain_metadata"]["chain_id"], 1)
        self.assertEqual(quote["bill_details"]["category"], "AIRTIME")
        self.assertEqual(quote["bill_details"]["customer_id"], "08031234567")
        self.assertEqual(quote["bill_details"]["biller_name"], "MTN")

    def test_bill_quote_electricity_validation(self):
        """Test validation errors for bill quotes."""
        service = BillQuoteService()

        # Missing category
        with self.assertRaises(QuoteValidationError):
            service.get_quote({"amount_ngn": 5000})

        # Invalid category
        with self.assertRaises(QuoteValidationError):
            service.get_quote({"amount_ngn": 5000, "category": "STREAMING"})

        # Missing customer_id
        with self.assertRaises(QuoteValidationError):
            service.get_quote({"amount_ngn": 5000, "category": "ELECTRICITY"})

    def test_quote_service_factory(self):
        """Test QuoteServiceFactory instantiates correct service classes."""
        transfer_service = QuoteServiceFactory.create("BANK_TRANSFER")
        self.assertIsInstance(transfer_service, BankTransferQuoteService)

        bill_service = QuoteServiceFactory.create("AIRTIME")
        self.assertIsInstance(bill_service, BillQuoteService)

        with self.assertRaises(ValueError):
            QuoteServiceFactory.create("UNSUPPORTED_TYPE")

    def test_api_quotes_endpoint_bank_transfer(self):
        """Test POST /api/v1/quotes for bank transfer."""
        import asyncio
        from fastapi.testclient import TestClient
        from sqlmodel import SQLModel
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlmodel.ext.asyncio.session import AsyncSession
        from sqlalchemy.pool import StaticPool
        from app.main import app
        from app.core.database import get_session
        from app.core.dependencies import get_user
        from app.core.models.user import User
        from app.core.models.enums import UserStatus, AuthProvider

        test_engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        async def init_db():
            async with test_engine.begin() as conn:
                await conn.run_sync(SQLModel.metadata.create_all)

        asyncio.run(init_db())

        mock_user = User(
            id="test-user-uuid",
            email="test@example.com",
            name="Test User",
            status=UserStatus.ACTIVE,
            auth_provider=AuthProvider.NORMAL,
            email_verified=True,
        )

        async def override_get_session():
            async with AsyncSession(test_engine, expire_on_commit=False) as session:
                yield session

        async def override_get_user():
            return mock_user

        app.dependency_overrides[get_session] = override_get_session
        app.dependency_overrides[get_user] = override_get_user

        try:
            client = TestClient(app)
            res = client.post("/api/v1/quotes", json={
                "type": "BANK_TRANSFER",
                "amount_ngn": 25000,
                "network": "SOLANA",
                "recipient": {
                    "account_number": "0123456789",
                    "bank_code": "058",
                    "bank_name": "GTBank",
                    "account_name": "Test User",
                },
            })
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertIn("wallet_address", data)
            self.assertEqual(data["payment_type"], "BANK_TRANSFER")
            self.assertEqual(data["recipient"]["account_number"], "0123456789")
        finally:
            app.dependency_overrides.pop(get_session, None)
            app.dependency_overrides.pop(get_user, None)

    def test_api_bills_quote_endpoint(self):
        """Test POST /api/v1/bills/quote for electricity."""
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        res = client.post("/api/v1/bills/quote", json={
            "category": "ELECTRICITY",
            "amount_ngn": 10000,
            "network": "POLYGON",
            "customer_id": "45012345678",
            "biller_name": "EKEDC",
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("wallet_address", data)
        self.assertEqual(data["payment_type"], "ELECTRICITY")
        self.assertEqual(data["bill_details"]["customer_id"], "45012345678")


if __name__ == "__main__":
    unittest.main()
