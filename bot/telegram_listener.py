"""
Signal Listener — Telegram Channel Listener
Listens to public Telegram channels and processes trading signals by category.
"""

import asyncio
import json
import os
import re
import time

from telethon import TelegramClient, events

from config import Config

SESSION_PATH = "sessions/telethon"


def parse_signal(text: str) -> dict | None:
    # Exchange: first line if plain all-caps word, or "at #EXCHANGE" pattern
    first_line = text.split('\n')[0].strip()
    exchange = first_line if re.fullmatch(r'[A-Z]{2,15}', first_line) else None
    if not exchange:
        exch_match = re.search(r'\bat\s+#([A-Z]{3,15})\b', text)
        if exch_match:
            exchange = exch_match.group(1)

    # Direction
    dir_match = re.search(r'\b(LONG|BUY|SHORT|SELL)\b', text, re.IGNORECASE)
    if not dir_match:
        return None
    direction = "BUY" if dir_match.group(1).upper() in ("LONG", "BUY") else "SELL"

    # Symbol: PAIR/BASE, then #BASE_QUOTE hashtag, then word before direction, then first all-caps line
    sym_match = re.search(r'\b([A-Z]{2,10}/[A-Z]{2,10})\b', text)
    if not sym_match:
        sym_match = re.search(r'#([A-Z]{2,10}_[A-Z]{2,10})\b', text)
    if not sym_match:
        sym_match = re.search(r'\b([A-Z]{3,10})\s+(?:LONG|BUY|SHORT|SELL)\b', text, re.IGNORECASE)
    if not sym_match:
        sym_match = re.search(r'^([A-Z]{3,10}(?:/[A-Z]{2,10})?)\b', text, re.MULTILINE)
    symbol = sym_match.group(1).upper() if sym_match else None

    # Entry: zone range ("Entry Zone: 0.228 - 0.237"), labeled block, "Ask:", or inline
    zone_match = re.search(r'[Ee]ntry\s+[Zz]one\s*:\s*([\d.]+\s*-\s*[\d.]+)', text)
    if zone_match:
        entry = zone_match.group(1).strip()
    else:
        entry_match = re.search(r'[Ee]ntry[^:\n]*:?\s*\n\s*\d*[).]\s*([\d.]+)', text)
        if not entry_match:
            entry_match = re.search(r'[Aa]sk\s*:\s*([\d.]+)', text)
        if not entry_match:
            entry_match = re.search(r'(?:LONG|BUY|SHORT|SELL)\s+([\d.]+)', text, re.IGNORECASE)
        entry = float(entry_match.group(1)) if entry_match else None

    # Take profits: numbered TP (TP1) 8.96), Target N: 8.96, or percentage (TP: 1.6%)
    take_profits = [float(p) for p in re.findall(r'[Tt][Pp]\s*\d+[).@]?\s*([\d.]+)', text)]
    if not take_profits:
        targets = re.findall(r'[Tt]arget\s*\d*\s*:\s*([\d.]+)', text)
        if targets:
            take_profits = [float(p) for p in targets]
        else:
            pct_tp = re.search(r'[Tt][Pp]\s*:\s*(-?[\d.]+%)', text)
            if pct_tp:
                take_profits = [pct_tp.group(1)]

    # Stop loss: percentage first (handles negative), then abbreviated SL, then full "Stop loss:"
    pct_sl = re.search(r'\b[Ss][Ll]\s*:\s*(-?[\d.]+%)', text)
    if pct_sl:
        stop_loss = pct_sl.group(1)
    else:
        sl_match = re.search(r'\b[Ss][Ll]\b[\s@:~\-]*([\d.]+)', text)
        if sl_match:
            stop_loss = float(sl_match.group(1))
        else:
            full_sl = re.search(r'[Ss]top\s+[Ll]oss\s*:\s*([\d.]+)', text)
            stop_loss = float(full_sl.group(1)) if full_sl else None

    if not symbol or entry is None:
        return None

    result: dict = {
        "symbol": symbol,
        "direction": direction,
        "entry": entry,
        "take_profits": take_profits,
        "stop_loss": stop_loss,
    }

    if exchange:
        result["exchange"] = exchange

    lev_match = re.search(r'(\d+)[Xx]', text)
    if lev_match:
        result["leverage"] = lev_match.group(0)

    amt_match = re.search(r'[Aa]mount\s*:?\s*([\d.]+%?)', text)
    if amt_match:
        result["amount"] = amt_match.group(1)

    return result


