"""购物场景:用户在服装店购物,练习尺码、颜色、价格谈判表达。"""
from app.scenarios.base import ScenarioConfig, ScenarioProp

SCENARIO = ScenarioConfig(
    id="shopping",
    display_name="Clothes Shopping",
    description="Shop for clothes at a fashion store — ask about sizes, colors, and prices.",
    opening_line="Welcome! Let me know if you need any help finding something.",
    goal_description="Help the customer find an item they want to buy. "
                     "The goal is reached when the customer decides to purchase something and you complete the sale.",
    props=[
        ScenarioProp("Store type", "Mid-range fashion boutique"),
        ScenarioProp("Available items", "T-shirts ($15–$25), jeans ($45–$80), dresses ($35–$70), jackets ($60–$120)"),
        ScenarioProp("Sizes available", "XS, S, M, L, XL for most items"),
        ScenarioProp("Colors", "T-shirts: white, black, navy, grey; Jeans: blue, black, grey wash"),
        ScenarioProp("Policies", "30-day return with receipt, fitting rooms available, no alteration service"),
    ],
    base_role="You are a helpful and friendly shop assistant at a clothing store. "
              "Help customers find what they're looking for without being pushy.",
    difficulty_notes={
        "beginner": "Use simple vocabulary: big, small, color names, price. Offer clear choices.",
        "intermediate": "Use retail terms: fitting room, exchange, receipt, on sale, in stock.",
        "advanced": "Handle complaints, negotiate discounts, suggest outfit combinations.",
    },
)
