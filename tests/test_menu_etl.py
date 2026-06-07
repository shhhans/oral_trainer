from scripts.build_menu_dataset import (
    build_catalog,
    classify_course,
    clean_rows,
    normalize_price,
)


def row(restaurant, section, item, price="$10", description=""):
    return {
        "Restaurant": restaurant,
        "Section": section,
        "Item": item,
        "Description": description,
        "Price": price,
    }


def test_course_classification_covers_required_groups():
    assert classify_course("Starters", "Garlic Bread") == "appetizer"
    assert classify_course("Entrees", "Grilled Chicken") == "main"
    assert classify_course("Desserts", "Chocolate Cake") == "dessert"
    assert classify_course("Beverages", "Iced Tea") == "beverage"


def test_clean_rows_normalizes_and_deduplicates():
    source = [
        row("sample cafe", "entrees", "house burger", "$12.5", " beef  patty "),
        row("sample cafe", "entrees", "house burger", "$12.50", "beef patty"),
        row("sample cafe", "cocktails must be 0 to purchase", "wine", "$9"),
        row("sample cafe", "entrees", "", "$10"),
    ]

    assert clean_rows(source) == [{
        "restaurant": "Sample Cafe",
        "section": "Entrees",
        "name": "House Burger",
        "description": "beef patty",
        "price": "$12.50",
        "course": "main",
    }]


def test_normalize_price_rejects_invalid_values():
    assert normalize_price("$8.5") == "$8.50"
    assert normalize_price("$0") is None
    assert normalize_price("market price") is None


def test_catalog_requires_all_courses_and_is_deterministic():
    source = []
    for restaurant in ("Complete Cafe", "Incomplete Cafe"):
        source.extend([
            row(restaurant, "Appetizers", "Spring Rolls", "$6"),
            row(restaurant, "Entrees", "Chicken Plate", "$14"),
            row(restaurant, "Desserts", "Apple Pie", "$7"),
        ])
    source.append(row("Complete Cafe", "Beverages", "Lemonade", "$4"))

    first = build_catalog(source, max_restaurants=100, per_course=20)
    second = build_catalog(source, max_restaurants=100, per_course=20)

    assert first == second
    assert first["metadata"]["restaurants"] == 1
    assert {item["restaurant"] for item in first["items"]} == {"Complete Cafe"}
    assert {item["course"] for item in first["items"]} == {
        "appetizer", "main", "dessert", "beverage",
    }
