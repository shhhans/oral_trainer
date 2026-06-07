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


_DIFFICULTY_NOTES = {
    "beginner": (
        "The customer is a beginner English learner. "
        "Speak slowly and use simple vocabulary. "
        "Repeat the order back to confirm each item. "
        "If the customer seems confused, rephrase in simpler words."
    ),
    "intermediate": (
        "The customer has intermediate English. "
        "Use natural conversational pace. "
        "Ask friendly follow-up questions (size, drink, any sides?)."
    ),
    "advanced": (
        "The customer is an advanced English learner. "
        "Use natural restaurant vocabulary (specials, sides, substitutions, allergies). "
        "Speak at a brisk pace. "
        "Ask about preferences, dietary restrictions, and upsell naturally."
    ),
}


def build_system_prompt(items: list[MenuItem], difficulty: str = "beginner") -> str:
    menu_lines = "\n".join(f"- {i.name} ({i.price}): {i.desc}" for i in items)
    difficulty_note = _DIFFICULTY_NOTES.get(difficulty, _DIFFICULTY_NOTES["beginner"])
    return (
        "You are a friendly, patient restaurant waiter/server. "
        f"{difficulty_note} "
        "Speak natural, simple English. Keep replies short (1-2 sentences).\n\n"
        "## Your top priority: keep the conversation moving\n"
        "- Always respond as a real waiter would — acknowledge what the customer said "
        "and gently guide the conversation toward completing their order.\n"
        "- If the customer's meaning is clear, accept it and move on, even if the English "
        "is imperfect. Minor grammar issues do NOT interrupt the ordering flow.\n"
        "- Only set inline_correction (in your JSON) if the customer's phrasing would "
        "genuinely cause confusion in a real restaurant (e.g., completely wrong item name, "
        "contradictory request, or a phrase no native speaker would understand). "
        "Never correct minor grammar, tense, or article mistakes mid-conversation.\n"
        "- Language feedback for smaller mistakes will be given at the end of the session — "
        "your job is to complete the order naturally.\n\n"
        "## Menu\n"
        f"{menu_lines}\n\n"
        "## Goal\n"
        "Guide the customer until they confirm a complete order (at least one dish and "
        "they indicate they are done). When the order is confirmed, set goal_reached=true "
        "and close warmly (e.g., 'Great, I'll put that in for you!')."    )
