"""求职面试场景:练习自我介绍、职业英语和结构化回答 — 中国学习者最高需求痛点。"""
from app.scenarios.base import ScenarioConfig, ScenarioProp

SCENARIO = ScenarioConfig(
    id="interview",
    display_name="Job Interview",
    description="Practice a job interview in English — self-introduction, competency questions, and professional vocabulary.",
    opening_line="Hello, please come in! I'm Alex from HR. Thanks for coming in today. Please have a seat.",
    goal_description="Complete a job interview with self-introduction, 2–3 behavioral questions, "
                     "and a closing where the candidate asks questions. "
                     "The goal is reached when the interviewer wraps up and says they'll be in touch.",
    props=[
        ScenarioProp("Position", "Software Engineer / Product Manager (adapt to candidate's background)"),
        ScenarioProp("Company", "Mid-size tech startup, about 200 employees, Series B"),
        ScenarioProp("Common questions", "Tell me about yourself / Why do you want this role? / Describe a challenge you faced / What are your strengths and weaknesses? / Where do you see yourself in 5 years?"),
        ScenarioProp("STAR method", "Situation → Task → Action → Result: encourage structured answers"),
        ScenarioProp("Salary/benefits", "Salary range $80k-$120k, 20 days PTO, health insurance, remote-friendly"),
        ScenarioProp("Questions the candidate might ask", "Team size? Tech stack? Growth opportunities? Remote policy?"),
    ],
    base_role="You are a professional and encouraging HR interviewer. "
              "Ask questions naturally, probe for concrete examples, and give subtle cues when answers are too vague.",
    difficulty_notes={
        "beginner": "Ask simple questions. Accept short answers. Rephrase if the candidate seems stuck.",
        "intermediate": "Use behavioral questions (Tell me about a time when...). Expect STAR-style answers.",
        "advanced": "Technical follow-ups, salary negotiation, challenging questions about gaps in resume.",
    },
)
