"""
Service layer for bills catalog operations (Data plans, TV subscription plans, services, betting).
"""

from typing import Any, Dict, List, Optional
from app.bills.mock_data import BETTING_PROVIDERS, BILL_SERVICES, DATA_PLANS, TV_PLANS


class BillCatalogService:
    """
    Catalog service for bills: data plans, TV subscription plans, and bill categories.
    """

    SUPPORTED_DATA_PROVIDERS = {"airtel", "glo", "mtn", "9mobile"}
    SUPPORTED_DATA_DURATIONS = {"daily", "weekly", "monthly", "night", "weekend"}

    SUPPORTED_TV_PROVIDERS = {"dstv", "gotv", "startimes", "showmax"}
    SUPPORTED_TV_DURATIONS = {"daily", "weekly", "monthly", "annual"}

    # Provider normalization mappings
    DATA_PROVIDER_ALIASES = {
        "airtel": "airtel",
        "glo": "glo",
        "globacom": "glo",
        "mtn": "mtn",
        "9mobile": "9mobile",
        "etisalat": "9mobile",
        "nine_mobile": "9mobile",
        "ninemobile": "9mobile",
    }

    DATA_DURATION_ALIASES = {
        "daily": "daily",
        "day": "daily",
        "1day": "daily",
        "2days": "daily",
        "weekly": "weekly",
        "week": "weekly",
        "7days": "weekly",
        "14days": "weekly",
        "monthly": "monthly",
        "month": "monthly",
        "30days": "monthly",
        "night": "night",
        "nightly": "night",
        "night_plan": "night",
        "night-plan": "night",
        "night_plans": "night",
        "nightplans": "night",
        "weekend": "weekend",
        "weekend_bundle": "weekend",
        "weekend-bundle": "weekend",
        "weekend_bundles": "weekend",
        "weekendbundles": "weekend",
    }

    TV_PROVIDER_ALIASES = {
        "dstv": "dstv",
        "d_stv": "dstv",
        "gotv": "gotv",
        "go_tv": "gotv",
        "startimes": "startimes",
        "star_times": "startimes",
        "star-times": "startimes",
        "showmax": "showmax",
        "show_max": "showmax",
    }

    TV_DURATION_ALIASES = {
        "daily": "daily",
        "day": "daily",
        "weekly": "weekly",
        "week": "weekly",
        "monthly": "monthly",
        "month": "monthly",
        "annual": "annual",
        "annually": "annual",
        "year": "annual",
        "yearly": "annual",
        "365days": "annual",
    }

    def normalize_data_provider(self, provider: Optional[str]) -> Optional[str]:
        if not provider or not provider.strip():
            return None
        cleaned = provider.strip().lower().replace(" ", "_")
        normalized = self.DATA_PROVIDER_ALIASES.get(cleaned)
        if not normalized or normalized not in self.SUPPORTED_DATA_PROVIDERS:
            supported = ", ".join(sorted(self.SUPPORTED_DATA_PROVIDERS))
            raise ValueError(f"Invalid data provider '{provider}'. Supported providers: {supported}")
        return normalized

    def normalize_data_duration(self, duration: Optional[str]) -> Optional[str]:
        if not duration or not duration.strip():
            return None
        cleaned = duration.strip().lower().replace(" ", "_")
        normalized = self.DATA_DURATION_ALIASES.get(cleaned)
        if not normalized or normalized not in self.SUPPORTED_DATA_DURATIONS:
            supported = ", ".join(sorted(self.SUPPORTED_DATA_DURATIONS))
            raise ValueError(f"Invalid duration '{duration}'. Supported durations: {supported}")
        return normalized

    def normalize_tv_provider(self, provider: Optional[str]) -> Optional[str]:
        if not provider or not provider.strip():
            return None
        cleaned = provider.strip().lower().replace(" ", "_")
        normalized = self.TV_PROVIDER_ALIASES.get(cleaned)
        if not normalized or normalized not in self.SUPPORTED_TV_PROVIDERS:
            supported = ", ".join(sorted(self.SUPPORTED_TV_PROVIDERS))
            raise ValueError(f"Invalid TV provider '{provider}'. Supported providers: {supported}")
        return normalized

    def normalize_tv_duration(self, duration: Optional[str]) -> Optional[str]:
        if not duration or not duration.strip():
            return None
        cleaned = duration.strip().lower().replace(" ", "_")
        normalized = self.TV_DURATION_ALIASES.get(cleaned)
        if not normalized or normalized not in self.SUPPORTED_TV_DURATIONS:
            supported = ", ".join(sorted(self.SUPPORTED_TV_DURATIONS))
            raise ValueError(f"Invalid duration '{duration}'. Supported durations: {supported}")
        return normalized

    def get_data_plans(
        self,
        provider: Optional[str] = None,
        duration: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch data plans with optional filtering by provider and/or duration.
        """
        norm_provider = self.normalize_data_provider(provider)
        norm_duration = self.normalize_data_duration(duration)

        filtered = DATA_PLANS
        if norm_provider:
            filtered = [p for p in filtered if p["provider"] == norm_provider]
        if norm_duration:
            filtered = [p for p in filtered if p["duration"] == norm_duration]

        return [dict(item) for item in filtered]

    def get_tv_plans(
        self,
        provider: Optional[str] = None,
        duration: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch TV subscription plans with optional filtering by provider and/or duration.
        """
        norm_provider = self.normalize_tv_provider(provider)
        norm_duration = self.normalize_tv_duration(duration)

        filtered = TV_PLANS
        if norm_provider:
            filtered = [p for p in filtered if p["provider"] == norm_provider]
        if norm_duration:
            filtered = [p for p in filtered if p["duration"] == norm_duration]

        return [dict(item) for item in filtered]

    def get_services(self) -> List[Dict[str, Any]]:
        """
        Return the supported bill payment categories and their providers.
        """
        return [dict(item) for item in BILL_SERVICES]

    def get_betting_providers(self) -> List[Dict[str, Any]]:
        """
        Return the supported betting platforms.
        """
        return [dict(item) for item in BETTING_PROVIDERS]
