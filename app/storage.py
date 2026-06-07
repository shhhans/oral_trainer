"""SQLite 持久化 + 本地音频文件。session/summary 各一行;turn 以 (session_id, index) 唯一,JSON 存整模型。"""
import os
import sqlite3
from app.models import Session, Turn, Summary


class Storage:
    def __init__(self, db_path: str, audio_dir: str):
        self.db_path = db_path
        self.audio_dir = audio_dir
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        os.makedirs(audio_dir, exist_ok=True)
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._conn() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS sessions(
                id TEXT PRIMARY KEY, scenario TEXT, status TEXT,
                created_at REAL, completed_at REAL)""")
            c.execute("""CREATE TABLE IF NOT EXISTS turns(
                session_id TEXT, idx INTEGER, data TEXT,
                PRIMARY KEY(session_id, idx))""")
            c.execute("""CREATE TABLE IF NOT EXISTS summaries(
                session_id TEXT PRIMARY KEY, data TEXT)""")
            self._migrate(c)

    @staticmethod
    def _migrate(c: sqlite3.Connection) -> None:
        """Apply additive schema migrations to existing databases."""
        migrations = [
            "ALTER TABLE sessions ADD COLUMN difficulty TEXT DEFAULT 'beginner'",
        ]
        for sql in migrations:
            try:
                c.execute(sql)
            except sqlite3.OperationalError:
                pass  # column already exists

    def save_session(self, s: Session) -> None:
        with self._conn() as c:
            c.execute("""INSERT INTO sessions(id, scenario, difficulty, status, created_at, completed_at)
                VALUES(?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET status=excluded.status,
                    difficulty=excluded.difficulty,
                    completed_at=excluded.completed_at""",
                (s.id, s.scenario, s.difficulty, s.status, s.created_at, s.completed_at))

    def save_turn(self, t: Turn) -> None:
        with self._conn() as c:
            c.execute("""INSERT INTO turns(session_id, idx, data) VALUES(?,?,?)
                ON CONFLICT(session_id, idx) DO UPDATE SET data=excluded.data""",
                (t.session_id, t.index, t.model_dump_json()))

    def get_session(self, session_id: str) -> Session | None:
        with self._conn() as c:
            row = c.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
            if row is None:
                return None
            turn_rows = c.execute(
                "SELECT data FROM turns WHERE session_id=? ORDER BY idx", (session_id,)
            ).fetchall()
        # difficulty uses dict() access with fallback for pre-migration rows
        keys = row.keys()
        s = Session(id=row["id"], scenario=row["scenario"],
                    difficulty=row["difficulty"] if "difficulty" in keys else "beginner",
                    status=row["status"],
                    created_at=row["created_at"], completed_at=row["completed_at"])
        s.turns = [Turn.model_validate_json(r["data"]) for r in turn_rows]
        return s

    def save_audio(self, session_id: str, turn_id: str, data: bytes, suffix: str) -> str:
        d = os.path.join(self.audio_dir, session_id)
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, f"{turn_id}{suffix}")
        with open(path, "wb") as f:
            f.write(data)
        return path

    def save_summary(self, summary: Summary) -> None:
        with self._conn() as c:
            c.execute("""INSERT INTO summaries(session_id, data) VALUES(?,?)
                ON CONFLICT(session_id) DO UPDATE SET data=excluded.data""",
                (summary.session_id, summary.model_dump_json()))

    def get_summary(self, session_id: str) -> Summary | None:
        with self._conn() as c:
            row = c.execute("SELECT data FROM summaries WHERE session_id=?",
                            (session_id,)).fetchone()
        return Summary.model_validate_json(row["data"]) if row else None
