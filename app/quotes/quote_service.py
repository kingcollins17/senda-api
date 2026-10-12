"""
Unified Quote generation service for crypto-to-fiat transactions.
Supports bank transfers and bill payments (Data, Airtime, TV, Electricity, Betting).
All payments are routed through the same payment flow, differentiated by payload metadata.
"""

from datetime import datetime, timedelta
import json
import uuid
from typing import Any, Dict, Optional, Union

from app.bills.mock_data import DATA_PLANS, TV_PLANS
from app.core.models.enums import BillCategory, Network, PaymentType
from app.utils.time import now


class QuoteValidationError(ValueError):
    """Raised when request information for a quote is missing or invalid."""
    pass


class QuoteServiceImpl:
    """
    Unified Quote Service implementation.
    
    Orchestrates quote generation for both bank transfers and bill payments.
    Differentiator resides in the payload metadata:
    - Recipient bank accounts (for offramp / bank transfers)
    - Bill metadata (category, customer_id, biller_name, plan/package id)
    """

    # Contract addresses for supported stablecoins
    TOKEN_CONTRACT_ADDRESSES = {
        Network.SOLANA.value: {
            "USDC": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
            "USDT": "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",
        },
        Network.POLYGON.value: {
            "USDC": "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359",
            "USDT": "0xc2132D05D31c914a87C6611C10748AEb04B58e8F",
        },
        Network.ETHEREUM.value: {
            "USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
            "USDT": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
        },
    }

    CHAIN_IDS = {
        Network.SOLANA.value: 101,      # Solana Mainnet-Beta
        Network.POLYGON.value: 137,     # Polygon Mainnet
        Network.ETHEREUM.value: 1,      # Ethereum Mainnet
    }

    # Pre-configured mock pool/deposit addresses per network for settlement
    MOCK_DEPOSIT_ADDRESSES = {
        Network.SOLANA.value: "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
        Network.POLYGON.value: "0x71C845A00755a9562725832a8A406df7a00f8623",
        Network.ETHEREUM.value: "0x71C845A00755a9562725832a8A406df7a00f8623",
    }

    VALID_BILL_CATEGORIES = {c.value for c in BillCategory}

    def __init__(
        self,
        default_rate: float = 1500.0,
        platform_fee_ngn: float = 500.0,
        provider_fee_ngn: float = 200.0,
        validity_seconds: int = 900,
        default_network: str = Network.SOLANA.value,
        default_token: str = "USDC",
    ) -> None:
        self.default_rate = default_rate
        self.platform_fee_ngn = platform_fee_ngn
        self.provider_fee_ngn = provider_fee_ngn
        self.validity_seconds = validity_seconds
        self.default_network = default_network
        self.default_token = default_token

    # =========================================================================
    # Plan Catalog Lookup
    # =========================================================================

    @staticmethod
    def find_plan(plan_id: str) -> Optional[Dict[str, Any]]:
        """Look up plan from data plans or TV plans catalog."""
        if not plan_id:
            return None
        cleaned_id = str(plan_id).strip()
        for plan in DATA_PLANS:
            if plan["id"] == cleaned_id:
                return dict(plan)
        for plan in TV_PLANS:
            if plan["id"] == cleaned_id:
                return dict(plan)
        return None

    # =========================================================================
    # Main Quote Generation
    # =========================================================================

    def get_quote(self, request_data: Union[Dict[str, Any], str]) -> Dict[str, Any]:
        """
        Generates a quote for a blockchain payment.
        
        Accepts dict or JSON string. Resolves plan if plan_id/package_id is supplied.
        Attaches recipient or bill metadata accordingly.
        """
        payload = self._parse_payload(request_data)

        # 1. Resolve package / plan ID if provided
        plan_id = payload.get("plan_id") or payload.get("package_id") or payload.get("product_id")
        plan = self.find_plan(plan_id) if plan_id else None
        if plan:
            # Auto-populate amount_ngn from plan if not passed
            if "amount_ngn" not in payload or payload["amount_ngn"] is None:
                payload["amount_ngn"] = plan["price_ngn"]
            if not payload.get("category") and not payload.get("service_type"):
                payload["category"] = plan.get("category", "DATA")
            if not payload.get("provider") and not payload.get("biller_name"):
                payload["biller_name"] = plan.get("provider_name", plan.get("provider"))

        # 2. Validate common parameters (amount_ngn, network, token)
        self._validate_common(payload)

        # 3. Extract core parameters
        amount_ngn = float(payload["amount_ngn"])
        network = str(payload.get("network", self.default_network)).upper()
        token = str(payload.get("token", payload.get("crypto_asset", self.default_token))).upper()

        # 4. Exchange rate and fee calculations
        rate = self._get_exchange_rate(token=token, network=network)
        fees = self._calculate_fees(amount_ngn=amount_ngn)
        total_fiat_amount = amount_ngn + fees["platform_fee_ngn"] + fees["provider_fee_ngn"]
        crypto_amount = self._calculate_crypto_amount(
            total_fiat=total_fiat_amount,
            rate=rate,
            token=token,
        )

        quote_id = f"{uuid.uuid4().hex[:12]}"
        created_at = now()
        expires_at = created_at + timedelta(seconds=self.validity_seconds)

        # 5. Resolve blockchain deposit wallet address & payment metadata
        wallet_address = self._generate_deposit_address(network=network, token=token, quote_id=quote_id)
        blockchain_metadata = self._build_blockchain_metadata(
            network=network,
            token=token,
            wallet_address=wallet_address,
            crypto_amount=crypto_amount,
            quote_id=quote_id,
        )

        # 6. Extract differentiator metadata (recipient vs bill details)
        payment_type, metadata_dict = self._extract_metadata_and_type(payload, plan)

        # 7. Assemble standardized output dictionary
        quote_response: Dict[str, Any] = {
            "quote_id": quote_id,
            "payment_type": payment_type,
            "wallet_address": wallet_address,
            "network": network,
            "amount": crypto_amount,
            "rate": rate,
            "token": token,
            "fiat_amount": amount_ngn,
            "fiat_currency": "NGN",
            "fees": {
                "platform_fee_ngn": fees["platform_fee_ngn"],
                "provider_fee_ngn": fees["provider_fee_ngn"],
                "total_fee_ngn": fees["platform_fee_ngn"] + fees["provider_fee_ngn"],
                "total_fiat_amount": total_fiat_amount,
            },
            "expires_at": expires_at.isoformat(),
            "validity_seconds": self.validity_seconds,
            "blockchain_metadata": blockchain_metadata,
            **metadata_dict,
        }

        return quote_response

    # =========================================================================
    # Payload & Metadata Extraction
    # =========================================================================

    def _extract_metadata_and_type(
        self,
        payload: Dict[str, Any],
        plan: Optional[Dict[str, Any]] = None,
    ) -> tuple[str, Dict[str, Any]]:
        """
        Differentiates between bank transfer and bill payments based on payload contents.
        Returns (payment_type, metadata_dict).
        """
        metadata: Dict[str, Any] = {}

        # Check for recipient bank details
        recipient_data = payload.get("recipient")
        has_recipient = isinstance(recipient_data, dict) or (
            payload.get("account_number") and payload.get("bank_code")
        ) or payload.get("recipient_id")

        # Check for bill category / details
        bill_data = payload.get("bill_details")
        category = None
        if isinstance(bill_data, dict):
            category = bill_data.get("category") or bill_data.get("service_type") or bill_data.get("type")
        if not category:
            category = payload.get("category") or payload.get("service_type") or payload.get("type")

        category_upper = str(category).upper() if category else None
        is_bill_category = category_upper in self.VALID_BILL_CATEGORIES or category_upper in [
            "BILL", "BILL_PAYMENT",
        ]
        has_bill = is_bill_category or bool(bill_data) or bool(plan) or bool(
            payload.get("phone_number") or payload.get("meter_number") or payload.get("smartcard_number")
        )

        raw_type = str(payload.get("payment_type", payload.get("type", ""))).upper()
        is_transfer_type = raw_type in ["BANK_TRANSFER", "TRANSFER", "OFFRAMP"]

        if has_bill:
            # Build bill details metadata
            if isinstance(bill_data, dict):
                cat = str(bill_data.get("category") or category_upper or (plan["category"] if plan else "BILL_PAYMENT")).upper()
                cust_id = str(
                    bill_data.get("customer_id")
                    or bill_data.get("phone_number")
                    or bill_data.get("meter_number")
                    or bill_data.get("smartcard_number")
                    or bill_data.get("user_id", "")
                ).strip()
                biller = bill_data.get("biller_name") or bill_data.get("provider") or bill_data.get("biller_code")
                p_id = bill_data.get("plan_id") or bill_data.get("package_id") or bill_data.get("product_id")
                cust_name = bill_data.get("customer_name")
            else:
                cat = str(category_upper or (plan["category"] if plan else "BILL_PAYMENT")).upper()
                cust_id = str(
                    payload.get("customer_id")
                    or payload.get("phone_number")
                    or payload.get("meter_number")
                    or payload.get("smartcard_number")
                    or payload.get("user_id", "")
                ).strip()
                biller = payload.get("biller_name") or payload.get("provider") or payload.get("biller_code")
                p_id = payload.get("plan_id") or payload.get("package_id") or payload.get("product_id")
                cust_name = payload.get("customer_name")

            if plan:
                p_id = plan["id"]
                if not biller:
                    biller = plan.get("provider_name", plan.get("provider"))

            # Customer identifier validation for bill payments
            if not cust_id:
                field_hint = {
                    BillCategory.AIRTIME.value: "phone number",
                    BillCategory.DATA.value: "phone number",
                    BillCategory.ELECTRICITY.value: "meter number",
                    BillCategory.TV.value: "smartcard/IUC number",
                    BillCategory.BETTING.value: "betting account/user ID",
                }.get(cat, "customer identifier")
                raise QuoteValidationError(f"Missing 'customer_id' for bill payment ({field_hint}).")

            bill_metadata: Dict[str, Any] = {
                "category": cat,
                "customer_id": cust_id,
                "biller_name": biller,
                "product_id": p_id,
                "plan_id": p_id,
                "customer_name": cust_name,
            }
            if plan:
                bill_metadata["plan_name"] = plan.get("name")
                if "data_amount" in plan:
                    bill_metadata["data_amount"] = plan["data_amount"]
                if "duration" in plan:
                    bill_metadata["duration"] = plan["duration"]
                if "validity" in plan:
                    bill_metadata["validity"] = plan["validity"]

            metadata["bill_details"] = bill_metadata
            payment_type = cat if cat in self.VALID_BILL_CATEGORIES else "BILL_PAYMENT"

        elif has_recipient or is_transfer_type:
            # Build bank transfer recipient metadata
            if isinstance(recipient_data, dict):
                acc_num = recipient_data.get("account_number")
                b_code = recipient_data.get("bank_code")
                b_name = recipient_data.get("bank_name")
                acc_name = recipient_data.get("account_name")
                rec_id = recipient_data.get("id") or recipient_data.get("recipient_id")
            else:
                acc_num = payload.get("account_number")
                b_code = payload.get("bank_code")
                b_name = payload.get("bank_name")
                acc_name = payload.get("account_name")
                rec_id = payload.get("recipient_id")

            if not (acc_num and b_code):
                raise QuoteValidationError(
                    "Recipient bank information is required for bank transfer quotes. "
                    "Must provide 'account_number', 'bank_code', 'bank_name', and 'account_name'."
                )

            if acc_num is not None:
                acc_num_str = str(acc_num).strip()
                if not (acc_num_str.isdigit() and len(acc_num_str) == 10):
                    raise QuoteValidationError(
                        f"Invalid bank account number '{acc_num}'. Nigerian NUBAN account number must be 10 digits."
                    )

            metadata["recipient"] = {
                "account_number": str(acc_num or "").strip(),
                "bank_code": str(b_code or "").strip(),
                "bank_name": str(b_name or "").strip(),
                "account_name": str(acc_name or "").strip(),
                "recipient_id": rec_id,
            }
            payment_type = PaymentType.BANK_TRANSFER.value
        else:
            # Fallback if no specific differentiator
            raw_type = str(payload.get("payment_type", payload.get("type", "BANK_TRANSFER"))).upper()
            payment_type = raw_type

        return payment_type, metadata

    # =========================================================================
    # Internal Validation & Calculation Helpers
    # =========================================================================

    def _parse_payload(self, request_data: Union[Dict[str, Any], str]) -> Dict[str, Any]:
        """Ensures request data is parsed into a Python dictionary."""
        if isinstance(request_data, str):
            try:
                parsed = json.loads(request_data)
                if not isinstance(parsed, dict):
                    raise QuoteValidationError("JSON payload must be a JSON object (dictionary).")
                return parsed
            except json.JSONDecodeError as exc:
                raise QuoteValidationError(f"Invalid JSON string provided: {exc}") from exc
        elif isinstance(request_data, dict):
            return dict(request_data)
        else:
            raise QuoteValidationError(
                f"Request data must be dict or JSON string, received {type(request_data).__name__}."
            )

    def _validate_common(self, payload: Dict[str, Any]) -> None:
        """Validates parameters common to all quotes."""
        if "amount_ngn" not in payload or payload["amount_ngn"] is None:
            raise QuoteValidationError("Missing required parameter: 'amount_ngn'.")

        try:
            amount = float(payload["amount_ngn"])
            if amount <= 0:
                raise QuoteValidationError("'amount_ngn' must be greater than zero.")
        except (ValueError, TypeError):
            raise QuoteValidationError("'amount_ngn' must be a valid positive number.")

        network = str(payload.get("network", self.default_network)).upper()
        valid_networks = [n.value for n in Network]
        if network not in valid_networks:
            raise QuoteValidationError(
                f"Unsupported network: '{network}'. Supported networks: {valid_networks}"
            )

        token = str(payload.get("token", payload.get("crypto_asset", self.default_token))).upper()
        if token not in ["USDC", "USDT"]:
            raise QuoteValidationError(f"Unsupported crypto token: '{token}'. Supported tokens: ['USDC', 'USDT'].")

    def _get_exchange_rate(self, token: str, network: str) -> float:
        """Retrieves exchange rate for token and network."""
        return self.default_rate

    def _calculate_fees(self, amount_ngn: float) -> Dict[str, float]:
        """Calculates platform and provider fees."""
        return {
            "platform_fee_ngn": self.platform_fee_ngn,
            "provider_fee_ngn": self.provider_fee_ngn,
        }

    def _calculate_crypto_amount(self, total_fiat: float, rate: float, token: str) -> float:
        """Computes required crypto amount rounded to token precision (6 decimals)."""
        raw_crypto = total_fiat / rate
        return round(raw_crypto, 6)

    def _generate_deposit_address(self, network: str, token: str, quote_id: str) -> str:
        """Returns the destination wallet address for deposit."""
        return self.MOCK_DEPOSIT_ADDRESSES.get(network, self.MOCK_DEPOSIT_ADDRESSES[Network.SOLANA.value])

    def _build_blockchain_metadata(
        self,
        network: str,
        token: str,
        wallet_address: str,
        crypto_amount: float,
        quote_id: str,
    ) -> Dict[str, Any]:
        """Builds web3/wallet metadata for payment execution."""
        token_contract = self.TOKEN_CONTRACT_ADDRESSES.get(network, {}).get(token, "")
        chain_id = self.CHAIN_IDS.get(network, 101)
        token_decimals = 6  # USDC / USDT standard decimals
        reference = f"ref_{quote_id}"

        if network == Network.SOLANA.value:
            payment_uri = (
                f"solana:{wallet_address}?amount={crypto_amount}"
                f"&spl-token={token_contract}&reference={reference}&label=Senda%20Payment"
            )
            transfer_instructions = (
                f"Transfer exactly {crypto_amount} {token} (SPL token) on Solana Mainnet "
                f"to wallet address {wallet_address} with reference {reference}."
            )
        else:
            raw_units = int(crypto_amount * (10 ** token_decimals))
            payment_uri = (
                f"ethereum:{token_contract}@{chain_id}/transfer?address={wallet_address}&uint256={raw_units}"
            )
            transfer_instructions = (
                f"Transfer exactly {crypto_amount} {token} on {network} (Chain ID {chain_id}) "
                f"to recipient {wallet_address}. Contract: {token_contract}."
            )

        return {
            "wallet_address": wallet_address,
            "network": network,
            "chain_id": chain_id,
            "token": token,
            "amount": crypto_amount,
            "token_decimals": token_decimals,
            "token_contract_address": token_contract,
            "payment_reference": reference,
            "payment_uri": payment_uri,
            "transfer_instructions": transfer_instructions,
        }
