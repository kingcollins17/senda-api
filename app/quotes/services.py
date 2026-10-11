"""
Quote generation service implementing the Abstract Pattern for crypto-to-fiat transactions.
Supports bank transfers and bill payments with JSON/dict information interchange.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
import json
import uuid
from typing import Any, Dict, Optional, Union

from app.core.models.enums import BillCategory, Network, PaymentType
from app.utils.time import now


class QuoteValidationError(ValueError):
    """Raised when request information for a quote is missing or invalid."""
    pass


class BaseQuoteService(ABC):
    """
    Abstract Base Class for quote generation.
    
    Implements the Template Method pattern where core workflow (parsing, common
    validation, rate & fee calculation, blockchain metadata generation, and JSON interchange)
    is orchestrated by the base class, while payment-type specific validations and metadata
    are delegated to subclasses.
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

    def __init__(
        self,
        default_rate: float = 1500.0,
        platform_fee_ngn: float = 500.0,
        provider_fee_ngn: float = 200.0,
        validity_seconds: int = 900,
        default_network: str = Network.SOLANA.value,
        default_token: str = "USDC",
    ) -> None:
        """
        Initialize the quote service.

        :param default_rate: Exchange rate (NGN per token, e.g. 1500 NGN = 1 USDC)
        :param platform_fee_ngn: Senda platform fee in NGN
        :param provider_fee_ngn: Liquidity/Off-ramp provider fee in NGN
        :param validity_seconds: Quote expiration time window in seconds (default 15 minutes)
        :param default_network: Fallback network if not specified in request
        :param default_token: Fallback token if not specified in request
        """
        self.default_rate = default_rate
        self.platform_fee_ngn = platform_fee_ngn
        self.provider_fee_ngn = provider_fee_ngn
        self.validity_seconds = validity_seconds
        self.default_network = default_network
        self.default_token = default_token

    def get_quote(self, request_data: Union[Dict[str, Any], str]) -> Dict[str, Any]:
        """
        Generates a quote for a blockchain payment.
        
        Uses JSON dict interchange. Accepts either a Python dict or a JSON string.
        Returns a complete dictionary containing wallet address, network, amount,
        rate, token, expiration, fees, and all blockchain payment metadata.
        """
        payload = self._parse_payload(request_data)

        # 1. Validate common parameters
        self._validate_common(payload)

        # 2. Validate payment-type specific parameters (template hook)
        self._validate_specific(payload)

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

        quote_id = f"quote_{uuid.uuid4().hex[:12]}"
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

        # 6. Specific metadata (recipient bank details or bill details)
        specific_metadata = self._build_specific_metadata(payload)

        # 7. Assemble standardized output dictionary
        quote_response: Dict[str, Any] = {
            "quote_id": quote_id,
            "payment_type": self._get_payment_type(payload),
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
            **specific_metadata,
        }

        return quote_response

    def get_quote_json(self, request_data: Union[Dict[str, Any], str], indent: Optional[int] = 2) -> str:
        """
        Convenience method to execute quote retrieval and return a formatted JSON string.
        """
        quote_dict = self.get_quote(request_data)
        return json.dumps(quote_dict, indent=indent, default=str)

    # =========================================================================
    # Abstract Template Methods (Must be implemented by subclasses)
    # =========================================================================

    @abstractmethod
    def _validate_specific(self, payload: Dict[str, Any]) -> None:
        """Validate fields unique to this payment type (e.g. bank info or bill info)."""
        pass

    @abstractmethod
    def _get_payment_type(self, payload: Dict[str, Any]) -> str:
        """Return the payment type identifier string."""
        pass

    @abstractmethod
    def _build_specific_metadata(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Construct the specific metadata dict (e.g., recipient or bill information)."""
        pass

    # =========================================================================
    # Internal Utility & Calculation Methods
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
            raise QuoteValidationError(f"Request data must be dict or JSON string, received {type(request_data).__name__}.")

    def _validate_common(self, payload: Dict[str, Any]) -> None:
        """Validates parameters common to all quotes."""
        if "amount_ngn" not in payload:
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
        """
        Returns the destination wallet address to which the user should make the transfer.
        In a production setup, this can be provided by an off-ramp liquidity provider or
        derived from a centralized deposit pool.
        """
        return self.MOCK_DEPOSIT_ADDRESSES.get(network, self.MOCK_DEPOSIT_ADDRESSES[Network.SOLANA.value])

    def _build_blockchain_metadata(
        self,
        network: str,
        token: str,
        wallet_address: str,
        crypto_amount: float,
        quote_id: str,
    ) -> Dict[str, Any]:
        """
        Builds all metadata and payloads needed for a web3 client or mobile wallet
        (Phantom, MetaMask, Solana Pay, etc.) to perform the blockchain payment.
        """
        token_contract = self.TOKEN_CONTRACT_ADDRESSES.get(network, {}).get(token, "")
        chain_id = self.CHAIN_IDS.get(network, 101)
        token_decimals = 6  # USDC / USDT standard decimals
        reference = f"ref_{quote_id}"

        # Construct payment URIs for QR codes and deep-linking
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
            # EVM formatted URI (ERC-20 token transfer)
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


class BankTransferQuoteService(BaseQuoteService):
    """
    Quote generation service for Bank Transfers.
    
    Requires recipient bank details:
    - account_number (10 digits)
    - bank_code (e.g. 3-digit CBN code)
    - bank_name
    - account_name
    """

    def _get_payment_type(self, payload: Dict[str, Any]) -> str:
        return PaymentType.BANK_TRANSFER.value

    def _validate_specific(self, payload: Dict[str, Any]) -> None:
        """
        Validates the recipient bank information required to process the bank transfer.
        Accepts either a nested 'recipient' dictionary or top-level recipient fields.
        """
        recipient_data = payload.get("recipient")
        if isinstance(recipient_data, dict):
            account_number = recipient_data.get("account_number")
            bank_code = recipient_data.get("bank_code")
            bank_name = recipient_data.get("bank_name")
            account_name = recipient_data.get("account_name")
        else:
            account_number = payload.get("account_number")
            bank_code = payload.get("bank_code")
            bank_name = payload.get("bank_name")
            account_name = payload.get("account_name")

        # Allow passing recipient_id if already saved, but if details are missing and no id, reject
        recipient_id = payload.get("recipient_id") or (recipient_data.get("id") if isinstance(recipient_data, dict) else None)

        if not recipient_id and not (account_number and bank_code):
            raise QuoteValidationError(
                "Recipient bank information is required for bank transfer quotes. "
                "Must provide 'account_number', 'bank_code', 'bank_name', and 'account_name' (or 'recipient_id')."
            )

        if account_number is not None:
            account_number_str = str(account_number).strip()
            if not (account_number_str.isdigit() and len(account_number_str) == 10):
                raise QuoteValidationError(
                    f"Invalid bank account number '{account_number}'. Nigerian NUBAN account number must be 10 digits."
                )

        if bank_code is not None and not str(bank_code).strip():
            raise QuoteValidationError("Invalid 'bank_code': bank code cannot be empty.")

        if bank_name is not None and not str(bank_name).strip():
            raise QuoteValidationError("Invalid 'bank_name': bank name cannot be empty.")

        if account_name is not None and not str(account_name).strip():
            raise QuoteValidationError("Invalid 'account_name': recipient account name cannot be empty.")

    def _build_specific_metadata(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extracts recipient bank details and returns structured recipient metadata.
        """
        recipient_data = payload.get("recipient")
        if isinstance(recipient_data, dict):
            account_number = str(recipient_data.get("account_number", "")).strip()
            bank_code = str(recipient_data.get("bank_code", "")).strip()
            bank_name = str(recipient_data.get("bank_name", "")).strip()
            account_name = str(recipient_data.get("account_name", "")).strip()
            recipient_id = recipient_data.get("id") or recipient_data.get("recipient_id")
        else:
            account_number = str(payload.get("account_number", "")).strip()
            bank_code = str(payload.get("bank_code", "")).strip()
            bank_name = str(payload.get("bank_name", "")).strip()
            account_name = str(payload.get("account_name", "")).strip()
            recipient_id = payload.get("recipient_id")

        return {
            "recipient": {
                "account_number": account_number,
                "bank_code": bank_code,
                "bank_name": bank_name,
                "account_name": account_name,
                "recipient_id": recipient_id,
            }
        }


class BillQuoteService(BaseQuoteService):
    """
    Quote generation service for Bill Payments.
    
    Requires bill payment details:
    - category: AIRTIME, DATA, ELECTRICITY, or TV
    - customer_id: Phone number, meter number, or smartcard number
    - biller_name / provider: Telco, Disco, or Cable TV provider name
    - product_id: (Optional/Required depending on bundle)
    """

    VALID_CATEGORIES = [c.value for c in BillCategory]

    def _get_payment_type(self, payload: Dict[str, Any]) -> str:
        category = str(payload.get("category", payload.get("type", "BILL_PAYMENT"))).upper()
        return category if category in self.VALID_CATEGORIES else "BILL_PAYMENT"

    def _validate_specific(self, payload: Dict[str, Any]) -> None:
        """
        Validates bill payment details (category, customer ID, biller/provider).
        Accepts either nested 'bill_details' or top-level bill fields.
        """
        bill_data = payload.get("bill_details")
        if isinstance(bill_data, dict):
            category = bill_data.get("category") or bill_data.get("type")
            customer_id = bill_data.get("customer_id") or bill_data.get("phone_number") or bill_data.get("meter_number")
            biller_name = bill_data.get("biller_name") or bill_data.get("provider") or bill_data.get("biller_code")
        else:
            category = payload.get("category") or payload.get("type")
            customer_id = payload.get("customer_id") or payload.get("phone_number") or payload.get("meter_number")
            biller_name = payload.get("biller_name") or payload.get("provider") or payload.get("biller_code")

        if not category:
            raise QuoteValidationError(
                f"Missing bill 'category'. Must be one of {self.VALID_CATEGORIES}."
            )

        category_str = str(category).upper()
        if category_str not in self.VALID_CATEGORIES:
            raise QuoteValidationError(
                f"Invalid bill category '{category}'. Must be one of {self.VALID_CATEGORIES}."
            )

        if not customer_id or not str(customer_id).strip():
            field_hint = {
                BillCategory.AIRTIME.value: "phone number",
                BillCategory.DATA.value: "phone number",
                BillCategory.ELECTRICITY.value: "meter number",
                BillCategory.TV.value: "smartcard/IUC number",
            }.get(category_str, "customer identifier")
            raise QuoteValidationError(
                f"Missing 'customer_id' for bill payment ({field_hint})."
            )

    def _build_specific_metadata(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extracts bill details and returns structured bill payment metadata.
        """
        bill_data = payload.get("bill_details")
        if isinstance(bill_data, dict):
            category = str(bill_data.get("category") or bill_data.get("type", "")).upper()
            customer_id = str(bill_data.get("customer_id") or bill_data.get("phone_number") or bill_data.get("meter_number", "")).strip()
            biller_name = bill_data.get("biller_name") or bill_data.get("provider") or bill_data.get("biller_code")
            product_id = bill_data.get("product_id")
            customer_name = bill_data.get("customer_name")
        else:
            category = str(payload.get("category") or payload.get("type", "")).upper()
            customer_id = str(payload.get("customer_id") or payload.get("phone_number") or payload.get("meter_number", "")).strip()
            biller_name = payload.get("biller_name") or payload.get("provider") or payload.get("biller_code")
            product_id = payload.get("product_id")
            customer_name = payload.get("customer_name")

        return {
            "bill_details": {
                "category": category,
                "customer_id": customer_id,
                "biller_name": biller_name,
                "product_id": product_id,
                "customer_name": customer_name,
            }
        }


class QuoteServiceFactory:
    """
    Factory to obtain the appropriate quote service implementation.
    """

    @staticmethod
    def create(quote_type: str, **kwargs: Any) -> BaseQuoteService:
        quote_type_normalized = quote_type.strip().upper()
        if quote_type_normalized in ["BANK_TRANSFER", "TRANSFER", "OFFRAMP"]:
            return BankTransferQuoteService(**kwargs)
        elif quote_type_normalized in ["BILL", "BILL_PAYMENT", "AIRTIME", "DATA", "ELECTRICITY", "TV"]:
            return BillQuoteService(**kwargs)
        else:
            raise ValueError(
                f"Unknown quote type '{quote_type}'. Expected 'BANK_TRANSFER' or bill payment category."
            )
