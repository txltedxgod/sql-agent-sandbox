"""Read-only SQLite sandbox and rule-synthesized Text-to-SQL query engine."""

from __future__ import annotations

import re
import sqlite3
from typing import Any

_COMMENT_LINE_RE = re.compile(r"--[^\n]*")
_COMMENT_BLOCK_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_STRING_LIT_RE = re.compile(r"'(?:''|[^'])*'")
_ALLOWED_START_RE = re.compile(r"^\s*(SELECT|WITH|EXPLAIN)\b", re.IGNORECASE)
_FORBIDDEN_KW_RE = re.compile(
    r"\b(DROP|DELETE|UPDATE|INSERT|ALTER|CREATE|REPLACE|ATTACH|DETACH|PRAGMA|VACUUM|REINDEX)\b",
    re.IGNORECASE,
)

_ALLOWED_SQLITE_ACTIONS = frozenset(
    {
        sqlite3.SQLITE_SELECT,
        sqlite3.SQLITE_READ,
        sqlite3.SQLITE_FUNCTION,
    }
)


def _sqlite_read_only_authorizer(
    action: int,
    arg1: str | None,
    arg2: str | None,
    db_name: str | None,
    trigger_name: str | None,
) -> int:
    if action in _ALLOWED_SQLITE_ACTIONS:
        return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


class SQLAgent:
    """Text-to-SQL synthesizer with SQLite C-level read-only authorizer sandbox."""

    def __init__(self) -> None:
        self.conn = sqlite3.connect(":memory:", check_same_thread=False)
        self._init_mock_schema()
        self.conn.set_authorizer(_sqlite_read_only_authorizer)

    def _init_mock_schema(self) -> None:
        cur = self.conn.cursor()
        cur.execute(
            "CREATE TABLE orders (id INT PRIMARY KEY, customer TEXT, amount REAL, status TEXT)"
        )
        cur.executemany(
            "INSERT INTO orders (id, customer, amount, status) VALUES (?, ?, ?, ?)",
            [
                (1, "Acme Corp", 1500.0, "completed"),
                (2, "Globex", 2400.0, "completed"),
                (3, "Initech", 850.0, "pending"),
                (4, "Umbrella", 420.0, "refunded"),
            ],
        )
        self.conn.commit()

    def natural_language_to_sql(self, prompt: str) -> str:
        """Compile a natural language question into a bounded read-only SQL query."""
        q = (prompt or "").strip().lower()
        if not q:
            raise ValueError("Question must not be empty.")

        if "average" in q or "avg" in q:
            return "SELECT ROUND(AVG(amount), 2) AS avg_order_amount FROM orders"
        if "count" in q or "how many" in q:
            return (
                "SELECT status, COUNT(*) AS order_count FROM orders "
                "GROUP BY status ORDER BY order_count DESC"
            )
        if "pending" in q:
            return (
                "SELECT id, customer, amount FROM orders "
                "WHERE status = 'pending' ORDER BY amount DESC"
            )
        if "total sales" in q or "sum" in q or "revenue" in q:
            return "SELECT SUM(amount) AS total_sales FROM orders WHERE status = 'completed'"
        return "SELECT customer, amount, status FROM orders ORDER BY amount DESC LIMIT 20"

    @staticmethod
    def _validate_read_only_sql(query: str) -> str:
        raw = (query or "").strip()
        if not raw:
            raise ValueError("SQL query must not be empty.")

        stripped = _COMMENT_BLOCK_RE.sub(" ", _COMMENT_LINE_RE.sub(" ", raw)).strip()
        # Allow a single optional trailing semicolon, reject stacked statements
        core = stripped[:-1].strip() if stripped.endswith(";") else stripped
        masked = _STRING_LIT_RE.sub("''", core)

        if ";" in masked:
            raise PermissionError("Multiple SQL statements are prohibited in the sandbox.")
        if not _ALLOWED_START_RE.match(masked):
            raise PermissionError(
                "Only single SELECT, WITH, or EXPLAIN read-only queries are allowed."
            )
        forbidden = _FORBIDDEN_KW_RE.search(masked)
        if forbidden:
            raise PermissionError(
                f"Write or administrative SQL keyword '{forbidden.group(1).upper()}' is blocked."
            )
        return core

    def execute_query(self, query: str) -> dict[str, Any]:
        """Execute a validated read-only SQL query under the SQLite authorizer."""
        try:
            safe_sql = self._validate_read_only_sql(query)
        except (ValueError, PermissionError) as exc:
            return {"error": str(exc)}

        cur = self.conn.cursor()
        try:
            cur.execute(safe_sql)
            cols = [d[0] for d in cur.description] if cur.description else []
            rows = cur.fetchall()
            return {"columns": cols, "rows": rows, "row_count": len(rows)}
        except sqlite3.DatabaseError as exc:
            return {"error": f"Sandbox blocked or failed query: {exc}"}
