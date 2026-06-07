"""Deterministic per-session menu and task-card sampling."""
from __future__ import annotations

import json
import random
from functools import lru_cache
from pathlib import Path

from app.models import SessionMenuItem, TaskCard

DIFFICULTY_MENU_COUNTS = {
    "beginner": {"appetizer": 2, "main": 3, "dessert": 1, "beverage": 2},
    "intermediate": {"appetizer": 3, "main": 5, "dessert": 2, "beverage": 2},
    "advanced": {"appetizer": 4, "main": 7, "dessert": 2, "beverage": 3},
}

SCENARIO_TASKS = {
    "ordering": {
        "core": [
            "Ask about a dish on the menu",
            "Order a food item",
            "Order a drink",
            "Confirm the complete order",
            "Handle a dietary restriction or make a substitution",
        ],
        "variant": [
            "Ask the server for a recommendation",
            "Choose an appetizer or dessert",
            "Order a beverage",
            "Confirm quantities and the final order",
            "Ask about ingredients and adjust one item",
        ],
    },
    "hotel": {
        "core": [
            "Confirm the reservation using your name",
            "Ask for the room location",
            "Ask whether breakfast is included",
            "Get the WiFi details",
            "Resolve a room preference or booking issue",
        ],
        "variant": [
            "State your booking details",
            "Confirm check-in and check-out times",
            "Ask about one hotel facility",
            "Request a useful local service",
            "Negotiate a room change or late checkout",
        ],
    },
    "doctor": {
        "core": [
            "Describe your main symptom",
            "Say how long it has lasted",
            "Answer a follow-up question",
            "Confirm allergies or current medicine",
            "Repeat the diagnosis and treatment plan",
        ],
        "variant": [
            "Explain why you made the appointment",
            "Describe the severity and timing",
            "Mention another relevant symptom",
            "Ask about side effects",
            "Clarify when to seek further care",
        ],
    },
    "shopping": {
        "core": [
            "Describe the item you want",
            "Ask whether your size is available",
            "Ask about the price or discount",
            "Check the return policy",
            "Compare options and make a final decision",
        ],
        "variant": [
            "Ask for a specific color or style",
            "Request to try the item on",
            "Ask whether another option is available",
            "Confirm payment or returns",
            "Explain a constraint and choose the best option",
        ],
    },
    "interview": {
        "core": [
            "Give a concise self-introduction",
            "Describe one relevant strength",
            "Answer a behavioral question",
            "Explain a career detail",
            "Ask two specific questions about the role",
        ],
        "variant": [
            "Summarize your relevant experience",
            "Explain why you want the role",
            "Give a concrete example of teamwork",
            "Discuss a weakness or setback",
            "Clarify role expectations and next steps",
        ],
    },
    "directions": {
        "core": [
            "Politely ask for directions",
            "Confirm the first turn",
            "Ask for clarification",
            "Confirm the travel time",
            "Repeat the full route and mention a landmark",
        ],
        "variant": [
            "Name your destination",
            "Ask which street to take",
            "Check one landmark",
            "Ask about distance",
            "Compare walking with another transport option",
        ],
    },
    "phone": {
        "core": [
            "State your name and reason for calling",
            "Ask for an available appointment",
            "Provide requested personal details",
            "Confirm the selected time",
            "Resolve a scheduling conflict and repeat all details",
        ],
        "variant": [
            "Explain the service you need",
            "Ask about two possible time slots",
            "Spell or repeat important information",
            "Confirm the location or preparation",
            "Change one detail before final confirmation",
        ],
    },
    "volleyball": {
        "core": [
            "Introduce yourself to the team",
            "Ask which position you should play",
            "Confirm one court instruction",
            "Coordinate a play with a teammate",
            "Discuss tactics and resolve a misunderstanding",
        ],
        "variant": [
            "Ask to join the practice",
            "Describe your playing experience",
            "Clarify the rotation",
            "Call for the ball during a play",
            "Suggest an adjustment for the next point",
        ],
    },
}

TASK_COUNTS = {"beginner": 3, "intermediate": 4, "advanced": 5}
MENU_PATH = Path(__file__).resolve().parents[1] / "data" / "menus.json"


@lru_cache(maxsize=1)
def _restaurants() -> dict[str, dict[str, list[SessionMenuItem]]]:
    payload = json.loads(MENU_PATH.read_text(encoding="utf-8"))
    grouped: dict[str, dict[str, list[SessionMenuItem]]] = {}
    for raw in payload["items"]:
        item = SessionMenuItem.model_validate(raw)
        grouped.setdefault(item.restaurant, {}).setdefault(item.course, []).append(item)
    return {
        name: courses
        for name, courses in grouped.items()
        if all(
            len(courses.get(course, [])) >= count
            for course, count in DIFFICULTY_MENU_COUNTS["advanced"].items()
        )
    }


def sample_menu(difficulty: str, seed: str) -> tuple[str, list[SessionMenuItem]]:
    counts = DIFFICULTY_MENU_COUNTS.get(
        difficulty, DIFFICULTY_MENU_COUNTS["beginner"])
    rng = random.Random(f"menu:{seed}:{difficulty}")
    restaurants = _restaurants()
    name = rng.choice(sorted(restaurants))
    sampled: list[SessionMenuItem] = []
    for course, count in counts.items():
        sampled.extend(rng.sample(restaurants[name][course], count))
    rng.shuffle(sampled)
    return name, sampled


def task_card_pool(scenario: str, difficulty: str) -> list[TaskCard]:
    profile = SCENARIO_TASKS[scenario]
    count = TASK_COUNTS.get(difficulty, TASK_COUNTS["beginner"])
    cards = []
    for index, key in enumerate(("core", "variant"), start=1):
        tasks = profile[key][:count]
        cards.append(TaskCard(
            id=f"{scenario}-{difficulty}-{index}",
            title=f"{difficulty.title()} mission",
            tasks=tasks,
            goal="Complete every task in this mission: " + "; ".join(tasks),
        ))
    return cards


def sample_task_card(scenario: str, difficulty: str, seed: str) -> TaskCard:
    pool = task_card_pool(scenario, difficulty)
    return random.Random(f"task:{seed}:{scenario}:{difficulty}").choice(pool)
