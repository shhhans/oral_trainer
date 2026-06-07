from app.scenarios.registry import SCENARIOS
from app.services.session_content import (
    DIFFICULTY_MENU_COUNTS,
    SCENARIO_TASKS,
    sample_menu,
    sample_task_card,
    task_card_pool,
)


def test_menu_sampling_scales_and_covers_every_course():
    for difficulty, expected in DIFFICULTY_MENU_COUNTS.items():
        restaurant, items = sample_menu(difficulty, "session-1")
        assert restaurant
        assert len(items) == sum(expected.values())
        assert {item.course for item in items} == set(expected)
        assert {item.restaurant for item in items} == {restaurant}
        for course, count in expected.items():
            assert sum(item.course == course for item in items) == count


def test_menu_sampling_is_deterministic_for_session():
    assert sample_menu("advanced", "same-session") == sample_menu(
        "advanced", "same-session")


def test_every_scenario_and_difficulty_has_two_task_cards():
    assert set(SCENARIO_TASKS) == set(SCENARIOS)
    expected_counts = {"beginner": 3, "intermediate": 4, "advanced": 5}
    for scenario in SCENARIOS:
        for difficulty, count in expected_counts.items():
            pool = task_card_pool(scenario, difficulty)
            assert len(pool) >= 2
            assert all(len(card.tasks) == count for card in pool)


def test_task_sampling_is_deterministic_for_session():
    assert sample_task_card("ordering", "intermediate", "same-session") == (
        sample_task_card("ordering", "intermediate", "same-session")
    )
