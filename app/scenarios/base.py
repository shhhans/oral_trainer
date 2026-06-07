"""场景抽象基类。每个场景定义角色、道具、目标和开场白。"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ScenarioProp:
    name: str
    detail: str


@dataclass
class ScenarioConfig:
    id: str
    display_name: str
    description: str
    opening_line: str
    goal_description: str
    props: list[ScenarioProp]
    base_role: str
    difficulty_notes: dict[str, str] = field(default_factory=dict)

    def build_prompt(
        self,
        difficulty: str = "beginner",
        props: list[ScenarioProp] | None = None,
        goal_description: str | None = None,
    ) -> str:
        active_props = self.props if props is None else props
        props_text = "\n".join(f"- {p.name}: {p.detail}" for p in active_props)
        diff_note = self.difficulty_notes.get(difficulty, self.difficulty_notes.get("beginner", ""))
        parts = [self.base_role]
        if diff_note:
            parts.append(diff_note)
        parts.append("Speak natural, simple English. Keep replies short (1-2 sentences) so the conversation flows.")
        if props_text:
            parts.append(f"Context:\n{props_text}")
        goal = goal_description or self.goal_description
        parts.append(f"Goal: {goal} When the goal is reached, set goal_reached=true and close warmly.")
        return "\n".join(parts)
