"""Tool-calling loop that connects a chat model to the read-only SQL tool."""
from __future__ import annotations

import json
from typing import Any

from agent.database import describe_schema, run_readonly_sql
from agent.llm import ChatProvider


TOOLS = [{
    "type": "function",
    "function": {
        "name": "run_sql",
        "description": "Run a read-only SQL query against the Chinook database.",
        "parameters": {
            "type": "object",
            "properties": {"sql": {"type": "string", "description": "One SELECT query."}},
            "required": ["sql"],
            "additionalProperties": False,
        },
    },
}]

SYSTEM_PROMPT = """You answer questions using the Chinook SQLite database.
Use run_sql when the answer needs database facts. Never claim to have run a query
unless a tool result was returned. The database is read-only; never promise writes.
If information is absent or a request is ambiguous, say so or ask a clarification.
For words like "best" with multiple reasonable meanings, ask which metric the
user wants; if you choose a metric, label it as an assumption. Do not infer that
refunds are zero from the absence of negative invoice totals: if the database
does not record refunds, say the requested value is unavailable.
Explain the result briefly and do not invent facts.

Database tables and columns:
{schema}"""


def ask(question: str, provider: ChatProvider, *, max_tool_calls: int = 4) -> dict[str, Any]:
    """Ask the model a question and execute its requested SQL tool calls."""
    if not question.strip():
        raise ValueError("Please enter a question.")
    if max_tool_calls < 1:
        raise ValueError("max_tool_calls must be at least 1.")
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT.format(schema=describe_schema())},
        {"role": "user", "content": question},
    ]
    queries: list[str] = []
    tool_results: list[dict[str, Any]] = []
    executed_calls = 0
    for _ in range(max_tool_calls + 1):
        message = provider.complete(messages, tools=TOOLS)
        calls = getattr(message, "tool_calls", None) or []
        content = getattr(message, "content", None)
        if not calls:
            return {"answer": content or "The model returned no text.", "queries": queries,
                    "tool_results": tool_results}

        messages.append({
            "role": "assistant", "content": content,
            "tool_calls": [call.model_dump(exclude_none=True) for call in calls],
        })
        for call in calls:
            name = call.function.name
            call_id = call.id
            sql = None
            try:
                if executed_calls >= max_tool_calls:
                    raise ValueError(f"Tool-call limit reached ({max_tool_calls}).")
                executed_calls += 1
                if name != "run_sql":
                    raise ValueError(f"Unknown tool: {name}")
                args = json.loads(call.function.arguments)
                if set(args) != {"sql"}:
                    raise ValueError("run_sql expects only a 'sql' argument.")
                sql = args["sql"]
                queries.append(sql)
                result = run_readonly_sql(sql)
                tool_results.append({"sql": sql, "result": result})
                tool_content = json.dumps(result, ensure_ascii=False)
            except Exception as exc:
                # Return a bounded error so the model can correct its query.
                tool_content = json.dumps({"error": str(exc)[:500]})
                tool_results.append({"sql": sql, "error": str(exc)[:500]})
            messages.append({"role": "tool", "tool_call_id": call_id, "content": tool_content})
    return {"answer": "I could not complete the query within the tool-call limit.",
            "queries": queries, "tool_results": tool_results}
