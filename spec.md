Absolutely. The backend should be designed around one core rule:

> **Your app orchestrates payments. It never receives, holds, signs, or transfers the user's crypto.**

The provider owns the crypto-to-fiat settlement flow. Your backend creates the provider order, receives the provider's deposit instructions, gives those instructions to the Flutter app, and tracks the resulting payment.

Here is the implementation plan I would use for the prototype.


# 1. Architecture

Use a **modular monolith**:

```text
Flutter
   │
   │ HTTPS REST
   ▼
┌──────────────────────────────────────────┐
│                 FastAPI                  │
│                                          │
│ Auth                                     │
│ Users                                    │
│ Wallets                                  │
│ Quotes                                   │
│ Payments                                 │
│ Recipients                               │
│ Bills                                    │
│ Transactions                             │
│ Notifications                            │
│ Webhooks                                 │
└──────────────────┬───────────────────────┘
                   │
          ┌────────┴────────┐
          ▼                 ▼
    PostgreSQL            Redis
                           │
                           ▼
                        Celery
                           │
             ┌─────────────┼──────────────┐
             ▼             ▼              ▼
        Provider       Notifications   Maintenance
        workers
             │
             ▼
     External providers
```

For the prototype:

- PostgreSQL = source of truth
- FastAPI = API + business orchestration
- Celery = asynchronous/reconciliation work
- Redis = Celery broker
- External crypto/payment infrastructure = mocked
- No blockchain infrastructure inside your backend
- No crypto custody

---

# 2. Backend modules

Organize the backend around business domains:

```text
app/
├── auth
├── users
├── wallets
├── quotes
├── payments
├── recipients
├── bills
├── transactions
├── notifications
├── providers
├── webhooks
└── common
```

Don't create separate microservices.

---

# 3. Authentication

The user needs an application identity independent of their blockchain wallet.

Prototype APIs:

```http
POST /api/v1/auth/register
POST /api/v1/auth/login
POST /api/v1/auth/refresh
POST /api/v1/auth/logout
GET  /api/v1/auth/me
```

If using email/password:

```text
email
password
name
```

Later you can add:

- email verification
- Google/Apple authentication
- passkeys
- wallet-based authentication

But don't block the prototype on these.

## Authentication model

Use:

```text
access token
refresh token
```

JWT access tokens are sufficient for the prototype.

---

# 4. Users

User endpoints:

```http
GET   /api/v1/users/me
PATCH /api/v1/users/me
DELETE /api/v1/users/me
```

User model:

```text
users
─────
id
email
name
phone
avatar_url
status
created_at
updated_at
```

Keep `status` simple:

```text
ACTIVE
SUSPENDED
DELETED
```

Don't build a full KYC system yet.

---

# 5. Wallet connection

A wallet is connected to the user's application account.

The backend should **never receive private keys or seed phrases**.

Supported networks:

```text
ETHEREUM
POLYGON
SOLANA
```

Wallet APIs:

```http
POST   /api/v1/wallets/connect
GET    /api/v1/wallets
GET    /api/v1/wallets/{wallet_id}
DELETE /api/v1/wallets/{wallet_id}
GET    /api/v1/wallets/{wallet_id}/accounts
```

Example:

```json
{
  "provider": "phantom",
  "accounts": [
    {
      "network": "solana",
      "address": "7xK..."
    }
  ]
}
```

Eventually the wallet connection should use signed challenges/nonces.

For the prototype, mock the wallet verification.

---

# 6. Wallet data model

Don't store one address directly on `users`.

Use:

```text
wallets
───────
id
user_id
provider
created_at
updated_at
```

and:

```text
wallet_accounts
───────────────
id
wallet_id
network
address
created_at
updated_at
```

Example:

```text
Wallet
  │
  ├── Ethereum → 0xABC...
  ├── Polygon  → 0xABC...
  └── Solana   → 7xK...
```

This matches your multi-chain UX.

---

# 7. Wallet balances

The backend doesn't own the balances.

For the prototype, expose:

```http
GET /api/v1/wallets/balances
```

Return mocked balances:

```json
{
  "total_usdc": 450.70,
  "networks": [
    {
      "network": "solana",
      "usdc_balance": 250.00
    },
    {
      "network": "polygon",
      "usdc_balance": 120.50
    },
    {
      "network": "ethereum",
      "usdc_balance": 80.20
    }
  ]
}
```

Later this can come from a wallet/balance provider.

The important architectural distinction is:

```text
Your DB:
    knows user's wallet addresses

External blockchain/provider:
    knows actual balances
```

---

# 8. Supported assets and networks

Create a simple configuration layer.

