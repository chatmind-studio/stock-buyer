from typing import Dict, List, Literal, Optional

from line import Cog, Context, command
from line.models import (
    CarouselColumn,
    CarouselTemplate,
    ConfirmTemplate,
    PostbackAction,
)

from ..bot import StockBuyer
from ..models import User

ACTION_NAMES: Dict[Literal["Buy", "Sell"], str] = {
    "Buy": "買",
    "Sell": "賣",
}


class Main(Cog):
    def __init__(self, bot: StockBuyer) -> None:
        super().__init__(bot)
        self.bot = bot

    @command
    async def place_order(
        self,
        ctx: Context,
        stock_id: Optional[str] = None,
        quantity: Optional[int] = None,
        price: Optional[float] = None,
        action: Optional[Literal["Buy", "Sell"]] = None,
        confirm: bool = False,
    ) -> None:
        user = await User.get_or_none(id=ctx.user_id)
        if user is None:
            return await ctx.reply_text("請先設定永豐金證卷帳戶")

        if stock_id is None:
            user.temp_data = f"cmd=place_order&stock_id={{text}}&quantity={quantity}&price={price}&action={action}"
            await user.save()
            return await ctx.reply_text("請輸入要下單的股票代號")
        if quantity is None:
            user.temp_data = f"cmd=place_order&stock_id={stock_id}&quantity={{text}}&price={price}&action={action}"
            await user.save()
            return await ctx.reply_text("請輸入要下單的張數")
        if price is None:
            user.temp_data = f"cmd=place_order&stock_id={stock_id}&quantity={quantity}&price={{text}}&action={action}"
            await user.save()
            return await ctx.reply_text("請輸入要下單的價格")
        if action is None:
            user.temp_data = f"cmd=place_order&stock_id={stock_id}&quantity={quantity}&price={price}&action={{text}}"
            await user.save()
            return await ctx.reply_template(
                "請選擇要下單的交易行為",
                template=ConfirmTemplate(
                    text="請選擇要下單的交易行為",
                    actions=[
                        PostbackAction(
                            label="買",
                            data=f"cmd=place_order&stock_id={stock_id}&quantity={quantity}&price={price}&action=Buy",
                        ),
                        PostbackAction(
                            label="賣",
                            data=f"cmd=place_order&stock_id={stock_id}&quantity={quantity}&price={price}&action=Sell",
                        ),
                    ],
                ),
            )

        if not confirm:
            template = ConfirmTemplate(
                text=f"確認下單?\n\n股票代號: {stock_id}\n張數: {quantity}\n價格: NTD${price}\n交易行為: {ACTION_NAMES[action]}",
                actions=[
                    PostbackAction(
                        label="確定",
                        data=f"cmd=place_order&stock_id={stock_id}&quantity={quantity}&price={price}&action={action}&confirm=True",
                    ),
                    PostbackAction(
                        label="取消",
                        data="cmd=cancel",
                    ),
                ],
            )
            return await ctx.reply_template("確認下單?", template=template)

        async with user.shioaji as sj:
            contract = await sj.get_contract(stock_id)
            if contract is None:
                return await ctx.reply_text(f"找不到代號為 {stock_id} 的股票")
            result = await sj.place_order(
                contract, price=price, quantity=quantity, action=action
            )
            await ctx.reply_text(
                f"✅ 下單成功\n\n股票代號: {stock_id}\n張數: {quantity}\n價格: NTD${price}\n交易行為: {ACTION_NAMES[action]}\n委託單狀態: {result}"
            )

    @command
    async def cancel(self, ctx: Context) -> None:
        await ctx.reply_text("已取消")

    @command
    async def balance(self, ctx: Context) -> None:
        user = await User.get_or_none(id=ctx.user_id)
        if user is None:
            return await ctx.reply_text("請先設定永豐金證卷帳戶")

        async with user.shioaji as sj:
            balance = await sj.get_account_balance()
            await ctx.reply_text(f"帳戶餘額: NTD${balance}")

    @command
    async def stock(self, ctx: Context) -> None:
        user = await User.get_or_none(id=ctx.user_id)
        if user is None:
            return await ctx.reply_text("請先設定永豐金證卷帳戶")

        async with user.shioaji as sj:
            positions = await sj.list_positions()
            columns: List[CarouselColumn] = []
            for position in positions:
                contract = await sj.get_contract(position.code)
                if contract is None:
                    continue
                columns.append(
                    CarouselColumn(
                        text=f"[{position.code}] {contract.name}\n\n張數: {position.quantity}\n平均價格: NTD${position.price}\n目前股價: NTD${position.last_price}\n損益: NTD${position.pnl}",
                        actions=[
                            PostbackAction(
                                "買",
                                data=f"cmd=place_order&stock_id={position.code}&action=Buy",
                            ),
                            PostbackAction(
                                "賣",
                                data=f"cmd=place_order&stock_id={position.code}&action=Sell",
                            ),
                        ],
                    )
                )

        if not columns:
            return await ctx.reply_text("目前沒有庫存")
        template = CarouselTemplate(columns=columns)
        await ctx.reply_template("庫存", template=template)

    @command
    async def list_trades(self, ctx: Context, filled_only: bool) -> None:
        user = await User.get_or_none(id=ctx.user_id)
        if user is None:
            return await ctx.reply_text("請先設定永豐金證卷帳戶")

        async with user.shioaji as sj:
            trades = await sj.list_trades()
            columns: List[CarouselColumn] = []
            for trade in trades:
                if not isinstance(trade.order, StockOrder):
                    log.warning("Unsupported order type: %s", type(trade.order))
                    continue
                if trade.order.order_lot.value in ("BlockTrade", "Fixing"):
                    log.warning("Unsupported order lot: %s", trade.order.order_lot)
                    continue
                if filled_only and trade.status.status is not Status.Filled:
                    continue
                contract = await sj.get_contract(trade.contract.code)
                if contract is None:
                    raise AssertionError("Contract should not be None")

                if trade.status.status is Status.Filled:
                    actions = [
                        PostbackAction(
                            "加買",
                            data=f"cmd=place_order&stock_id={trade.contract.code}&action=Buy",
                        ),
                        PostbackAction(
                            "賣",
                            data=f"cmd=place_order&stock_id={trade.contract.code}&action=Sell",
                        ),
                    ]
                else:
                    actions = [
                        PostbackAction(
                            "減量",
                            data=f"cmd=update_order&trade_id={trade.order.id}&update_quantity=True",
                        ),
                        PostbackAction(
                            "刪單",
                            data=f"cmd=update_order&trade_id={trade.order.id}&update_quantity=True&quantity=0",
                        ),
                        PostbackAction(
                            "改價",
                            data=f"cmd=update_order&trade_id={trade.order.id}&update_quantity=False",
                        ),
                    ]

                columns.append(
                    CarouselColumn(
                        text=(
                            f"委託單 {trade.order.id}\n\n"
                            f"股票: [{trade.contract.code}] {contract.name}\n"
                            f"狀態: {STATUS_MESSAGES[trade.status.status]}\n"
                            f"數量: {trade.order.quantity if trade.status.cancel_quantity == 0 else trade.status.cancel_quantity}\n"
                            f"價格: NTD${trade.order.price if trade.status.modified_price == 0.0 else trade.status.modified_price}\n"
                            f"交易行為: {ACTION_NAMES[trade.order.action.value]}\n"
                            f"委託類型: {ORDER_LOT_NAMES[trade.order.order_lot.value]}\n"
                        ),
                        actions=actions,
                    )
                )

        if not columns:
            if filled_only:
                return await ctx.reply_text("目前沒有成交單")
            return await ctx.reply_text("目前沒有委託單")

        template = CarouselTemplate(columns=columns)
        await ctx.reply_template("委託單", template=template)
