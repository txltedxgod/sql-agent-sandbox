"""Unit and API tests for Text-to-SQL compilation and SQLite authorizer sandboxing."""

from fastapi.testclient import TestClient

from sql_agent.agent import SQLAgent
from sql_agent.api import app


def test_sql_generation_and_exec() -> None:
    ag = SQLAgent()
    sql = ag.natural_language_to_sql("Show total sales")
    res = ag.execute_query(sql)
    assert res["rows"][0][0] == 3900.0

    count_sql = ag.natural_language_to_sql("How many orders per status?")
    count_res = ag.execute_query(count_sql)
    assert count_res["row_count"] == 3


def test_sandbox_blocks_write_admin_and_stacked_queries() -> None:
    ag = SQLAgent()
    for malicious in (
        "DROP TABLE orders",
        "ATTACH DATABASE ':memory:' AS extra",
        "PRAGMA table_info(orders)",
        "SELECT * FROM orders; DROP TABLE orders",
        "DELETE FROM orders WHERE id = 1",
    ):
        res = ag.execute_query(malicious)
        assert "error" in res

    # Literals mentioning blocked words must NOT trigger false positives
    safe = ag.execute_query("SELECT customer FROM orders WHERE status != 'updated' ORDER BY id")
    assert "error" not in safe
    assert safe["row_count"] == 4


def test_api_endpoints() -> None:
    client = TestClient(app)
    assert client.get("/health").json() == {"status": "healthy"}

    ok = client.post("/api/v1/query", json={"question": "Show pending orders"})
    assert ok.status_code == 200
    assert ok.json()["result"]["rows"][0][1] == "Initech"

    blocked = client.post("/api/v1/execute", json={"query": "PRAGMA database_list"})
    assert blocked.status_code == 403
