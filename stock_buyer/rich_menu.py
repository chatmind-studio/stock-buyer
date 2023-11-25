from line.models import PostbackAction
from linebot.v3.messaging import (
    RichMenuArea,
    RichMenuBounds,
    RichMenuRequest,
    RichMenuSize,
)

RICH_MENU = RichMenuRequest(
    size=RichMenuSize(width=1200, height=400),
    selected=True,
    name="rich_menu_1",
    chatBarText="打開/關閉導覽列",
    areas=[
        RichMenuArea(
            bounds=RichMenuBounds(x=26, y=18, width=457, height=170),
            action=PostbackAction(data="cmd=list_positions", label="庫存"),
        ),
        RichMenuArea(
            bounds=RichMenuBounds(x=26, y=212, width=457, height=170),
            action=PostbackAction(data="cmd=get_balance", label="帳戶餘額"),
        ),
        RichMenuArea(
            bounds=RichMenuBounds(x=505, y=18, width=457, height=364),
            action=PostbackAction(data="cmd=place_order", label="下單"),
        ),
        RichMenuArea(
            bounds=RichMenuBounds(x=984, y=18, width=190, height=170),
            action=PostbackAction(
                data="cmd=list_trades&filled_only=False", label="委託查詢"
            ),
        ),
        RichMenuArea(
            bounds=RichMenuBounds(x=984, y=212, width=190, height=170),
            action=PostbackAction(
                data="cmd=list_trades&filled_only=True", label="成交查詢"
            ),
        ),
    ],
)
