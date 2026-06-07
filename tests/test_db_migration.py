import sqlite3
import pytest
from app.storage import Storage


def _create_legacy_db(path: str) -> None:
    """Create a pre-migration schema (no difficulty column)."""
    with sqlite3.connect(path) as c:
        c.execute("""CREATE TABLE sessions(
            id TEXT PRIMARY KEY, scenario TEXT, status TEXT,
            created_at REAL, completed_at REAL)""")
        c.execute("""CREATE TABLE turns(
            session_id TEXT, idx INTEGER, data TEXT,
            PRIMARY KEY(session_id, idx))""")
        c.execute("""CREATE TABLE summaries(session_id TEXT PRIMARY KEY, data TEXT)""")
        c.execute("INSERT INTO sessions VALUES ('old1','ordering','active',1.0,NULL)")


def test_migration_adds_difficulty_column(tmp_path):
    db = str(tmp_path / "legacy.db")
    _create_legacy_db(db)

    # Opening Storage against legacy DB should apply migration without error.
    storage = Storage(db_path=db, audio_dir=str(tmp_path / "audio"))

    # Legacy session should be readable with default difficulty.
    session = storage.get_session("old1")
    assert session is not None
    assert session.difficulty == "beginner"


def test_migration_idempotent(tmp_path):
    db = str(tmp_path / "t.db")
    # Opening twice should not raise (migration is idempotent).
    Storage(db_path=db, audio_dir=str(tmp_path / "audio"))
    Storage(db_path=db, audio_dir=str(tmp_path / "audio"))


def test_new_session_persists_difficulty(tmp_path):
    from app.models import Session
    import time
    storage = Storage(db_path=str(tmp_path / "t.db"), audio_dir=str(tmp_path / "audio"))
    session = Session(id="s1", scenario="ordering", difficulty="advanced", created_at=time.time())
    storage.save_session(session)
    loaded = storage.get_session("s1")
    assert loaded.difficulty == "advanced"


def test_new_session_persists_dialect(tmp_path):
    from app.models import Session
    import time
    storage = Storage(db_path=str(tmp_path / "t.db"), audio_dir=str(tmp_path / "audio"))
    session = Session(id="s1", scenario="ordering", dialect="en-gb", created_at=time.time())
    storage.save_session(session)
    loaded = storage.get_session("s1")
    # dialect 决定 TTS 音色与发音测评口音,丢失会回落 en-us
    assert loaded.dialect == "en-gb"


def test_migration_adds_dialect_column(tmp_path):
    db = str(tmp_path / "legacy.db")
    _create_legacy_db(db)  # 旧库无 dialect 列
    storage = Storage(db_path=db, audio_dir=str(tmp_path / "audio"))
    session = storage.get_session("old1")
    assert session is not None
    assert session.dialect == "en-us"  # 迁移后旧行回落默认值,不报错
