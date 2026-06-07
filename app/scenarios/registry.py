"""场景注册表:所有可用场景的唯一来源。"""
from app.scenarios.base import ScenarioConfig
from app.scenarios.directions import SCENARIO as DIRECTIONS
from app.scenarios.shopping import SCENARIO as SHOPPING
from app.scenarios.hotel import SCENARIO as HOTEL
from app.scenarios.volleyball import SCENARIO as VOLLEYBALL
from app.scenarios.doctor import SCENARIO as DOCTOR
from app.scenarios.interview import SCENARIO as INTERVIEW
from app.scenarios.phone import SCENARIO as PHONE
from app.scenarios.ordering import load_ordering_scenario

_ordering = load_ordering_scenario()

SCENARIOS: dict[str, ScenarioConfig] = {
    s.id: s for s in [
        _ordering,
        DIRECTIONS,
        SHOPPING,
        HOTEL,
        VOLLEYBALL,
        DOCTOR,
        INTERVIEW,
        PHONE,
    ]
}
