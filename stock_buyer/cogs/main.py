import logging
from typing import Dict, List, Literal, Optional

from line import Cog, Context, command
from line.models import (
    ButtonsTemplate,
    CarouselColumn,
    CarouselTemplate,
    ConfirmTemplate,
    PostbackAction,
    QuickReply,
    QuickReplyItem,
)
from shioaji.constant import Status, StockOrderLot
from shioaji.order import StockOrder

from ..bot import StockBuyer
from ..models import User

ACTION_NAMES: Dict[Literal["Buy", "Sell"], str] = {
    "Buy": "買",
    "Sell": "賣",
}
ORDER_LOT_NAMES: Dict[Literal["Common", "Odd", "IntradayOdd"], str] = {
    "Common": "整股",
    "Odd": "零股",
    "IntradayOdd": "盤中零股",
}
STATUS_MESSAGES: Dict[Status, str] = {
    Status.PendingSubmit: "傳送中",
    Status.PreSubmitted: "預約單",
    Status.Submitted: "傳送成功",
    Status.Failed: "失敗",
    Status.Cancelled: "已刪除",
    Status.Filled: "完全成交",
    Status.PartFilled: "部分成交",
}
QA_QUICK_REPLY = QuickReply(
    [
        QuickReplyItem(
            action=PostbackAction(
                label="⌨️ 打開鍵盤", data="ignore", input_option="openKeyboard"
            )
        ),
        QuickReplyItem(action=PostbackAction(label="❌ 取消", data="cmd=cancel")),
    ]
)

