import logging
import os
from pathlib import Path

from line import Bot
from linebot.v3.webhooks import MessageEvent
from stock_crawl import StockCrawl
from tortoise import Tortoise

from .models import User
from .rich_menu import RICH_MENU

log = logging.getLogger(__name__)


class StockBuyer(Bot):
    def __init__(self, *, channel_secret: str, access_token: str) -> None:
        super().__init__(channel_secret=channel_secret, access_token=access_token)
        self.crawl = StockCrawl()

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