```text
GET /api/v1/config
```

Response:

```json
{
  "networks": [
    "ethereum",
    "polygon",
    "solana"
  ],
  "assets": [
    "USDC"
  ]
}
```

This allows Flutter to avoid hardcoding product configuration.

---

# 9. Quotes

Quotes should be their own domain.

A quote represents:

> "If you want to pay ₦100,000 right now, this is how much USDC you need."

API:

```http
POST /api/v1/quotes
GET  /api/v1/quotes/{quote_id}
```

Request:

```json
{
  "type": "BANK_TRANSFER",
  "amount_ngn": 100000,
  "recipient_id": "recipient_123"
}
```

Response:

```json
{
  "id": "quote_123",
  "amount_ngn": 100000,
  "crypto_asset": "USDC",
  "crypto_amount": 67.68,
  "network": "SOLANA",
  "platform_fee": 500,
  "provider_fee": 200,
  "expires_at": "..."
}
```

For the prototype:

```text
exchange rate → mocked
provider fee → mocked
network → mocked
```

---

# 10. Provider abstraction

This is the most important backend abstraction.

Create:

```text
providers/
    offramp/
        base.py
        mock.py
```

Interface:

```text
OffRampProvider

create_quote()
create_order()
get_order()
cancel_order()
verify_webhook()
```

Later:

```text
providers/
    offramp/
        base.py
        mock.py
        real_provider.py
```

Your payment service doesn't care which provider you're using.

---

# 11. Creating an off-ramp order

This is the heart of the product.

When the user wants:

```text
₦100,000 → Nigerian bank account
```

your backend calls the provider.

Conceptually:

```text
FastAPI
   │
   ▼
OffRampProvider.create_order()
   │
   ▼
Provider
   │
   ▼
Provider order
```

The provider returns:

```json
{
  "provider_order_id": "ord_123",
  "crypto_asset": "USDC",
  "crypto_amount": 67.68,
  "network": "SOLANA",
  "deposit_address": "PROVIDER_ADDRESS",
  "status": "AWAITING_CRYPTO"
}
```

Your backend stores those details.

**The provider deposit address belongs to the provider.**

Your backend does not create it.

---

# 12. Payment model

Create:

```text
payments
```

Suggested fields:

```text
id
user_id
quote_id
recipient_id

type
status

fiat_currency
fiat_amount

crypto_asset
crypto_amount
network

wallet_account_id
user_wallet_address

provider
provider_order_id
provider_deposit_address
provider_reference

failure_reason

created_at
updated_at
completed_at
```

Notice:

```text
NO private key
NO seed phrase
NO crypto custody
```

---

# 13. Payment state machine

Use explicit states:

```text
CREATED
AWAITING_WALLET
PROVIDER_ORDER_CREATED
AWAITING_CRYPTO
CRYPTO_RECEIVED
PROCESSING
COMPLETED
FAILED
CANCELLED
EXPIRED
```

Flow:

```text
CREATED
   ↓
PROVIDER_ORDER_CREATED
   ↓
AWAITING_CRYPTO
   ↓
CRYPTO_RECEIVED
   ↓
PROCESSING
   ↓
COMPLETED
```

The provider determines when the crypto is received.

Your backend simply records the provider's state.

---

# 14. Payment APIs

```http
POST /api/v1/payments
GET  /api/v1/payments
GET  /api/v1/payments/{payment_id}
POST /api/v1/payments/{payment_id}/cancel
```

Creating a payment:

```json
{
  "quote_id": "quote_123",
  "recipient_id": "recipient_123",
  "wallet_account_id": "wallet_account_123"
}
```

Backend:

```text
1. Validate quote
2. Validate recipient
3. Validate wallet account
4. Create payment
5. Call provider
6. Receive deposit address
7. Store provider order
8. Return payment instructions
```

Response:

```json
{
  "id": "payment_123",
  "status": "AWAITING_CRYPTO",
  "crypto_amount": 67.68,
  "asset": "USDC",
  "network": "SOLANA",
  "deposit_address": "PROVIDER_ADDRESS"
}
```

Flutter then opens the user's wallet.

---

# 15. Crypto never passes through your backend

The actual transaction is:

```text
User wallet
     │
     │ 67.68 USDC
     ▼
Provider deposit address
```

Your system sees:

```text
payment status
provider order
provider webhook
transaction metadata
```

It does **not** see or control the crypto transfer.

---

# 16. Recipient management

Bank recipients:

```http
POST   /api/v1/recipients
GET    /api/v1/recipients
GET    /api/v1/recipients/{id}
PATCH  /api/v1/recipients/{id}
DELETE /api/v1/recipients/{id}
POST   /api/v1/recipients/verify
```

