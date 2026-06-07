"""酒店入住场景:用户办理入住,练习预订确认、要求设施、报告问题。"""
from app.scenarios.base import ScenarioConfig, ScenarioProp

SCENARIO = ScenarioConfig(
    id="hotel",
    display_name="Hotel Check-in",
    description="Check in to a hotel, confirm your reservation, and request room preferences.",
    opening_line="Good evening! Welcome to the Grand Plaza Hotel. How can I assist you?",
    goal_description="Complete the check-in process for the guest. "
                     "The goal is reached when room keys are issued and the guest knows all essential information.",
    props=[
        ScenarioProp("Hotel", "Grand Plaza Hotel, 3-star city center"),
        ScenarioProp("Check-in info", "ID required, credit card for deposit ($100 hold), check-out is 11 AM"),
        ScenarioProp("Room types available", "Standard (queen bed, city view), Deluxe (king bed, river view, +$30/night)"),
        ScenarioProp("Amenities", "free WiFi (password on key card), breakfast buffet 7–10 AM ($15), gym open 6 AM–10 PM, laundry service"),
        ScenarioProp("Potential issues to handle", "early check-in (room ready at 2 PM, luggage storage available), late check-out ($20 fee), room upgrade requests"),
    ],
    base_role="You are a professional and courteous hotel front desk receptionist. "
              "Be efficient but warm, anticipate guest needs.",
    difficulty_notes={
        "beginner": "Use simple check-in vocabulary: reservation, room key, floor, breakfast. Speak clearly.",
        "intermediate": "Handle preferences and requests: smoking/non-smoking, high floor, connecting rooms.",
        "advanced": "Handle complaints, overbooking scenarios, explain policies with justification.",
    },
)
