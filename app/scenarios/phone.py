"""电话预约场景:无视觉线索纯听力沟通 — 中国学习者技术最难痛点。"""
from app.scenarios.base import ScenarioConfig, ScenarioProp

SCENARIO = ScenarioConfig(
    id="phone",
    display_name="Phone Appointment",
    description="Make an appointment over the phone — no visual cues, must rely on listening alone.",
    opening_line="Hello, City Dental Clinic, this is Sarah speaking. How can I help you?",
    goal_description="Successfully make, modify, or cancel an appointment over the phone. "
                     "The goal is reached when the appointment is confirmed with a date, time, and doctor name.",
    props=[
        ScenarioProp("Clinic", "City Dental Clinic"),
        ScenarioProp("Available slots", "Dr. Kim: Monday 10 AM, Wednesday 2 PM, Friday 9 AM; Dr. Patel: Tuesday 11 AM, Thursday 3 PM"),
        ScenarioProp("Phone conventions", "Speak slowly / Could you repeat that? / Could you spell that? / I didn't catch that / Sorry, you're breaking up"),
        ScenarioProp("Appointment types", "routine checkup (30 min), filling (45 min), cleaning (1 hour), emergency (same day, limited slots)"),
        ScenarioProp("Information needed", "Full name, date of birth, phone number, reason for visit, insurance provider"),
    ],
    base_role="You are a clinic receptionist taking calls. "
              "Speak at a natural phone pace — not too slow. Ask for information piece by piece. "
              "Simulate occasional phone-call challenges: ask for clarification, spell things back.",
    difficulty_notes={
        "beginner": "Speak slowly and clearly. Confirm each piece of information. Use simple date formats.",
        "intermediate": "Normal speaking pace. Ask for insurance info. Handle rescheduling requests.",
        "advanced": "Fast pace, background noise mentions, complex insurance questions, put caller on hold.",
    },
)
