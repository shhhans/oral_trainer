import time
from app.models import Session, Turn, Summary, SubScores, TimingBreakdown
from app.storage import Storage


def make_storage(tmp_path):
    return Storage(db_path=str(tmp_path / "t.db"), audio_dir=str(tmp_path / "audio"))


def test_create_and_get_session(tmp_path):
    st = make_storage(tmp_path)
    s = Session(id="s1", scenario="ordering", created_at=time.time())
    st.save_session(s)
    got = st.get_session("s1")
    assert got is not None
    assert got.scenario == "ordering"
    assert got.turns == []


def test_append_and_update_turn(tmp_path):
    st = make_storage(tmp_path)
    st.save_session(Session(id="s1", scenario="ordering", created_at=time.time()))
    turn = Turn(id="t1", session_id="s1", index=0, user_transcript="hi")
    st.save_turn(turn)
    turn.assistant_text = "Hello!"
    st.save_turn(turn)  # upsert
    got = st.get_session("s1")
    assert len(got.turns) == 1
    assert got.turns[0].assistant_text == "Hello!"


def test_save_audio_returns_path(tmp_path):
    st = make_storage(tmp_path)
    path = st.save_audio("s1", "t1", b"\x00\x01", suffix=".wav")
    assert path.endswith(".wav")
    with open(path, "rb") as f:
        assert f.read() == b"\x00\x01"


def test_summary_roundtrip(tmp_path):
    st = make_storage(tmp_path)
    st.save_session(Session(id="s1", scenario="ordering", created_at=time.time()))
    summary = Summary(
        session_id="s1", overall_score=80,
        sub_scores=SubScores(pronunciation=80, fluency=80, grammar=80),
        timing_breakdown=TimingBreakdown(stt_avg=1, llm_avg=2, tts_avg=3, total_avg=6, samples=1),
    )
    st.save_summary(summary)
    assert st.get_summary("s1").overall_score == 80