Model:

```text
recipients
──────────
id
user_id
type
bank_code
bank_name
account_number
account_name
created_at
```

For prototype:

```text
verify account
      ↓
MockBankProvider
      ↓
"John Doe"
```

Later replace it with your real provider.

---

# 17. Bills

Treat bills as another payment product.

Supported:

```text
AIRTIME
DATA
ELECTRICITY
TV
```

APIs:

```http
GET  /api/v1/bills/services
POST /api/v1/bills/verify
POST /api/v1/bills/quote
POST /api/v1/bills/orders
GET  /api/v1/bills/orders/{id}
```

Example:

```json
{
  "type": "AIRTIME",
  "phone_number": "08012345678",
  "amount_ngn": 5000
}
```

Again:

```text
BillProvider
    ↓
MockBillProvider
```

No real provider yet.

---

# 18. Bill providers

Use:

```text
providers/
    bills/
        base.py
        mock.py
```

Interface:

```text
verify_customer()
get_products()
create_order()
get_order()
```

Later you can plug in the real bill provider without changing your Flutter-facing APIs.

---

# 19. On-ramp

If you decide to support:

```text
₦ → USDC → user's wallet
```

give it its own module.

```http
POST /api/v1/onramp/quotes
POST /api/v1/onramp/orders
GET  /api/v1/onramp/orders/{id}
POST /api/v1/onramp/orders/{id}/cancel
```

The provider would give you something like:

```text
bank name
account number
account name
amount to transfer
reference
USDC amount
destination wallet
status
```

Your backend orchestrates the order but the provider handles conversion and crypto delivery.

---

# 20. Transactions

Create a unified transaction history.

```http
GET /api/v1/transactions
GET /api/v1/transactions/{id}
```

Types:

```text
BANK_TRANSFER
AIRTIME
DATA
ELECTRICITY
TV
ONRAMP
OFFRAMP
```

Example:

```json
{
  "id": "tx_123",
  "type": "BANK_TRANSFER",
  "status": "COMPLETED",
  "amount_ngn": 100000,
  "amount_usdc": 67.68,
  "network": "SOLANA",
  "created_at": "..."
}
```

Flutter doesn't need to know whether the underlying transaction came from an off-ramp provider, bill provider, etc.

---

# 21. Transaction details

```http
GET /api/v1/transactions/{id}
```

Return:

```text
NGN amount
USDC amount
exchange rate
fees
recipient
network
status
provider reference
created date
```

Blockchain details can remain optional.

For example:

```text
Advanced details
    Network: Solana
    Transaction: 8x7...abc
```

The actual blockchain transaction hash can come from the provider webhook/order status.

---

# 22. Webhooks

This is essential.

```http
POST /api/v1/webhooks/{provider}
```

Provider events might include:

```text
ORDER_CREATED
CRYPTO_RECEIVED
PROCESSING
COMPLETED
FAILED
```

Webhook flow:

```text
Provider
   │
   ▼
FastAPI webhook
   │
   ├── verify signature
   ├── check event ID
   ├── store webhook
   └── enqueue Celery task
              │
              ▼
        process event
              │
              ▼
        update payment
```

---

# 23. Webhook event table

Create:

```text
webhook_events
```

Fields:

```text
id
provider
event_id
event_type
payload
status
processed_at
created_at
```

Put a unique constraint on:

```text
(provider, event_id)
```

That makes webhook processing idempotent.

If a provider sends the same webhook five times, you process it once.

---

# 24. Celery workers

You don't need dozens of workers.

Start with:

```text
workers/
├── payments.py
├── onramp.py
├── bills.py
├── notifications.py
└── maintenance.py
```

Important tasks:

### Payment reconciliation

```text
reconcile_payment(payment_id)
```

Checks provider status.

### Webhook processing

```text
process_provider_webhook(event_id)
```

### Notification

```text
send_payment_notification(payment_id)
```

### Bill processing

```text
reconcile_bill_order(order_id)
```

### On-ramp

```text
reconcile_onramp_order(order_id)
```

---

# 25. Celery Beat

Use scheduled tasks for reconciliation.

For example:

```text
Every 1 minute:
    find pending provider orders
    query provider
    update status
```

And:

```text
Every 5 minutes:
    find stuck bill orders
    reconcile
```

And:

```text
Every 10 minutes:
    expire old quotes
```

This is a safety net even when provider webhooks fail.

---

# 26. Notifications

API:

```http
GET  /api/v1/notifications
POST /api/v1/notifications/{id}/read
POST /api/v1/notifications/read-all
```

Backend events:

