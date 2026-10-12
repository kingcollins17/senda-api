import enum


class UserStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    DELETED = "DELETED"


class AuthProvider(str, enum.Enum):
    NORMAL = "NORMAL"
    GOOGLE = "GOOGLE"
    APPLE = "APPLE"



class Network(str, enum.Enum):
    ETHEREUM = "ETHEREUM"
    POLYGON = "POLYGON"
    SOLANA = "SOLANA"


class PaymentType(str, enum.Enum):
    BANK_TRANSFER = "BANK_TRANSFER"
    AIRTIME = "AIRTIME"
    DATA = "DATA"
    ELECTRICITY = "ELECTRICITY"
    TV = "TV"
    BETTING = "BETTING"


class PaymentStatus(str, enum.Enum):
    CREATED = "CREATED"
    AWAITING_WALLET = "AWAITING_WALLET"
    PROVIDER_ORDER_CREATED = "PROVIDER_ORDER_CREATED"
    AWAITING_CRYPTO = "AWAITING_CRYPTO"
    CRYPTO_RECEIVED = "CRYPTO_RECEIVED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"



class BillCategory(str, enum.Enum):
    AIRTIME = "AIRTIME"
    DATA = "DATA"
    ELECTRICITY = "ELECTRICITY"
    TV = "TV"
    BETTING = "BETTING"


class BillOrderStatus(str, enum.Enum):
    CREATED = "CREATED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class OnRampOrderStatus(str, enum.Enum):
    CREATED = "CREATED"
    AWAITING_FIAT = "AWAITING_FIAT"
    FIAT_RECEIVED = "FIAT_RECEIVED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class OffRampOrderStatus(str, enum.Enum):
    CREATED = "CREATED"
    AWAITING_CRYPTO = "AWAITING_CRYPTO"
    CRYPTO_RECEIVED = "CRYPTO_RECEIVED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class TransactionType(str, enum.Enum):
    BANK_TRANSFER = "BANK_TRANSFER"
    AIRTIME = "AIRTIME"
    DATA = "DATA"
    ELECTRICITY = "ELECTRICITY"
    TV = "TV"
    BETTING = "BETTING"
    ONRAMP = "ONRAMP"
    OFFRAMP = "OFFRAMP"


class TransactionStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class WebhookEventStatus(str, enum.Enum):
    RECEIVED = "RECEIVED"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"


class NotificationStatus(str, enum.Enum):
    UNREAD = "UNREAD"
    READ = "READ"
