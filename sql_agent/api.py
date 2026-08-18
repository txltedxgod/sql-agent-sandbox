from fastapi import FastAPI
from pydantic import BaseModel
from sql_agent.agent import SQLAgent

app = FastAPI(title="Text-to-SQL Agent", version="0.1.0")
agent = SQLAgent()

class NLQueryReq(BaseModel):
    question: str

@app.post("/api/v1/query")
def run_query(req: NLQueryReq):
    sql = agent.natural_language_to_sql(req.question)
    result = agent.execute_query(sql)
    return {"question": req.question, "generated_sql": sql, "result": result}
