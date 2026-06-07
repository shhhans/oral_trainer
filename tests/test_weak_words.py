import base64
from fastapi.testclient import TestClient
from app.models import LlmReply, Pronunciation, WordScore, Turn, Session, Timings
from app.main import create_app, Services
from app.storage import Storage


class FakeLlm:
    def chat(self, system_prompt, history, user_text):
        return LlmReply(reply="ok", inline_correction=None, goal_reached=False)
    def correct(self, text): return []
    def summarize_comment(self, overall, weak_points): return ""


class FakeTts:
    def synthesize(self, text, voice="x"): return b"AUDIO"


class FakePron:
    def __init__(self, word_scores):
        self._scores = word_scores

    def assess(self, wav):
        if not self._scores:
            return None
        return Pronunciation(overall=80, accuracy=80, fluency=75, words=self._scores)


def make_client(tmp_path, pron):
    services = Services(llm=FakeLlm(), tts=FakeTts(), pron=pron,
                        db_path=str(tmp_path / "t.db"),
                        audio_dir=str(tmp_path / "audio"))
    return TestClient(create_app(services=services))


def test_weak_words_returns_sorted_by_score(tmp_path):
    word_scores = [
        WordScore(word="coffee", score=90),
        WordScore(word="please", score=45),
        WordScore(word="burger", score=60),
    ]
    client = make_client(tmp_path, FakePron(word_scores))
    sid = client.post("/api/session").json()["id"]

    # Manually inject a turn with pronunciation data via storage
    storage = Storage(db_path=str(tmp_path / "t.db"), audio_dir=str(tmp_path / "audio"))
    session = storage.get_session(sid)
    turn = Turn(id="t1", session_id=sid, index=0, user_transcript="I want coffee please",
                pronunciation=Pronunciation(overall=65, accuracy=65, fluency=60,
                                            words=word_scores),
                timings=Timings())
    storage.save_turn(turn)

    r = client.get(f"/api/session/{sid}/weak-words")
    assert r.status_code == 200
    result = r.json()
    assert len(result) <= 5
    assert result[0]["word"] == "please"  # lowest score (45)
    assert result[0]["avg_score"] == 45.0


def test_weak_words_aggregates_multiple_turns(tmp_path):
    client = make_client(tmp_path, FakePron([]))
    sid = client.post("/api/session").json()["id"]

    storage = Storage(db_path=str(tmp_path / "t.db"), audio_dir=str(tmp_path / "audio"))
    # Same word "coffee" appears in two turns with different scores
    for i, score in enumerate([60.0, 80.0]):
        turn = Turn(id=f"t{i}", session_id=sid, index=i,
                    user_transcript="coffee",
                    pronunciation=Pronunciation(overall=score, accuracy=score, fluency=score,
                                                words=[WordScore(word="coffee", score=score)]),
                    timings=Timings())
        storage.save_turn(turn)

    r = client.get(f"/api/session/{sid}/weak-words")
    result = r.json()
    coffee = next((w for w in result if w["word"] == "coffee"), None)
    assert coffee is not None
    assert coffee["avg_score"] == 70.0  # (60+80)/2
    assert coffee["occurrences"] == 2


def test_weak_words_empty_when_no_pronunciation(tmp_path):
    client = make_client(tmp_path, FakePron([]))
    sid = client.post("/api/session").json()["id"]
    r = client.get(f"/api/session/{sid}/weak-words")
    assert r.status_code == 200
    assert r.json() == []


def test_weak_words_404_for_unknown_session(tmp_path):
    client = make_client(tmp_path, FakePron([]))
    r = client.get("/api/session/unknown/weak-words")
    assert r.status_code == 404


def test_weak_words_n_param_limits_results(tmp_path):
    word_scores = [WordScore(word=f"w{i}", score=float(i * 10)) for i in range(10)]
    client = make_client(tmp_path, FakePron([]))
    sid = client.post("/api/session").json()["id"]

    storage = Storage(db_path=str(tmp_path / "t.db"), audio_dir=str(tmp_path / "audio"))
    turn = Turn(id="t0", session_id=sid, index=0, user_transcript="test",
                pronunciation=Pronunciation(overall=50, accuracy=50, fluency=50,
                                            words=word_scores),
                timings=Timings())
    storage.save_turn(turn)

    r3 = client.get(f"/api/session/{sid}/weak-words?n=3")
    assert len(r3.json()) == 3
    r10 = client.get(f"/api/session/{sid}/weak-words?n=10")
    assert len(r10.json()) == 10