```text
Payment completed
Payment failed
Payment processing
Quote expired
On-ramp completed
```

Celery can send push notifications.

For the prototype, you can mock the actual push provider.

---

# 27. Activity feed

Don't make Flutter construct activity from multiple endpoints.

Have:

```http
GET /api/v1/activity
```

or use:

```http
GET /api/v1/transactions
```

with pagination:

```text
?page=1
&page_size=20
```

Response:

```json
{
  "items": [],
  "next_cursor": "..."
}
```

I'd eventually use cursor pagination rather than page-number pagination.

---

# 28. Home dashboard

The home screen needs a lightweight endpoint:

```http
GET /api/v1/home
```

Return:

```json
{
  "wallet": {
    "connected": true,
    "total_usdc": 450.70
  },
  "recent_transactions": [],
  "services": [
    "SEND_MONEY",
    "AIRTIME",
    "DATA",
    "ELECTRICITY",
    "TV"
  ]
}
```

This prevents Flutter from making five requests just to render Home.

---

# 29. Configuration API

Have:

```http
GET /api/v1/config
```

Return things like:

```text
supported networks
supported assets
bill categories
minimum payment
maximum payment
feature flags
```

Example:

```json
{
  "supported_networks": [
    "ethereum",
    "polygon",
    "solana"
  ],
  "supported_assets": [
    "USDC"
  ],
  "features": {
    "onramp": true,
    "offramp": true,
    "airtime": true,
    "data": true,
    "electricity": true,
    "tv": true
  }
}
```

---

# 30. Database tables

For the prototype, I'd start with:

```text
users

wallets
wallet_accounts

recipients

quotes

payments
payment_attempts

onramp_orders
offramp_orders

bill_orders

transactions

notifications

webhook_events
```

You can keep the actual provider-specific details in the corresponding order/payment records.

---

# 31. Payment attempts

Keep this table:

```text
payment_attempts
────────────────
id
payment_id
provider
provider_order_id
status
request_reference
error_code
error_message
created_at
updated_at
```

This gives you a history when a provider operation fails/retries.

---

# 32. Idempotency

This is extremely important for payments.

Every payment-creating request should support:

```http
Idempotency-Key: abc123
```

If Flutter accidentally sends:

```text
POST /payments
POST /payments
```

because the network timed out, you must **not create two provider orders**.

Store the idempotency key.

```text
user_id + idempotency_key
```

must be unique.

---

# 33. Provider abstraction

Your code should essentially look like:

```text
PaymentService
      │
      ▼
OffRampProvider
      │
      ├── MockOffRampProvider
      │
      └── RealOffRampProvider
```

For bills:

```text
BillService
      │
      ▼
BillProvider
      │
      ├── MockBillProvider
      │
      └── RealBillProvider
```

For on-ramp:

```text
OnRampService
      │
      ▼
OnRampProvider
```

This lets you develop the complete app now without waiting for provider contracts.

---

# 34. Project structure

```text
app/
│
├── main.py
│
├── core/
│   ├── config.py
│   ├── security.py
│   ├── dependencies.py
│   └── exceptions.py
│
├── api/
│   └── v1/
│       ├── auth.py
│       ├── users.py
│       ├── wallets.py
│       ├── quotes.py
│       ├── payments.py
│       ├── recipients.py
│       ├── bills.py
│       ├── onramp.py
│       ├── offramp.py
│       ├── transactions.py
│       ├── activity.py
│       ├── notifications.py
│       ├── config.py
│       └── webhooks.py
│
├── models/
│   ├── user.py
│   ├── wallet.py
│   ├── quote.py
│   ├── payment.py
│   ├── recipient.py
│   ├── bill.py
│   ├── transaction.py
│   └── webhook.py
│
├── schemas/
│   ├── auth.py
│   ├── user.py
│   ├── wallet.py
│   ├── quote.py
│   ├── payment.py
│   ├── recipient.py
│   ├── bill.py
│   └── transaction.py
│
├── services/
│   ├── auth_service.py
│   ├── wallet_service.py
│   ├── quote_service.py
│   ├── payment_service.py
│   ├── recipient_service.py
│   ├── bill_service.py
│   ├── onramp_service.py
│   ├── transaction_service.py
│   └── notification_service.py
│
├── providers/
│   ├── offramp/
│   │   ├── base.py
│   │   └── mock.py
│   │
│   ├── onramp/
│   │   ├── base.py
│   │   └── mock.py
│   │
│   └── bills/
│       ├── base.py
│       └── mock.py
│
├── workers/
│   ├── celery_app.py
│   ├── payments.py
│   ├── onramp.py
│   ├── bills.py
│   ├── notifications.py
│   └── maintenance.py
│
└── db/
    ├── session.py
    └── migrations/
```

