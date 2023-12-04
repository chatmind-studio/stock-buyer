import logging
import os
from pathlib import Path
from typing import Dict

from line import Bot
from linebot.v3.webhooks import MessageEvent
from stock_crawl import StockCrawl
from tortoise import Tortoise

from .models import User
from .rich_menu import RICH_MENU
from .shioaji import Shioaji

log = logging.getLogger(__name__)


class StockBuyer(Bot):
    def __init__(self, *, channel_secret: str, access_token: str) -> None:
        super().__init__(channel_secret=channel_secret, access_token=access_token)
        self.crawl = StockCrawl()
        self.shioaji_accounts: Dict[str, Shioaji] = {}

    async def setup_hook(self) -> None:
        log.info("Setting up database...")
        await Tortoise.init(
            db_url=os.getenv("DB_URL") or "sqlite://db.sqlite3",
            modules={"models": ["stock_buyer.models"]},
        )
        await Tortoise.generate_schemas()

        log.info("Loading cogs")
        for cog in Path("stock_buyer/cogs").glob("*.py"):
            log.info("Loading cog %s", cog.stem)
            self.add_cog(f"stock_buyer.cogs.{cog.stem}")

        log.info("Setting up rich menu")
        await self.delete_all_rich_menus()
        rich_menu_id = await self.create_rich_menu(RICH_MENU, "assets/rich_menu.png")
        await self.line_bot_api.set_default_rich_menu(rich_menu_id)

        log.info("Setting up shioaji")
        for user in await User.all():
            shioaji = user.shioaji
            await shioaji.start()
            self.shioaji_accounts[user.id] = shioaji

    async def on_message(self, event: MessageEvent) -> None:
        if event.message is None:
            return
        text: str = event.message.text  # type: ignore
        user = await User.get(id=event.source.user_id)  # type: ignore
        if user.temp_data:
            event.message.text = user.temp_data.format(text=text)  # type: ignore
            user.temp_data = None
            await user.save()

        await super().on_message(event)

    async def on_close(self) -> None:
        await Tortoise.close_connections()
        await self.crawl.close()
        for shioaji in self.shioaji_accounts.values():
            await shioaji.logout()
