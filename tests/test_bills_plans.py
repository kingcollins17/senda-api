"""
Tests for Bills endpoints:
- Data plans listing & filtering by provider (airtel, glo, mtn, 9mobile) and duration (daily, weekly, monthly, night, weekend)
- TV subscription plans listing & filtering by provider (dstv, gotv, startimes, showmax) and duration
- Services catalog endpoint
- Provider mock integration
"""

import unittest
from httpx import AsyncClient, ASGITransport
from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core.database import get_session
from app.bills.bill_service import BillCatalogService
from app.providers.bills.mock import MockBillProvider

test_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


async def override_get_session():
    async with AsyncSession(test_engine, expire_on_commit=False) as session:
        yield session


class TestBillsPlans(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        async with test_engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

        app.dependency_overrides[get_session] = override_get_session
        self.transport = ASGITransport(app=app)
        self.client = AsyncClient(transport=self.transport, base_url="http://test")
        self.catalog = BillCatalogService()

    async def asyncTearDown(self):
        app.dependency_overrides.clear()
        await self.client.aclose()
        async with test_engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.drop_all)

    # =========================================================================
    # DATA PLANS ENDPOINTS
    # =========================================================================

    async def test_get_all_data_plans_without_query_params(self):
        """Listing data plans without query params returns plans for all 4 providers."""
        response = await self.client.get("/api/v1/bills/data-plans")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn("plans", data)
        self.assertIn("data", data)
        self.assertIn("total", data)
        self.assertGreater(data["total"], 0)
        self.assertEqual(data["provider"], None)
        self.assertEqual(data["duration"], None)

        providers = {p["provider"] for p in data["plans"]}
        self.assertEqual(providers, {"airtel", "glo", "mtn", "9mobile"})

        durations = {p["duration"] for p in data["plans"]}
        self.assertTrue({"daily", "weekly", "monthly", "night", "weekend"}.issubset(durations))

    async def test_filter_data_plans_by_provider(self):
        """Filter data plans by each of the 4 providers (airtel, glo, mtn, 9mobile)."""
        for provider in ["airtel", "glo", "mtn", "9mobile"]:
            response = await self.client.get(f"/api/v1/bills/data-plans?provider={provider}")
            self.assertEqual(response.status_code, 200)

            data = response.json()
            self.assertEqual(data["provider"], provider)
            self.assertGreater(data["total"], 0)

            for plan in data["plans"]:
                self.assertEqual(plan["provider"], provider)
                self.assertEqual(plan["category"], "DATA")
                self.assertIn("data_amount", plan)
                self.assertIn("validity", plan)
                self.assertGreater(plan["price_ngn"], 0)

    async def test_filter_data_plans_by_provider_case_insensitive_and_aliases(self):
        """Provider filter is case-insensitive and supports aliases (e.g. MTN, etisalat)."""
        response = await self.client.get("/api/v1/bills/data-plans?provider=MTN")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["provider"], "mtn")

        # 9mobile alias: etisalat
        response_alias = await self.client.get("/api/v1/bills/data-plans?provider=etisalat")
        self.assertEqual(response_alias.status_code, 200)
        self.assertEqual(response_alias.json()["provider"], "9mobile")

    async def test_filter_data_plans_by_duration(self):
        """Filter data plans by daily, weekly, monthly, night, and weekend durations."""
        expected_durations = ["daily", "weekly", "monthly", "night", "weekend"]
        for duration in expected_durations:
            response = await self.client.get(f"/api/v1/bills/data-plans?duration={duration}")
            self.assertEqual(response.status_code, 200)

            data = response.json()
            self.assertEqual(data["duration"], duration)
            self.assertGreater(data["total"], 0)

            for plan in data["plans"]:
                self.assertEqual(plan["duration"], duration)

    async def test_filter_data_plans_by_duration_aliases(self):
        """Duration filter supports aliases such as night_plan, weekend_bundle."""
        response_night = await self.client.get("/api/v1/bills/data-plans?duration=night_plan")
        self.assertEqual(response_night.status_code, 200)
        self.assertEqual(response_night.json()["duration"], "night")

        response_weekend = await self.client.get("/api/v1/bills/data-plans?duration=weekend_bundle")
        self.assertEqual(response_weekend.status_code, 200)
        self.assertEqual(response_weekend.json()["duration"], "weekend")

    async def test_filter_data_plans_by_both_provider_and_duration(self):
        """Filter data plans by both provider and duration simultaneously."""
        response = await self.client.get("/api/v1/bills/data-plans?provider=mtn&duration=monthly")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["provider"], "mtn")
        self.assertEqual(data["duration"], "monthly")
        self.assertGreater(data["total"], 0)

        for plan in data["plans"]:
            self.assertEqual(plan["provider"], "mtn")
            self.assertEqual(plan["duration"], "monthly")

    async def test_invalid_data_provider_returns_400(self):
        """Passing an unrecognized data provider returns a 400 Bad Request."""
        response = await self.client.get("/api/v1/bills/data-plans?provider=vodacom")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid data provider", response.json()["detail"])

    async def test_invalid_data_duration_returns_400(self):
        """Passing an unrecognized data duration returns a 400 Bad Request."""
        response = await self.client.get("/api/v1/bills/data-plans?duration=hourly")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid duration", response.json()["detail"])

    async def test_data_plans_endpoint_aliases(self):
        """Verify endpoint path aliases work: /data/plans, /plans/data, /data."""
        for path in ["/api/v1/bills/data/plans", "/api/v1/bills/plans/data", "/api/v1/bills/data"]:
            response = await self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertIn("plans", response.json())

    # =========================================================================
    # TV SUBSCRIPTION PLANS ENDPOINTS
    # =========================================================================

    async def test_get_all_tv_plans_without_query_params(self):
        """Listing TV plans without query params returns plans for all TV providers."""
        response = await self.client.get("/api/v1/bills/tv-plans")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn("plans", data)
        self.assertIn("data", data)
        self.assertIn("total", data)
        self.assertGreater(data["total"], 0)

        providers = {p["provider"] for p in data["plans"]}
        self.assertEqual(providers, {"dstv", "gotv", "startimes", "showmax"})

    async def test_filter_tv_plans_by_provider(self):
        """Filter TV plans by dstv, gotv, startimes, showmax."""
        for provider in ["dstv", "gotv", "startimes", "showmax"]:
            response = await self.client.get(f"/api/v1/bills/tv-plans?provider={provider}")
            self.assertEqual(response.status_code, 200)

            data = response.json()
            self.assertEqual(data["provider"], provider)
            self.assertGreater(data["total"], 0)

            for plan in data["plans"]:
                self.assertEqual(plan["provider"], provider)
                self.assertEqual(plan["category"], "TV")
                self.assertIn("validity", plan)
                self.assertGreater(plan["price_ngn"], 0)

    async def test_filter_tv_plans_by_provider_case_insensitive(self):
        """TV provider filter is case-insensitive (e.g. DSTV, GOtv, StarTimes)."""
        response = await self.client.get("/api/v1/bills/tv-plans?provider=DSTV")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["provider"], "dstv")

        response_gotv = await self.client.get("/api/v1/bills/tv-plans?provider=GOtv")
        self.assertEqual(response_gotv.status_code, 200)
        self.assertEqual(response_gotv.json()["provider"], "gotv")

    async def test_filter_tv_plans_by_duration(self):
        """Filter TV plans by duration (e.g. monthly, annual, daily, weekly)."""
        response_monthly = await self.client.get("/api/v1/bills/tv-plans?duration=monthly")
        self.assertEqual(response_monthly.status_code, 200)
        self.assertGreater(response_monthly.json()["total"], 0)

        response_annual = await self.client.get("/api/v1/bills/tv-plans?duration=annual")
        self.assertEqual(response_annual.status_code, 200)
        self.assertGreater(response_annual.json()["total"], 0)

    async def test_filter_tv_plans_by_provider_and_duration(self):
        """Filter TV plans by both provider and duration."""
        response = await self.client.get("/api/v1/bills/tv-plans?provider=dstv&duration=monthly")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["provider"], "dstv")
        self.assertEqual(data["duration"], "monthly")
        self.assertGreater(data["total"], 0)

        for plan in data["plans"]:
            self.assertEqual(plan["provider"], "dstv")
            self.assertEqual(plan["duration"], "monthly")

    async def test_invalid_tv_provider_returns_400(self):
        """Passing an unrecognized TV provider returns 400 Bad Request."""
        response = await self.client.get("/api/v1/bills/tv-plans?provider=netflix")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid TV provider", response.json()["detail"])

    async def test_invalid_tv_duration_returns_400(self):
        """Passing an unrecognized TV duration returns 400 Bad Request."""
        response = await self.client.get("/api/v1/bills/tv-plans?duration=decade")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid duration", response.json()["detail"])

    async def test_tv_plans_endpoint_aliases(self):
        """Verify TV endpoint path aliases work: /tv/plans, /plans/tv, /tv-subscriptions, /tv."""
        for path in ["/api/v1/bills/tv/plans", "/api/v1/bills/plans/tv", "/api/v1/bills/tv-subscriptions", "/api/v1/bills/tv"]:
            response = await self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertIn("plans", response.json())

    # =========================================================================
    # BILL SERVICES CATALOG ENDPOINT
    # =========================================================================

    async def test_get_bill_services(self):
        """Verify GET /api/v1/bills/services returns bill categories including DATA, TV, and BETTING."""
        response = await self.client.get("/api/v1/bills/services")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn("services", data)
        categories = {s["category"] for s in data["services"]}
        self.assertIn("DATA", categories)
        self.assertIn("TV", categories)
        self.assertIn("AIRTIME", categories)
        self.assertIn("ELECTRICITY", categories)
        self.assertIn("BETTING", categories)

    # =========================================================================
    # BETTING PROVIDERS ENDPOINTS
    # =========================================================================

    async def test_get_betting_providers(self):
        """Verify GET /api/v1/bills/betting-providers returns supported betting platforms."""
        response = await self.client.get("/api/v1/bills/betting-providers")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn("providers", data)
        self.assertIn("data", data)
        self.assertIn("total", data)
        self.assertGreater(data["total"], 0)

        provider_ids = {p["id"] for p in data["providers"]}
        self.assertIn("sportybet", provider_ids)
        self.assertIn("bet9ja", provider_ids)
        self.assertIn("1xbet", provider_ids)

    async def test_betting_providers_endpoint_aliases(self):
        """Verify betting provider path aliases: /betting/providers, /betting."""
        for path in ["/api/v1/bills/betting/providers", "/api/v1/bills/betting"]:
            response = await self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertIn("providers", response.json())

    # =========================================================================
    # MOCK BILL PROVIDER INTEGRATION
    # =========================================================================

    def test_mock_bill_provider_products(self):
        """Verify MockBillProvider returns DATA, TV, and BETTING plans/providers catalog."""
        provider = MockBillProvider()
        data_prods = provider.get_products("DATA")
        self.assertGreater(len(data_prods), 0)
        self.assertIn("data_amount", data_prods[0])

        tv_prods = provider.get_products("TV")
        self.assertGreater(len(tv_prods), 0)
        self.assertIn("name", tv_prods[0])

        betting_prods = provider.get_products("BETTING")
        self.assertGreater(len(betting_prods), 0)
        self.assertIn("name", betting_prods[0])
