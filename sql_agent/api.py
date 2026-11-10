"""FastAPI service for safe Text-to-SQL compilation and read-only SQLite execution."""

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from sql_agent.agent import SQLAgent

app = FastAPI(title="Text-to-SQL Agent Sandbox", version="1.0.0")
agent = SQLAgent()


class NLQueryReq(BaseModel):
    """Natural language query request."""

    question: str = Field(..., min_length=2, max_length=2000)


class RawSQLReq(BaseModel):
    """Direct sandboxed read-only SQL query request."""

    query: str = Field(..., min_length=6, max_length=4000)


@app.get("/health", tags=["Monitoring"])
def health() -> dict[str, str]:
    """Liveness check endpoint."""
    return {"status": "healthy"}


@app.post("/api/v1/query", tags=["Agent"])
def run_query(req: NLQueryReq) -> dict[str, Any]:
    """Synthesize SQL from natural language and execute in read-only sandbox."""
    try:
        sql = agent.natural_language_to_sql(req.question)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    result = agent.execute_query(sql)
    return {"question": req.question, "generated_sql": sql, "result": result}


@app.post("/api/v1/execute", tags=["Sandbox"])
def execute_raw_sql(req: RawSQLReq) -> dict[str, Any]:
    """Execute user-supplied SQL under the strict read-only sandbox."""
    result = agent.execute_query(req.query)
    if "error" in result:
        raise HTTPException(status_code=403, detail=result["error"])
    return result
