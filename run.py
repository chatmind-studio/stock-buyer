import asyncio
import os

from dotenv import load_dotenv

from stock_buyer.bot import StockBuyer
from stock_buyer.logging import setup_logging

load_dotenv()


async def main() -> None:
    channel_secret = os.getenv("LINE_CHANNEL_SECRET")
    access_token = os.getenv("LINE_ACCESS_TOKEN")
    if not (channel_secret and access_token):
        raise RuntimeError("LINE_CHANNEL_SECRET and LINE_ACCESS_TOKEN are required.")

    bot = StockBuyer(channel_secret=channel_secret, access_token=access_token)
    await bot.run(port=8064)


with setup_logging():
    asyncio.run(main())
