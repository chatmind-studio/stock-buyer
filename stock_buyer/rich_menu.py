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
            bounds=RichMenuBounds(x=23, y=18, width=364, height=364),
            action=PostbackAction(data="cmd=stock", label="庫存"),
        ),
        RichMenuArea(
            bounds=RichMenuBounds(x=418, y=18, width=364, height=364),
            action=PostbackAction(data="cmd=balance", label="帳戶餘額"),
        ),
        RichMenuArea(
            bounds=RichMenuBounds(x=813, y=18, width=364, height=364),
            action=PostbackAction(data="cmd=place_order", label="下單"),
        ),
    ],
)
