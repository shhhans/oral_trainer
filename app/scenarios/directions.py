"""问路场景:用户向路人问路,练习方位词和地点表达。"""
from app.scenarios.base import ScenarioConfig, ScenarioProp

SCENARIO = ScenarioConfig(
    id="directions",
    display_name="Asking for Directions",
    description="Ask a local pedestrian for directions to a nearby landmark.",
    opening_line="Excuse me, could you help me? I'm a bit lost.",
    goal_description="Help the user navigate to their destination using clear directions. "
                     "The goal is reached when the user understands the route and thanks you.",
    props=[
        ScenarioProp("Location", "Downtown area, near City Hall"),
        ScenarioProp("Nearby landmarks", "subway station (2 blocks north), coffee shop on the corner, post office across the street"),
        ScenarioProp("Destinations", "art museum (3 blocks east, then left on Main St), central park (straight ahead, 5 min walk), train station (take the No.3 bus, 2 stops)"),
    ],
    base_role="You are a friendly local pedestrian who knows the area well. "
              "Give clear, step-by-step directions using landmarks.",
    difficulty_notes={
        "beginner": "Use simple words: left, right, straight, next to, across from. Speak slowly.",
        "intermediate": "Use cardinal directions (north/south) and distances (blocks, minutes walking).",
        "advanced": "Use complex references, multiple turns, and ask clarifying questions about their starting point.",
    },
)
