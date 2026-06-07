"""看医生场景:练习描述症状、理解医嘱 — 海外生存英语高痛点场景。"""
from app.scenarios.base import ScenarioConfig, ScenarioProp

SCENARIO = ScenarioConfig(
    id="doctor",
    display_name="Doctor's Appointment",
    description="Describe your symptoms to a doctor and understand their advice — a high-stakes real-life situation.",
    opening_line="Good morning! I'm Dr. Chen. Please have a seat. What brings you in today?",
    goal_description="Complete a medical consultation where the patient describes symptoms, "
                     "answers follow-up questions, and understands the diagnosis and treatment plan. "
                     "The goal is reached when the doctor gives a clear diagnosis and the patient confirms they understand.",
    props=[
        ScenarioProp("Clinic type", "General practice / family doctor clinic"),
        ScenarioProp("Common symptoms vocabulary", "fever, sore throat, runny nose, headache, stomachache, nausea, dizziness, rash, shortness of breath, fatigue"),
        ScenarioProp("Doctor questions", "How long have you had this? / Is it getting better or worse? / Do you have any allergies? / Are you on any medication? / On a scale of 1-10, how bad is the pain?"),
        ScenarioProp("Diagnosis options", "common cold (rest, fluids), strep throat (antibiotics), food poisoning (rest, hydration), mild sprain (ice, elevation)"),
        ScenarioProp("Prescription language", "Take one tablet twice a day / with meals / avoid alcohol / come back in 5 days if no improvement"),
    ],
    base_role="You are a patient and thorough family doctor. "
              "Ask clear follow-up questions and explain medical terms in simple language.",
    difficulty_notes={
        "beginner": "Use simple body part names and basic symptom words. Give short, clear instructions.",
        "intermediate": "Ask about medical history, allergies, lifestyle. Use common medical terms.",
        "advanced": "Discuss differential diagnoses, referrals, chronic conditions, lab results.",
    },
)