---

# 35. Implementation order

Don't build everything at once.

## Phase 1 — Foundation

Build:

```text
PostgreSQL
FastAPI
SQLAlchemy/SQLModel
Alembic
Pydantic
JWT
Redis
Celery
```

Then:

```text
User
Auth
```

---

## Phase 2 — Wallet

Build:

```text
Wallet
WalletAccount
```

Then:

```text
connect wallet
get wallets
get balances
disconnect wallet
```

Use mocked balances.

---

## Phase 3 — Recipient

Build:

```text
create recipient
verify recipient
list recipients
```

Mock the bank-account verification.

---

## Phase 4 — Quote

Build:

```text
POST /quotes
```

Make it produce:

```text
NGN amount
USDC amount
exchange rate
fees
network
expiry
```

Now the Flutter review screen can work.

---

# 36. Phase 5 — The critical vertical slice

Build this **before anything else**:

```text
Connect wallet
      ↓
Select Send Money
      ↓
Enter ₦ amount
      ↓
Select recipient
      ↓
Get quote
      ↓
Create provider order
      ↓
Provider returns:
    deposit address
    USDC amount
    network
      ↓
Show payment instructions
      ↓
User sends USDC
      ↓
Provider detects crypto
      ↓
Provider processes NGN payout
      ↓
Provider webhook
      ↓
FastAPI
      ↓
PostgreSQL
      ↓
Celery notification
      ↓
Success
```

This proves the actual product.

---

# 37. Phase 6 — Transactions

Once the payment works:

```text
GET /transactions
GET /transactions/{id}
```

Connect:

```text
Home recent activity
Activity screen
Transaction details
Receipt
```

---

# 38. Phase 7 — Bills

Then add:

```text
Airtime
Data
Electricity
TV
```

using the same architecture:

```text
Flutter
   ↓
FastAPI
   ↓
BillService
   ↓
BillProvider
   ↓
Mock provider
```

---

# 39. Phase 8 — On-ramp

Then implement:

```text
NGN
 ↓
provider bank account
 ↓
provider conversion
 ↓
USDC
 ↓
user wallet
```

The provider owns the actual crypto movement.

Your backend tracks:

```text
onramp order
fiat payment status
crypto delivery status
```

---

# 40. Prototype infrastructure

Keep it extremely small:

```text
FastAPI
   │
   ├── PostgreSQL
   │
   └── Redis
          │
          └── Celery Worker
```

You don't need:

```text
Kafka
RabbitMQ
Kubernetes
microservices
blockchain nodes
custody infrastructure
crypto wallets
```

at this stage.

---

# 41. What should be mocked

Mock:

```text
Provider quote
Provider order creation
Provider deposit address
Provider crypto detection
Provider NGN settlement
Bank-account verification
Bill providers
USDC balances
Push notifications
```

But make the **interfaces real**.

So eventually:

```text
MockOffRampProvider
        ↓
RealOffRampProvider
```

without changing:

```text
Flutter
FastAPI routes
PaymentService
Database
payment state machine
```

---

# 42. Final prototype scope

When you're finished, the prototype should support:

```text
AUTH
├── Register
├── Login
└── Current user

WALLET
├── Connect wallet
├── Ethereum
├── Polygon
├── Solana
├── Balances
└── Disconnect

PAYMENTS
├── Quote
├── Create provider order
├── Get deposit instructions
├── Track status
└── Cancel

BANK
├── Add recipient
├── Verify account
└── Manage recipients

BILLS
├── Airtime
├── Data
├── Electricity
└── TV

ON-RAMP
├── Quote
├── Create order
├── Bank transfer instructions
└── Track delivery

ACTIVITY
├── Transactions
├── Transaction details
└── Receipt

NOTIFICATIONS
├── List
├── Read
└── Push

INFRASTRUCTURE
├── PostgreSQL
├── Redis
├── Celery
├── Provider adapters
└── Webhooks
```

The **most important architectural boundary** is this:

```text
                    YOUR APP
                       │
                       │ payment/order API
                       ▼
              ┌──────────────────┐
              │ Provider Adapter  │
              └────────┬─────────┘
                       │
                       ▼
                 REAL PROVIDER
                       │
              ┌────────┴─────────┐
              │                  │
         Crypto side         Fiat side
              │                  │
      User wallet          Nigerian bank
```

Your backend **never sits between the user's wallet and the provider's deposit address**. It only tells the user **where, how much, and on which network to pay**, then tracks what the provider reports.

That is the architecture I'd build the prototype around.