log = logging.getLogger(__name__)


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
        order_lot: Optional[Literal["Common", "Odd", "IntradayOdd"]] = None,
        confirm: bool = False,
    ) -> None:
        user = await User.get_or_none(id=ctx.user_id)
        if user is None:
            return await ctx.reply_text("請先設定永豐金證卷帳戶")

        if order_lot is None:
            user.temp_data = f"cmd=place_order&stock_id={stock_id}&quantity={quantity}&price={price}&action={action}&order_lot={{text}}"
            await user.save()
            return await ctx.reply_template(
                "請選擇要交易類型",
                template=ButtonsTemplate(
                    text="請選擇交易類型",
                    actions=[
                        PostbackAction(
                            label=v,
                            data=f"cmd=place_order&stock_id={stock_id}&quantity={quantity}&price={price}&action={action}&order_lot={k}",
                        )
                        for k, v in ORDER_LOT_NAMES.items()
                    ],
                ),
            )
        if stock_id is None:
            user.temp_data = f"cmd=place_order&stock_id={{text}}&quantity={quantity}&price={price}&action={action}&order_lot={order_lot}"
            await user.save()
            return await ctx.reply_text("請輸入要下單的股票代號", quick_reply=QA_QUICK_REPLY)
        if price is None:
            user.temp_data = f"cmd=place_order&stock_id={stock_id}&quantity={quantity}&price={{text}}&action={action}&order_lot={order_lot}"
            await user.save()
            async with user.shioaji as sj:
                contract = await sj.get_contract(stock_id)
                if contract is None:
                    return await ctx.reply_text(f"找不到代號為 {stock_id} 的股票")
            return await ctx.reply_text(
                f"請輸入要下單的價格\n\n參考價: NTD${contract.reference}\n漲停價: NTD${contract.limit_up}\n跌停價: NTD${contract.limit_down}",
                quick_reply=QA_QUICK_REPLY,
            )
        if quantity is None:
            user.temp_data = f"cmd=place_order&stock_id={stock_id}&quantity={{text}}&price={price}&action={action}&order_lot={order_lot}"
            await user.save()
            async with user.shioaji as sj:
                balance = await sj.get_account_balance()
            return await ctx.reply_text(
                f"請輸入要下單的數量\n\n目前下單的價格: NTD${price}\n目前交易類型: {ORDER_LOT_NAMES[order_lot]}\n當前帳戶餘額: NTD${balance}\n最多可買 {round(balance//price)} 股",
                quick_reply=QA_QUICK_REPLY,
            )
        if action is None:
            user.temp_data = f"cmd=place_order&stock_id={stock_id}&quantity={quantity}&price={price}&action={{text}}&order_lot={order_lot}"
            await user.save()
            return await ctx.reply_template(
                "請選擇交易行為",
                template=ConfirmTemplate(
                    text="請選擇交易行為",
                    actions=[
                        PostbackAction(
                            label=v,
                            data=f"cmd=place_order&stock_id={stock_id}&quantity={quantity}&price={price}&action={k}&order_lot={order_lot}",
                        )
                        for k, v in ACTION_NAMES.items()
                    ],
                ),
            )

        async with user.shioaji as sj:
            contract = await sj.get_contract(stock_id)
            if contract is None:
                return await ctx.reply_text(f"找不到代號為 {stock_id} 的股票")

            order_str = (
                f"股票: [{contract.code}] {contract.name}\n"
                f"數量: {quantity}\n"
                f"價格: NTD${price}\n"
                f"交易行為: {ACTION_NAMES[action]}\n"
                f"委託類型: {ORDER_LOT_NAMES[order_lot]}"
            )
            if not confirm:
                template = ConfirmTemplate(
                    text=f"確認下單?\n\n{order_str}",
                    actions=[
                        PostbackAction(
                            label="確定",
                            data=f"cmd=place_order&stock_id={stock_id}&quantity={quantity}&price={price}&action={action}&order_lot={order_lot}&confirm=True",
                        ),
                        PostbackAction(
                            label="取消",
                            data="cmd=cancel",
                        ),
                    ],
                )
                return await ctx.reply_template("確認下單?", template=template)

            result = await sj.place_order(
                contract,
                price=price,
                quantity=quantity,
                action=action,
                order_lot=order_lot,
            )
            template = ButtonsTemplate(
                text=f"✅ 下單成功\n\n{order_str}\n委託單 ID: {result.order.id}\n委託單狀態: {STATUS_MESSAGES[result.status.status]}",
                actions=[
                    PostbackAction(
                        label="查詢委託狀態",
                        data=f"cmd=list_trades&filled_only=False",
                    ),
                ],
            )
            await ctx.reply_template("下單成功", template=template)

    @command
    async def cancel(self, ctx: Context) -> None:
        user = await User.get(id=ctx.user_id)
        user.temp_data = None
        await user.save()
        await ctx.reply_text("已取消")

    @command
    async def get_balance(self, ctx: Context) -> None:
        user = await User.get_or_none(id=ctx.user_id)
        if user is None:
            return await ctx.reply_text("請先設定永豐金證卷帳戶")

        async with user.shioaji as sj:
            balance = await sj.get_account_balance()
            await ctx.reply_text(f"帳戶餘額: NTD${balance}")

    @command
    async def list_positions(self, ctx: Context) -> None:
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
                        text=f"[{position.code}] {contract.name}\n\n數量: {position.quantity}\n平均價格: NTD${position.price}\n目前股價: NTD${position.last_price}\n損益: NTD${position.pnl}",
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

    @command
    async def update_order(
        self,
        ctx: Context,
        trade_id: str,
        update_quantity: bool,
        quantity: Optional[int] = None,
        price: Optional[float] = None,
    ) -> None:
        user = await User.get_or_none(id=ctx.user_id)
        if user is None:
            return await ctx.reply_text("請先設定永豐金證卷帳戶")

        async with user.shioaji as sj:
            trade = await sj.get_trade(trade_id)
            if trade is None:
                return await ctx.reply_text(f"找不到委託單 id 為 {trade_id} 的委託單")

            if not isinstance(trade.order, StockOrder):
                return await ctx.reply_text(
                    f"Unsupported order type: {type(trade.order)}"
                )
            if trade.order.order_lot.value in ("BlockTrade", "Fixing"):
                return await ctx.reply_text(
                    f"Unsupported order lot: {trade.order.order_lot}"
                )

            if (
                trade.order.order_lot in (StockOrderLot.IntradayOdd, StockOrderLot.Odd)
                and not update_quantity
            ):
                return await ctx.reply_text("盤中零股/零股委託單無法改價")

            if quantity is None and update_quantity:
                user.temp_data = f"cmd=update_order&trade_id={trade_id}&quantity={{text}}&update_quantity=True"
                await user.save()
                return await ctx.reply_text(
                    f"請輸入新的委託數量\n\n當前委託數量: {trade.order.quantity}",
                    quick_reply=QA_QUICK_REPLY,
                )
            if price is None and not update_quantity:
                user.temp_data = f"cmd=update_order&trade_id={trade_id}&quantity=0&price={{text}}&update_quantity=False"
                await user.save()
                return await ctx.reply_text(
                    f"請輸入新的委託價格\n\n當前委託價格: NTD${trade.order.price}",
                    quick_reply=QA_QUICK_REPLY,
                )

            if not update_quantity:
                await sj.update_order(trade, price=price)
                return await ctx.reply_text(
                    f"✅ 委託單 {trade_id} 改價成功\n\n新價格: NTD${price}"
                )

            if quantity >= trade.order.quantity:
                return await ctx.reply_text("新數量不能大於等於原委託數量 (只能減量)")
            if quantity == 0:
                await sj.cancel_order(trade)
                return await ctx.reply_text(f"✅ 委託單 {trade_id} 刪單成功")
            await sj.update_order(trade, quantity=quantity)
            await ctx.reply_text(f"✅ 委託單 {trade_id} 減量成功\n\n新數量: {quantity}")
