import sqlite3
import os
from pathlib import Path

_BASE = Path(os.environ["R2SYNC_HOME"].strip()) if "R2SYNC_HOME" in os.environ else Path.home()
DB_PATH = _BASE / ".r2sync_state.db"

# Garantiza que el directorio existe antes de conectar
_BASE.mkdir(parents=True, exist_ok=True)

SYNC_PENDING = "SYNC_PENDING"
SYNCED = "SYNCED"
SYNC_FAILED = "SYNC_FAILED"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS file_states (
                id        INTEGER PRIMARY KEY,
                bucket    TEXT NOT NULL,
                path      TEXT NOT NULL,
                status    TEXT NOT NULL DEFAULT 'SYNC_PENDING',
                updated   REAL NOT NULL DEFAULT (unixepoch('now')),
                UNIQUE(bucket, path)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_bucket_path ON file_states(bucket, path)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON file_states(bucket, status)")


def upsert(bucket: str, path: str, status: str) -> None:
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO file_states(bucket, path, status, updated)
            VALUES(?, ?, ?, unixepoch('now'))
            ON CONFLICT(bucket, path) DO UPDATE SET status=excluded.status, updated=excluded.updated
        """, (bucket, path, status))


def delete(bucket: str, path: str) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM file_states WHERE bucket=? AND path=?", (bucket, path))


def delete_prefix(bucket: str, prefix: str) -> None:
    """Elimina todos los registros cuyo path empiece con prefix (para carpetas)."""
    with get_conn() as conn:
        conn.execute("DELETE FROM file_states WHERE bucket=? AND path LIKE ?", (bucket, prefix + "%"))


def get_status(bucket: str, path: str) -> str | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT status FROM file_states WHERE bucket=? AND path=?", (bucket, path)
        ).fetchone()
    return row["status"] if row else None


def get_synced_paths(bucket: str) -> set[str]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT path FROM file_states WHERE bucket=? AND status=?", (bucket, SYNCED)
        ).fetchall()
    return {r["path"] for r in rows}


def rename(bucket: str, old_path: str, new_path: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE file_states SET path=?, updated=unixepoch('now') WHERE bucket=? AND path=?",
            (new_path, bucket, old_path)
        )
