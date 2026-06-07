"""点餐场景:加载菜单 + 组装"服务员"角色 system prompt。
goal_reached 由 LLM 在用户确认下单后判定(prompt 里定义目标)。"""
import json
from dataclasses import dataclass


@dataclass(frozen=True)
class MenuItem:
    name: str
    price: str
    desc: str


def load_menu(path: str) -> list[MenuItem]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return [MenuItem(name=i["name"], price=i.get("price", ""), desc=i.get("desc", ""))
            for i in data]


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
