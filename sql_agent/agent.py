import sqlite3
from typing import Dict, Any, List

class SQLAgent:
    def __init__(self):
        self.conn = sqlite3.connect(":memory:", check_same_thread=False)
        self._init_mock_schema()

    def _init_mock_schema(self):
        cur = self.conn.cursor()
        cur.execute("CREATE TABLE orders (id INT, customer TEXT, amount REAL, status TEXT)")
        cur.execute("INSERT INTO orders VALUES (1, 'Acme Corp', 1500.0, 'completed'), (2, 'Globex', 2400.0, 'completed')")
        self.conn.commit()

    def natural_language_to_sql(self, prompt: str) -> str:
        # Prompt rule synthesis
        if "total sales" in prompt.lower() or "sum" in prompt.lower():
            return "SELECT SUM(amount) AS total_sales FROM orders WHERE status = 'completed'"
        return "SELECT customer, amount FROM orders ORDER BY amount DESC"

    def execute_query(self, query: str) -> Dict[str, Any]:
        # Disallow destructive queries
        if any(w in query.upper() for w in ["DROP", "DELETE", "UPDATE", "INSERT"]):
            return {"error": "Destructive queries are disabled in sandbox"}
        cur = self.conn.cursor()
        cur.execute(query)
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
        return {"columns": cols, "rows": rows}
