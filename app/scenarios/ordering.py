"""点餐场景:加载菜单 + 组装"服务员"角色 system prompt。
goal_reached 由 LLM 在用户确认下单后判定(prompt 里定义目标)。"""
import json
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class MenuItem:
    name: str
    price: str
    desc: str


# 内置默认菜单:menu.json 被 gitignore,新检出/未跑爬虫时用它兜底,保证主场景可用。
# scrape_menu.py 也复用它作为抓取失败的 fallback(单一来源,DRY)。
DEFAULT_MENU: list[MenuItem] = [
    MenuItem("Classic Burger", "$9.50", "beef patty, lettuce, tomato, cheese"),
    MenuItem("Caesar Salad", "$7.00", "romaine, croutons, parmesan"),
    MenuItem("Margherita Pizza", "$11.00", "tomato, mozzarella, basil"),
    MenuItem("Latte", "$4.00", "espresso with steamed milk"),
    MenuItem("Cheesecake", "$6.00", "New York style, berry topping"),
]


def load_menu(path: str) -> list[MenuItem]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return [MenuItem(name=i["name"], price=i.get("price", ""), desc=i.get("desc", ""))
            for i in data]


def load_menu_or_default(path: str) -> list[MenuItem]:
    """文件存在则读,否则回退内置默认菜单(避免新检出时菜单为空)。"""
    return load_menu(path) if os.path.exists(path) else list(DEFAULT_MENU)


def build_system_prompt(items: list[MenuItem]) -> str:
    menu_lines = "\n".join(f"- {i.name} ({i.price}): {i.desc}" for i in items)
    return (
        "You are a friendly restaurant waiter/server. Speak natural, simple English. "
        "Keep replies short (1-2 sentences) so the conversation flows. "
        "Help the customer order from this menu:\n"
        f"{menu_lines}\n"
        "Goal: guide the customer until they have confirmed a complete order "
        "(at least one dish, and they say they're done). "
        "When the order is confirmed and complete, set goal_reached=true and warmly close."
    )
