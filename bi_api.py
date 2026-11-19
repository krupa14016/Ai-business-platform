from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text

import agent_router as ai_agent
from db_connect import get_engine
from financial_api import app


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)


@app.post("/ask")
def ask_question(req: AskRequest):
    result = ai_agent.ask(req.question)
    if result["status"] == "config_error":
        raise HTTPException(status_code=503, detail=result["answer"])
    return {
        "answer": result["answer"],
        "tools_used": [{"tool": t["tool"], "input": t["input"]} for t in result["tool_calls"]],
        "model": result["model"],
        "latency_ms": result["latency_ms"],
        "status": result["status"],
    }


@app.get("/audit/recent")
def audit_recent():
    ai_agent.ensure_audit_table()
    with get_engine().connect() as conn:
        rows = conn.execute(text("""SELECT id, asked_at, question, answer, status, latency_ms
                                    FROM ai_audit_log ORDER BY id DESC LIMIT 20""")).mappings().all()
    return [{k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in r.items()}
            for r in rows]
