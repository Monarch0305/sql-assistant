"""Small, read-only SQLite query tool used by the SQL agent."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


DATABASE_PATH = Path(__file__).resolve().parents[1] / "data" / "Chinook_Sqlite.sqlite"
MAX_ROWS = 100
MAX_SQL_CHARS = 20_000
MAX_CELL_BYTES = 32_768
MAX_RESULT_BYTES = 256 * 1024
MAX_VM_STEPS = 2_000_000
BLOCKED_FUNCTIONS = {"load_extension", "readfile", "writefile", "fts3_tokenizer"}


def describe_schema() -> str:
    """Return table names and columns so the model can write informed SQL."""
    uri = f"{DATABASE_PATH.as_uri()}?mode=ro"
    con = sqlite3.connect(uri, uri=True, timeout=5)
    try:
        tables = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        lines = []
        for (table,) in tables:
            columns = con.execute(f'PRAGMA table_info("{table}")').fetchall()
            lines.append(f"{table}: " + ", ".join(column[1] for column in columns))
        return "\n".join(lines)
    finally:
        con.close()


def run_readonly_sql(sql: str, *, max_rows: int = MAX_ROWS) -> dict[str, Any]:
    """Run one bounded, read-only SQL statement and return columns and rows."""
    if not isinstance(sql, str) or not sql.strip():
        raise ValueError("SQL must be a non-empty string.")
    if len(sql) > MAX_SQL_CHARS:
        raise ValueError(f"SQL is too long; the limit is {MAX_SQL_CHARS} characters.")
    if not 1 <= max_rows <= 1000:
        raise ValueError("max_rows must be between 1 and 1000.")

    uri = f"{DATABASE_PATH.as_uri()}?mode=ro"
    con = sqlite3.connect(uri, uri=True, timeout=5)
    try:
        # SQLite's own limits reduce the size and complexity of individual queries.
        if hasattr(con, "setlimit"):
            con.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, MAX_CELL_BYTES)
            con.setlimit(sqlite3.SQLITE_LIMIT_SQL_LENGTH, MAX_SQL_CHARS)
            con.setlimit(sqlite3.SQLITE_LIMIT_COLUMN, 100)
            con.setlimit(sqlite3.SQLITE_LIMIT_COMPOUND_SELECT, 20)
        con.execute("PRAGMA query_only = ON")

        # SQLite calls this function before each operation. Only reads, SELECTs,
        # and recursive SELECT steps are accepted; every other action is denied.
        allowed = {
            sqlite3.SQLITE_SELECT,
            sqlite3.SQLITE_READ,
            sqlite3.SQLITE_FUNCTION,
            getattr(sqlite3, "SQLITE_RECURSIVE", -1),
        }

        def authorize(action: int, arg1: str | None, arg2: str | None,
                      database: str | None, source: str | None) -> int:
            del arg1, database, source
            if action == sqlite3.SQLITE_FUNCTION and (arg2 or "").lower() in BLOCKED_FUNCTIONS:
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK if action in allowed else sqlite3.SQLITE_DENY

        con.set_authorizer(authorize)
        con.set_progress_handler(lambda: 1, MAX_VM_STEPS)
        cur = con.execute(sql)
        if cur.description is None:
            raise ValueError("Only statements that return rows are allowed.")
        rows = cur.fetchmany(max_rows + 1)
        truncated = len(rows) > max_rows
        rows = rows[:max_rows]
        columns = [column[0] for column in cur.description]
        safe_rows = [[f"[BLOB: {len(value)} bytes]" if isinstance(value, bytes) else value
                      for value in row] for row in rows]

        # Bound the data sent to the model as a second limit beyond max_rows.
        payload = {"columns": columns, "rows": safe_rows, "truncated": truncated}
        while len(json_bytes(payload)) > MAX_RESULT_BYTES and safe_rows:
            safe_rows.pop()
            payload["truncated"] = True
        if len(json_bytes(payload)) > MAX_RESULT_BYTES:
            raise ValueError("The query returned a row too large to send safely.")
        return payload
    finally:
        con.close()


def json_bytes(value: dict[str, Any]) -> bytes:
    """Serialize result data consistently when enforcing the output size cap."""
    import json

    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
