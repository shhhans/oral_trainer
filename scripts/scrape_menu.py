"""爬一份真实餐厅菜单 → resources/menu.json。
合规:只抓公开菜单页、低频、结果缓存本地,跑一次即可。抓取失败回退内置静态菜单。
用法:python scripts/scrape_menu.py [URL]"""
import json
import os
import sys
import requests
from bs4 import BeautifulSoup

FALLBACK_MENU = [
    {"name": "Classic Burger", "price": "$9.50", "desc": "beef patty, lettuce, tomato, cheese"},
    {"name": "Caesar Salad", "price": "$7.00", "desc": "romaine, croutons, parmesan"},
    {"name": "Margherita Pizza", "price": "$11.00", "desc": "tomato, mozzarella, basil"},
    {"name": "Latte", "price": "$4.00", "desc": "espresso with steamed milk"},
    {"name": "Cheesecake", "price": "$6.00", "desc": "New York style, berry topping"},
]

OUT_PATH = os.path.join("resources", "menu.json")


def scrape(url: str) -> list[dict]:
    """按目标站点结构解析。不同站点需调整选择器;失败抛异常由 main 回退。"""
    resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0 oral-trainer"}, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    items = []
    # 示例选择器:实现时按实际页面调整
    for card in soup.select(".menu-item"):
        name = card.select_one(".item-name")
        price = card.select_one(".item-price")
        desc = card.select_one(".item-desc")
        if name:
            items.append({"name": name.get_text(strip=True),
                          "price": price.get_text(strip=True) if price else "",
                          "desc": desc.get_text(strip=True) if desc else ""})
    if not items:
        raise ValueError("no items parsed")
    return items


def main() -> None:
    os.makedirs("resources", exist_ok=True)
    menu = FALLBACK_MENU
    if len(sys.argv) > 1:
        try:
            menu = scrape(sys.argv[1])
            print(f"scraped {len(menu)} items")
        except Exception as e:  # noqa: BLE001 — 任意抓取失败都回退,保证有可用菜单
            print(f"scrape failed ({e}); using fallback menu")
    else:
        print("no URL given; using fallback menu")
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(menu, f, ensure_ascii=False, indent=2)
    print(f"wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
