import asyncio
from typing import Dict, List, Literal, Optional, Union

import shioaji as sj
from shioaji.account import StockAccount
from shioaji.constant import Action, OrderType, Status, StockPriceType
from shioaji.contracts import Contract
from shioaji.position import FuturePosition, StockPosition

STATUS_MESSAGES: Dict[Status, str] = {
    Status.PendingSubmit: "傳送中",
    Status.PreSubmitted: "預約單",
    Status.Submitted: "傳送成功",
    Status.Failed: "失敗",
    Status.Cancelled: "已刪除",
    Status.Filled: "完全成交",
    Status.PartFilled: "部分成交",
}


class Shioaji:
    def __init__(
        self,
        *,
        api_key: str,
        secret_key: str,
        ca_path: str,
        ca_passwd: str,
        person_id: str,
    ):
        self.__api_key = api_key
        self.__secret_key = secret_key
        self.__ca_path = ca_path
        self.__ca_passwd = ca_passwd
        self.__person_id = person_id
        self.api = sj.Shioaji()
        self.stock_account: Optional[StockAccount] = None

    async def __aenter__(self) -> "Shioaji":
        await self.login()
        await self.activate_ca()
        if not isinstance(self.api.stock_account, StockAccount):
            raise RuntimeError("無法取得股票帳號")
        self.stock_account = self.api.stock_account
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.logout()

    async def login(self, **kwargs) -> None:
        await asyncio.to_thread(
            self.api.login, self.__api_key, self.__secret_key, **kwargs
        )

    async def logout(self) -> None:
        await asyncio.to_thread(self.api.logout)

    async def activate_ca(self) -> None:
        await asyncio.to_thread(
            self.api.activate_ca,
            ca_path=self.__ca_path,
            ca_passwd=self.__ca_passwd,
            person_id=self.__person_id,
        )

    async def get_account_balance(self) -> int:
        return round((await asyncio.to_thread(self.api.account_balance)).acc_balance)

    async def get_contract(self, stock_id: str) -> Optional[Contract]:
        """
        取得商品檔

        Args:
            stock_id (str): 商品檔代碼

        Returns:
            Optional[Contract]: 商品檔
        """
        return await asyncio.to_thread(self.api.Contracts.Stocks.__getitem__, stock_id)

    async def place_order(
        self,
        contract: Contract,
        price: float,
        quantity: int,
        action: Literal["Buy", "Sell"],
        order_lot: Literal["Common", "Odd", "IntradayOdd"],
    ) -> Trade:
        """
        下單

        Args:
            contract (Contract): 商品檔
            price (float): 價格
            quantity (int): 數量
            action (Literal["Buy", "Sell"]): 交易行為(買/賣)

        Returns:
            Trade: 委託單

        Raises:
            RuntimeError: 尚未登入
        """
        if self.stock_account is None:
            raise RuntimeError("尚未登入")
        order = sj.Order(
            price=price,
            quantity=quantity,
            action=Action(action),
            price_type=StockPriceType.LMT,
            order_type=OrderType.ROD,
            order_lot=StockOrderLot(order_lot),
            account=self.stock_account,
        )
        trade = await asyncio.to_thread(self.api.place_order, contract, order)
        return trade

    async def list_positions(self) -> List[Union[StockPosition, FuturePosition]]:
        """
        列出所有未實現損益

        Returns:
            List[Union[StockPosition, FuturePosition]]: 未實現損益

        Raises:
            RuntimeError: 尚未登入
        """
        if self.stock_account is None:
            raise RuntimeError("尚未登入")
        return await asyncio.to_thread(self.api.list_positions, self.stock_account)

    async def list_trades(self) -> List[Trade]:
        """
        列出所有成交紀錄

        Returns:
            List[Trade]: 成交紀錄

        Raises:
            RuntimeError: 尚未登入
        """
        if self.stock_account is None:
            raise RuntimeError("尚未登入")

        await asyncio.to_thread(self.api.update_status, self.stock_account)
        return await asyncio.to_thread(self.api.list_trades)

    async def get_trade(self, order_id: str) -> Optional[Trade]:
        """
        取得成交紀錄

        Args:
            order_id (str): 委託單編號

        Returns:
            Optional[Trade]: 成交紀錄
        """
        trades = await self.list_trades()
        for trade in trades:
            if trade.order.id == order_id:
                return trade
        return None

    async def update_order(
        self,
        trade: Trade,
        price: Optional[float] = None,
        quantity: Optional[int] = None,
    ) -> None:
        """
        更新委託單狀態

        Args:
            trade (Trade): 成交紀錄

        Raises:
            ValueError: price 和 quantity 不能同時為 None
            ValueError: price 和 quantity 不能同時有值
        """
        if price is None and quantity is None:
            raise ValueError("price 和 quantity 不能同時為 None")
        if price is None and quantity is not None:
            await asyncio.to_thread(self.api.update_order, trade, qty=quantity)
        elif price is not None and quantity is None:
            await asyncio.to_thread(self.api.update_order, trade, price=price)
        else:
            raise ValueError("price 和 quantity 不能同時有值")

    async def cancel_order(self, trade: Trade) -> None:
        """
        刪除委託單

        Args:
            trade (Trade): 成交紀錄
        """
        await asyncio.to_thread(self.api.cancel_order, trade)
