"""
Signal Listener — Configuration
Loads settings from environment variables with type validation.
"""

import os
from dataclasses import dataclass, field
from typing import Any


def _parse_list(env_key: str) -> list[str]:
    return [
        c.strip().lstrip("@") for c in os.getenv(env_key, "").split(",") if c.strip()
    ]


@dataclass
class Config:
    TELEGRAM_API_ID: int = field(
        default_factory=lambda: int(os.getenv("TELEGRAM_API_ID", "0"))
    )
    TELEGRAM_API_HASH: str = field(
        default_factory=lambda: os.getenv("TELEGRAM_API_HASH", "")
    )

    TELEGRAM_CHANNELS_CRYPTO: list = field(
        default_factory=lambda: _parse_list("TELEGRAM_CHANNELS_CRYPTO")
    )
    TELEGRAM_CHANNELS_FOREX: list = field(
        default_factory=lambda: _parse_list("TELEGRAM_CHANNELS_FOREX")
    )
    TELEGRAM_CHANNELS_INDICATORS: list = field(
        default_factory=lambda: _parse_list("TELEGRAM_CHANNELS_INDICATORS")
    )

    TELEGRAM_BOT_TOKEN: str = field(
        default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", "")
    )
    TELEGRAM_CHAT_ID: list = field(
        default_factory=lambda: _parse_list("TELEGRAM_CHAT_ID")
    )

    LLM_BASE_URL: str = field(
        default_factory=lambda: os.getenv("LLM_BASE_URL", "http://localhost:8000/v1")
    )
    LLM_MODEL_NAME: str = field(
        default_factory=lambda: os.getenv("LLM_MODEL_NAME", "gemma-2-2b-it")
    )

    SIGNAL_THRESHOLD: int = field(
        default_factory=lambda: int(os.getenv("SIGNAL_THRESHOLD", "7"))
    )
    MESSAGE_AGE_DAYS: int = field(
        default_factory=lambda: int(os.getenv("MESSAGE_AGE_DAYS", "7"))
    )

    WEBHOOK_PORT: int = field(
        default_factory=lambda: int(os.getenv("WEBHOOK_PORT", "8080"))
    )

    WEBHOOK_URL: str = field(
        default_factory=lambda: os.getenv("WEBHOOK_URL", "")
    )
    WEBHOOK_SECRET: str = field(
        default_factory=lambda: os.getenv("WEBHOOK_SECRET", "")
    )
    WEBHOOK_EXCHANGE: str = field(
        default_factory=lambda: os.getenv("WEBHOOK_EXCHANGE", "")
    )
    WEBHOOK_AMOUNT: float = field(
        default_factory=lambda: float(os.getenv("WEBHOOK_AMOUNT", "0"))
    )
    WEBHOOK_MARKET_TYPE: str = field(
        default_factory=lambda: os.getenv("WEBHOOK_MARKET_TYPE", "spot")
    )

    def get_all_channels(self) -> dict[str, list]:
        return {
            "CRYPTO": self.TELEGRAM_CHANNELS_CRYPTO,
            "FOREX": self.TELEGRAM_CHANNELS_FOREX,
            "INDICATORS": self.TELEGRAM_CHANNELS_INDICATORS,
        }