class SignalListener:
    def __init__(self, config: Config):
        self.config = config
        self._client: TelegramClient | None = None
        self._category_map: dict[int, str] = {}

    async def run(self) -> None:
        if not self.config.TELEGRAM_API_ID or not self.config.TELEGRAM_API_HASH:
            print("[TG] TELEGRAM_API_ID / TELEGRAM_API_HASH not set — skipping")
            return

        all_channels = self.config.get_all_channels()
        if not any(all_channels.values()):
            print("[TG] No TELEGRAM_CHANNELS configured — skipping")
            return

        os.makedirs("sessions", exist_ok=True)

        resolved: list | None = None
        backoff = 5

        while True:
            try:
                self._client = TelegramClient(
                    SESSION_PATH,
                    self.config.TELEGRAM_API_ID,
                    self.config.TELEGRAM_API_HASH,
                )
                await self._client.start()
                print(f"[TG] Logged in as: {(await self._client.get_me()).username}")

                if resolved is None:
                    resolved = await self._resolve_channels(all_channels)
                    if not resolved:
                        print("[TG] No valid channels — stopping")
                        return

                @self._client.on(events.NewMessage(chats=resolved))
                async def _on_message(event):
                    await self._process(event)

                backoff = 5
                await self._client.run_until_disconnected()
            except Exception as e:
                print(f"[TG] Disconnected ({type(e).__name__}: {e}). Reconnecting in {backoff}s...")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 300)

    async def _resolve_channels(self, all_channels: dict[str, list]) -> list:
        dialog_map: dict[str, object] = {}
        async for dialog in self._client.iter_dialogs():
            uname = getattr(dialog.entity, "username", None)
            if uname:
                dialog_map[uname.lower()] = dialog.entity

        resolved = []
        category_by_entity_id: dict[int, str] = {}

        for category, channels in all_channels.items():
            if not channels:
                continue
            print(f"[TG] Resolving {category} channels: {channels}")
            for ch in channels:
                ch_lower = ch.lower().lstrip("@")
                if ch_lower in dialog_map:
                    entity = dialog_map[ch_lower]
                    resolved.append(entity)
                    category_by_entity_id[entity.id] = category
                    print(f"[TG]   ✓ {category}: @{ch} (from dialogs)")
                    continue
                try:
                    entity = await self._client.get_entity(ch)
                    resolved.append(entity)
                    category_by_entity_id[entity.id] = category
                    print(f"[TG]   ✓ {category}: @{ch}")
                except Exception as e:
                    print(f"[TG]   ✗ {category}: @{ch} - {e}")

        self._category_map = category_by_entity_id
        print(f"[TG] Monitoring {len(resolved)} channel(s) across {len(all_channels)} categories")
        return resolved

    async def _process(self, event) -> None:
        text = event.message.message
        if not text or len(text) < 10:
            return

        chat = await event.get_chat()
        source = getattr(chat, "username", None) or getattr(chat, "title", "TG")
        pub_ts = event.message.date.timestamp()
        pub_str = time.strftime("%m-%d %H:%M UTC", time.gmtime(pub_ts))
        category = self._category_map.get(chat.id, "UNKNOWN")

        age_seconds = time.time() - pub_ts
        if age_seconds / 86400 > self.config.MESSAGE_AGE_DAYS:
            print(f"[TG]    [Skipping {age_seconds / 86400:.1f}d old message]")
            return

        print(f"\n[TG] [{category}] @{source} ({pub_str}): {text[:80]}")

        signal = parse_signal(text)
        if not signal:
            print("[TG]    [No signal parsed]")
            return

        print(f"[TG]    [Signal]: {json.dumps(signal)}")
        await self._send_signal(source=source, timestamp=pub_str, category=category, signal=signal)

    @staticmethod
    def _entry_price(entry) -> float | None:
        if isinstance(entry, (int, float)):
            return float(entry)
        if isinstance(entry, str):
            parts = entry.split("-")
            try:
                return (float(parts[0]) + float(parts[-1])) / 2
            except (ValueError, IndexError):
                pass
        return None

    async def _call_webhook(self, signal: dict) -> str:
        cfg = self.config
        if not all([cfg.WEBHOOK_URL, cfg.WEBHOOK_SECRET, cfg.WEBHOOK_EXCHANGE, cfg.WEBHOOK_USDT_AMOUNT]):
            return ""

        price = self._entry_price(signal["entry"])
        if price is None:
            print("[WH] Cannot compute amount: no usable entry price")
            return "❌ Order failed"

        symbol = signal["symbol"].replace("_", "/")
        amount = round(cfg.WEBHOOK_USDT_AMOUNT / price, 6)
        payload: dict = {
            "secret":      cfg.WEBHOOK_SECRET,
            "exchange":    cfg.WEBHOOK_EXCHANGE,
            "symbol":      symbol,
            "side":        signal["direction"].lower(),
            "amount":      amount,
            "market_type": cfg.WEBHOOK_MARKET_TYPE,
        }
        if isinstance(signal["entry"], float):
            payload["price"] = signal["entry"]

        import aiohttp
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    cfg.WEBHOOK_URL, json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    data = await resp.json()
                    if data.get("ok"):
                        print(f"[WH] Order placed: {symbol} {payload['side']}")
                        return "🔗 Order sent"
                    print(f"[WH] Order rejected: {data}")
                    return "❌ Order failed"
        except Exception as e:
            print(f"[WH] Webhook error: {e}")
            return "❌ Order failed"

    async def _send_signal(
        self, source: str, timestamp: str, category: str, signal: dict
    ) -> None:
        if not self.config.TELEGRAM_BOT_TOKEN or not self.config.TELEGRAM_CHAT_ID:
            print("[TG] No bot token/chat_id configured — skipping alert")
            return

        from telegram import Bot

        direction = signal["direction"]
        emoji = "🟢" if direction == "BUY" else "🔴"
        tps = " | ".join(str(p) for p in signal.get("take_profits", []))

        exchange_str = f" ({signal['exchange']})" if signal.get("exchange") else ""
        lines = [
            f"{emoji} <b>{direction}</b> {signal['symbol']}{exchange_str} [{category}]",
            "━━━━━━━━━━━━━━━━━━━━",
            f"📢 {source} | {timestamp}",
            f"📥 Entry: {signal['entry']}",
        ]
        if tps:
            lines.append(f"🎯 TP: {tps}")
        if signal.get("stop_loss"):
            lines.append(f"🛑 SL: {signal['stop_loss']}")
        if signal.get("leverage"):
            lines.append(f"⚡ Leverage: {signal['leverage']}")
        if signal.get("amount"):
            lines.append(f"💰 Amount: {signal['amount']}")

        webhook_status = await self._call_webhook(signal)
        if webhook_status:
            lines.append(webhook_status)

        alert_text = "\n".join(lines)
        bot = Bot(token=self.config.TELEGRAM_BOT_TOKEN)
        for chat_id in self.config.TELEGRAM_CHAT_ID:
            try:
                await bot.send_message(chat_id=chat_id, text=alert_text, parse_mode="HTML")
                print(f"[TG]    Alert sent to {chat_id}")
            except Exception as e:
                print(f"[TG]    Failed to send alert: {e}")


if __name__ == "__main__":
    asyncio.run(SignalListener(Config()).run())
