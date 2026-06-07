"""Build the normalized menu catalog used by difficulty-based sampling.

Source dataset:
  Restaurant Menu Items by Pranali Bose
  https://www.kaggle.com/datasets/pranalibose/restaurant
  License: CC0-1.0

Usage:
  python scripts/build_menu_dataset.py path/to/"Menu Items.csv"
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import defaultdict
from html import unescape
from pathlib import Path

COURSES = ("appetizer", "main", "dessert", "beverage")
SOURCE_URL = "https://www.kaggle.com/datasets/pranalibose/restaurant"

COURSE_PATTERNS = {
    "beverage": (
        "beverage", "drink", "coffee", "tea", "juice", "smoothie", "shake",
        "soda", "cocktail", "wine", "beer", "lemonade", "water",
    ),
    "dessert": (
        "dessert", "cake", "cheesecake", "pie", "ice cream", "gelato",
        "cookie", "brownie", "pudding", "pastry", "sweet",
    ),
    "appetizer": (
        "appetizer", "starter", "small plate", "side", "salad", "soup",
        "wing", "bread", "tapas", "dip",
    ),
    "main": (
        "entree", "main", "burger", "sandwich", "pizza", "pasta", "chicken",
        "beef", "pork", "seafood", "fish", "shrimp", "rice", "noodle",
        "lo mein", "chow mein", "wrap", "taco", "burrito", "curry", "tofu",
        "vegetable", "dinner", "breakfast", "platter", "combo", "special",
        "sub", "calzone",
    ),
}


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(value or "")).strip()


def display_name(value: str) -> str:
    value = normalize_text(value)
    return value.title() if value == value.lower() else value


def normalize_price(value: str) -> str | None:
    value = normalize_text(value).replace(",", "")
    match = re.fullmatch(r"\$?(\d+(?:\.\d{1,2})?)", value)
    if not match:
        return None
    amount = float(match.group(1))
    if amount <= 0 or amount > 500:
        return None
    return f"${amount:.2f}"


def classify_course(section: str, item: str) -> str | None:
    haystack = f"{section} {item}".lower()
    for course in COURSES:
        if any(pattern in haystack for pattern in COURSE_PATTERNS[course]):
            return course
    return None


def _stable_rank(item: dict) -> str:
    key = "|".join(
        str(item[field])
        for field in ("restaurant", "course", "section", "name", "price")
    )
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def clean_rows(rows: list[dict[str, str]]) -> list[dict]:
    cleaned: list[dict] = []
    seen: set[tuple[str, ...]] = set()
    for row in rows:
        restaurant = display_name(row.get("Restaurant", ""))
        section = display_name(row.get("Section", ""))
        name = display_name(row.get("Item", ""))
        description = normalize_text(row.get("Description", ""))
        price = normalize_price(row.get("Price", ""))
        raw_text = " ".join((section, name, description)).lower()
        course = classify_course(section, name)
        if (
            not restaurant
            or not section
            or not name
            or price is None
            or course is None
            or "must be 0 to purchase" in raw_text
        ):
            continue
        key = (restaurant.lower(), section.lower(), name.lower(), description.lower(), price)
        if key in seen:
            continue
        seen.add(key)
        cleaned.append({
            "restaurant": restaurant,
            "section": section,
            "name": name,
            "description": description,
            "price": price,
            "course": course,
        })
    return cleaned


def select_catalog(
    items: list[dict],
    max_restaurants: int = 100,
    per_course: int = 20,
) -> list[dict]:
    grouped: dict[str, dict[str, list[dict]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for item in items:
        grouped[item["restaurant"]][item["course"]].append(item)

    complete = []
    for restaurant, courses in grouped.items():
        if not all(courses[course] for course in COURSES):
            continue
        coverage = min(len(courses[course]) for course in COURSES)
        total = sum(len(courses[course]) for course in COURSES)
        complete.append((-coverage, -total, restaurant))
    selected_restaurants = {
        restaurant
        for _, _, restaurant in sorted(complete)[:max_restaurants]
    }

    selected: list[dict] = []
    for restaurant in sorted(selected_restaurants):
        for course in COURSES:
            candidates = sorted(
                grouped[restaurant][course],
                key=lambda item: (_stable_rank(item), item["name"]),
            )
            selected.extend(candidates[:per_course])
    return selected


def build_catalog(
    rows: list[dict[str, str]],
    max_restaurants: int = 100,
    per_course: int = 20,
) -> dict:
    items = select_catalog(
        clean_rows(rows),
        max_restaurants=max_restaurants,
        per_course=per_course,
    )
    restaurant_count = len({item["restaurant"] for item in items})
    course_counts = {
        course: sum(item["course"] == course for item in items)
        for course in COURSES
    }
    return {
        "metadata": {
            "source": "Restaurant Menu Items",
            "source_url": SOURCE_URL,
            "license": "CC0-1.0",
            "schema_version": 1,
            "restaurants": restaurant_count,
            "items": len(items),
            "courses": course_counts,
            "selection": {
                "max_restaurants": max_restaurants,
                "max_items_per_course_per_restaurant": per_course,
            },
        },
        "items": items,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_csv", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("app/data/menus.json"),
    )
    parser.add_argument("--max-restaurants", type=int, default=100)
    parser.add_argument("--per-course", type=int, default=20)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    with args.input_csv.open(encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))
    catalog = build_catalog(
        rows,
        max_restaurants=args.max_restaurants,
        per_course=args.per_course,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    metadata = catalog["metadata"]
    print(
        f"wrote {args.output}: "
        f"{metadata['restaurants']} restaurants, {metadata['items']} items"
    )


if __name__ == "__main__":
    main()
