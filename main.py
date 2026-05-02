"""
Signal Listener — Main Entry Point
"""

import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

from bot.telegram_listener import SignalListener
from config import Config


async def main():
    config = Config()
    listener = SignalListener(config)
    await listener.run()


if __name__ == "__main__":
    asyncio.run(main())
