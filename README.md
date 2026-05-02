# Signal Listener

Monitors Telegram trading channels, parses signal messages into structured data, and forwards formatted alerts via a Telegram bot.

## How it works

1. Connects to Telegram as a user account (Telethon) and subscribes to configured channels
2. On each new message, runs `parse_signal()` — a regex parser that extracts symbol, direction, entry, take-profits, stop-loss, exchange, leverage, and amount
3. If a signal is found, logs it as JSON and sends a formatted alert to your bot chat

Non-signal messages (news, promo, chatter) are silently dropped. On disconnect, the listener reconnects automatically with exponential backoff (5 s → 10 s → … → 300 s max).

## Parsed signal format

```json
{
  "symbol": "WLD/USD",
  "direction": "BUY",
  "entry": "0.22827520 - 0.23715520",
  "take_profits": [0.240352, 0.2453248, 0.2495872],
  "stop_loss": 0.2254336,
  "exchange": "CRYPTOCOM"
}
```

| Field | Type | Notes |
|---|---|---|
| `symbol` | string | e.g. `WLD/USD`, `USD_NMR` |
| `direction` | `"BUY"` or `"SELL"` | `LONG` → `BUY`, `SHORT` → `SELL` |
| `entry` | float or string | Float for a single price; `"X - Y"` string for an entry zone range |
| `take_profits` | list | Floats for absolute prices; `"1.6%"` string for percentage targets |
| `stop_loss` | float or string | Float for absolute price; `"-4.0%"` string for percentage |
| `exchange` | string | Optional — present when the channel includes an exchange name |
| `leverage` | string | Optional — e.g. `"15X"` |
| `amount` | string | Optional — e.g. `"3.0%"` |

## Supported channel formats

### CQSScalpingFree

Exchange on the first line, symbol as `#BASE_QUOTE`, entry as `Ask:`, target as `Target:`, SL as a percentage.

```
KRAKEN
#USD_NMR
LONG
🆔 #5175531
Ask: 8.82000000
Target: 8.96245000
TP: 1.6%
SL: -4.0%
```

Parsed result:
```json
{
  "symbol": "USD_NMR",
  "direction": "BUY",
  "entry": 8.82,
  "take_profits": [8.96245],
  "stop_loss": "-4.0%",
  "exchange": "KRAKEN"
}
```

### QualitySignalsChannel

Exchange as `at #EXCHANGE`, symbol as `#BASE/QUOTE`, entry as a zone range, numbered targets, and full `Stop loss:` label.

```
✳ New FREE signal

💎 BUY #WLD/USD at #CRYPTOCOM

📈 SPOT TRADE
🆔 #3948399
⏱ 02-May-2026 14:04:09 UTC

🛒 Entry Zone: 0.22827520 - 0.23715520
💵 Current ask: 0.23690000
🎯 Target 1: 0.24035200 (1.46%)
🎯 Target 2: 0.24532480 (3.56%)
🎯 Target 3: 0.24958720 (5.36%)
🚫 Stop loss: 0.22543360 (4.84%)
```

Parsed result:
```json
{
  "symbol": "WLD/USD",
  "direction": "BUY",
  "entry": "0.22827520 - 0.23715520",
  "take_profits": [0.240352, 0.2453248, 0.2495872],
  "stop_loss": 0.2254336,
  "exchange": "CRYPTOCOM"
}
```

### Generic formats

The parser also handles common inline formats used by many signal channels:

```
XAUUSD SELL 2726
TP1) 2710
TP2) 2700
SL: 2740
```

## Setup

**1. Install dependencies**

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**2. Create `.env`**

```bash
cp .env.example .env
```

Edit `.env` with your credentials (see [Configuration](#configuration)).

**3. Run**

```bash
python main.py
```

On first run, Telethon will prompt for your phone number and a verification code to create a session file under `sessions/`.

## Configuration

| Variable | Required | Description |
|---|---|---|
| `TELEGRAM_API_ID` | Yes | From [my.telegram.org](https://my.telegram.org) → API development tools |
| `TELEGRAM_API_HASH` | Yes | Same as above |
| `TELEGRAM_CHANNELS_CRYPTO` | — | Comma-separated channel usernames for CRYPTO signals |
| `TELEGRAM_CHANNELS_FOREX` | — | Comma-separated channel usernames for FOREX signals |
| `TELEGRAM_CHANNELS_INDICATORS` | — | Comma-separated channel usernames for INDICATORS signals |
| `TELEGRAM_BOT_TOKEN` | — | Bot token for sending alerts (from @BotFather). Alerts are skipped if not set |
| `TELEGRAM_CHAT_ID` | — | Comma-separated chat/user IDs to receive alerts |
| `MESSAGE_AGE_DAYS` | — | Skip messages older than this many days (default: 7) |

At least one channel list must be non-empty to start. The `@` prefix in channel names is optional.

## Project structure

```
main.py                  # Entry point
config.py                # Loads and validates env vars
bot/
  telegram_listener.py   # SignalListener class + parse_signal()
sessions/                # Telethon session files (auto-created, gitignored)
```

## Adding order logic

`_send_signal()` in `bot/telegram_listener.py` receives the parsed `signal` dict before sending the Telegram alert. Add your order placement code there:

```python
async def _send_signal(self, source, timestamp, category, signal):
    # place your order here using signal["symbol"], signal["direction"], etc.
    ...
```
