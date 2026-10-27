"""Natural-language question -> SQL -> answer, using LLM tool calling.

Loop:
  1. Send the question and the run_sql tool definition to the model.
  2. The model calls run_sql with a query; we execute it and send back rows or the error.
  3. Repeat (the model can fix a failed query) until it writes a final answer, max MAX_STEPS calls.

Providers (set LLM_PROVIDER):
  anthropic  - Claude, needs ANTHROPIC_API_KEY
  openai     - any OpenAI-compatible API (OpenAI, DeepSeek, ...), needs OPENAI_API_KEY,
               optional OPENAI_BASE_URL (e.g. https://api.deepseek.com) and LLM_MODEL
"""
import json
import os

from .db import run_sql
from .prompts import PROMPTS, TOOL_DESCRIPTION

MAX_STEPS = 4
PROVIDER = os.getenv("LLM_PROVIDER", "anthropic")
DEFAULT_MODELS = {"anthropic": "claude-haiku-5-5", "openai": "gpt-4o-mini"}
MODEL = os.getenv("LLM_MODEL", DEFAULT_MODELS.get(PROVIDER, ""))

SQL_PARAM = {
    "type": "object",
    "properties": {"sql": {"type": "string", "description": "A single DuckDB SELECT query."}},
    "required": ["sql"],
}


def _tool_result(sql):
    cols, rows, err = run_sql(sql)
    if err:
        return {"error": err}, None
    data = [dict(zip(cols, [str(v) for v in r])) for r in rows]
    return {"columns": cols, "rows": data, "row_count": len(rows)}, (cols, rows)


def ask(question: str, prompt_version: str = "v2"):
    """Return dict(answer, sql, columns, rows, steps, error)."""
    system = PROMPTS[prompt_version]
    if PROVIDER == "anthropic":
        return _ask_anthropic(question, system)
    return _ask_openai(question, system)


def _ask_anthropic(question, system):
    import anthropic

    client = anthropic.Anthropic()
    tools = [{"name": "run_sql", "description": TOOL_DESCRIPTION, "input_schema": SQL_PARAM}]
    messages = [{"role": "user", "content": question}]
    out = {"answer": "", "sql": None, "columns": [], "rows": [], "steps": 0, "error": None, "all_rows": []}
    for _ in range(MAX_STEPS + 1):
        resp = client.messages.create(model=MODEL, max_tokens=1024, system=system,
                                      tools=tools, messages=messages)
        messages.append({"role": "assistant", "content": resp.content})
        calls = [b for b in resp.content if b.type == "tool_use"]
        if not calls:
            out["answer"] = "".join(b.text for b in resp.content if b.type == "text")
            return out
        results = []
        for c in calls:
            out["steps"] += 1
            out["sql"] = c.input.get("sql", "")
            payload, table = _tool_result(out["sql"])
            out["error"] = payload.get("error")
            if table:
                out["columns"], out["rows"] = table
                out["all_rows"].extend(table[1])
            results.append({"type": "tool_result", "tool_use_id": c.id,
                            "content": json.dumps(payload, ensure_ascii=False)[:8000]})
        messages.append({"role": "user", "content": results})
    out["answer"] = "Stopped after too many attempts."
    return out


def _ask_openai(question, system):
    from openai import OpenAI

    client = OpenAI(base_url=os.getenv("OPENAI_BASE_URL") or None)
    tools = [{"type": "function", "function": {"name": "run_sql", "description": TOOL_DESCRIPTION,
                                                "parameters": SQL_PARAM}}]
    messages = [{"role": "system", "content": system}, {"role": "user", "content": question}]
    out = {"answer": "", "sql": None, "columns": [], "rows": [], "steps": 0, "error": None, "all_rows": []}
    for _ in range(MAX_STEPS + 1):
        resp = client.chat.completions.create(model=MODEL, messages=messages, tools=tools, temperature=0)
        msg = resp.choices[0].message
        messages.append(msg)
        if not msg.tool_calls:
            out["answer"] = msg.content or ""
            return out
        for c in msg.tool_calls:
            out["steps"] += 1
            out["sql"] = json.loads(c.function.arguments).get("sql", "")
            payload, table = _tool_result(out["sql"])
            out["error"] = payload.get("error")
            if table:
                out["columns"], out["rows"] = table
                out["all_rows"].extend(table[1])
            messages.append({"role": "tool", "tool_call_id": c.id,
                             "content": json.dumps(payload, ensure_ascii=False)[:8000]})
    out["answer"] = "Stopped after too many attempts."
    return out
