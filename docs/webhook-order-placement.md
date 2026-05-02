# Webhook Order Placement

When a trading signal is parsed from a Telegram channel, the listener can automatically place an order by posting to the [xchange-line-bot](https://github.com/dchou/xchange-mcp-line-bot) TradingView-compatible webhook. The webhook handles exchange connectivity and sends the execution result back to you via LINE.

## How it works

```
Telegram channel message
        │
        ▼
  parse_signal()          extracts symbol, direction, entry, TP, SL, exchange
        │
        ▼
  _call_webhook()         POST to xchange-line-bot /webhook/tradingview
        │
        ├─ success ──▶  🔗 Order sent   (appended to Telegram alert)
        └─ failure ──▶  ❌ Order failed  (appended to Telegram alert)
                                │
                                ▼
                     xchange-line-bot places the order
                     and pushes the result to LINE
```

## Configuration

Add these variables to your `.env`:

| Variable | Required | Description |
|---|---|---|
| `WEBHOOK_URL` | Yes | Webhook endpoint, e.g. `https://xchange-line.ezcoin.cc/webhook/tradingview` |
| `WEBHOOK_SECRET` | Yes | Your personal secret token — get it from `/mywebhook` in the LINE bot |
| `WEBHOOK_EXCHANGE` | Yes | Exchange to execute on, e.g. `bybit`, `binance` |
| `WEBHOOK_AMOUNT` | Yes | Order size in base currency, e.g. `0.01` |
| `WEBHOOK_MARKET_TYPE` | — | `spot` or `swap` (default: `spot`) |

All four required fields must be set for webhook calls to fire. If any is missing or `WEBHOOK_AMOUNT` is `0`, the feature is silently disabled and the Telegram alert is sent as usual.

## Webhook payload

The listener maps the parsed signal to the webhook format:

| Webhook field | Source |
|---|---|
| `secret` | `WEBHOOK_SECRET` |
| `exchange` | `WEBHOOK_EXCHANGE` (always the configured exchange, not the signal's exchange) |
| `symbol` | `signal["symbol"]` with `_` replaced by `/` |
| `side` | `signal["direction"].lower()` → `"buy"` or `"sell"` |
| `amount` | `WEBHOOK_AMOUNT` |
| `market_type` | `WEBHOOK_MARKET_TYPE` |
| `price` | `signal["entry"]` — only included when entry is a single float (limit order). Omitted for zone-range entries → market order |

Example payload sent for a CQSScalpingFree signal:

```json
{
  "secret": "cf6bb9be9afe3042d89d1beabe16ff92",
  "exchange": "bybit",
  "symbol": "USD/NMR",
  "side": "buy",
  "amount": 0.01,
  "price": 8.82,
  "market_type": "spot"
}
```

Example payload for a QualitySignalsChannel signal (entry zone → market order):

```json
{
  "secret": "cf6bb9be9afe3042d89d1beabe16ff92",
  "exchange": "bybit",
  "symbol": "WLD/USD",
  "side": "buy",
  "amount": 0.01,
  "market_type": "spot"
}
```

## Telegram alert with order status

The order result is appended as the last line of the Telegram alert:

```
🟢 BUY WLD/USD (CRYPTOCOM) [CRYPTO]
━━━━━━━━━━━━━━━━━━━━
📢 QualitySignalsChannel | 05-02 14:04 UTC
📥 Entry: 0.22827520 - 0.23715520
🎯 TP: 0.240352 | 0.2453248 | 0.2495872
🛑 SL: 0.2254336
🔗 Order sent
```

## Getting your webhook secret

1. Open the LINE bot and send `/mywebhook`
2. Copy the secret from the displayed JSON template
3. Set it as `WEBHOOK_SECRET` in your `.env`

## Notes

- The webhook call has a 10-second timeout. If it exceeds this, the Telegram alert still goes out with `❌ Order failed`.
- `WEBHOOK_EXCHANGE` is always used for order execution — the exchange name embedded in a signal (e.g. `KRAKEN`, `CRYPTOCOM`) indicates where the signal originated, not where you trade.
- Order amount is always taken from `WEBHOOK_AMOUNT`. Signal amount fields (e.g. `"3.0%"`) are displayed in the alert but not used for sizing.
