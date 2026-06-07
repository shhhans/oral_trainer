"""排球场上沟通场景:练习运动中的英语喊话、战术沟通和团队协作用语。"""
from app.scenarios.base import ScenarioConfig, ScenarioProp

SCENARIO = ScenarioConfig(
    id="volleyball",
    display_name="Volleyball Team Communication",
    description="Communicate on the volleyball court — call for the ball, give tactical instructions, and encourage teammates.",
    opening_line="Alright team, let's warm up! I'm the setter today — talk to me out there!",
    goal_description="Complete a practice session communicating key volleyball situations in English: "
                     "calling the ball, setting a play, responding to a mistake, and rallying the team. "
                     "The goal is reached when the user has practiced all four communication types.",
    props=[
        ScenarioProp("Setting", "Recreational beach volleyball, 3v3 pickup game"),
        ScenarioProp("Court calls", "Mine! / I got it! / Yours! / Out! / In! / Let! / Rotate!"),
        ScenarioProp("Tactical terms", "set (二传), spike (扣球), serve (发球), dig (垫球), block (拦网), back row, front row"),
        ScenarioProp("Encouragement", "Nice serve! / Great dig! / Good hustle! / My bad! / Shake it off! / Next point!"),
        ScenarioProp("Play calls", "Short / Deep / Line / Cross / Tip it / Jump serve"),
    ],
    base_role="You are an experienced volleyball player and team captain. "
              "Simulate real on-court communication: shout calls, react to plays, give tips between points.",
    difficulty_notes={
        "beginner": "Teach basic calls: Mine, Yours, Out, In. React to simple serve and rally situations.",
        "intermediate": "Include tactical calls, rotation instructions, and error recovery phrases.",
        "advanced": "Full match communication: timeouts, score calls, strategy adjustments mid-game.",
    },
)
