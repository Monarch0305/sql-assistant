"""FastAPI web API and browser UI for the Chinook SQL assistant."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

from agent.assistant import ask
from agent.llm import ChatProvider, create_provider


ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

app = FastAPI(
    title="SQL Assistant",
    description="Ask questions about the sample Chinook music store database.",
    version="1.0.0",
)


class QuestionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=2000)


@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    return response


@lru_cache(maxsize=1)
def get_provider() -> ChatProvider:
    """Create the configured provider once; credentials stay on the server."""
    return create_provider()


@app.get("/", include_in_schema=False)
def home() -> FileResponse:
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/assistant", include_in_schema=False)
def assistant_page() -> FileResponse:
    return FileResponse(ROOT / "static" / "assistant.html")


@app.get("/health", tags=["service"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/ask", tags=["assistant"])
def ask_question(request: QuestionRequest) -> dict[str, object]:
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Enter a question.")
    try:
        provider = get_provider()
    except RuntimeError as exc:
        # Avoid returning provider configuration details or credentials to clients.
        raise HTTPException(
            status_code=503,
            detail="The model provider is not configured. Set GROQ_API_KEY on the server.",
        ) from exc

    try:
        # Keep public requests below the more generous offline evaluation limit.
        return ask(question, provider, max_tool_calls=2)
    except Exception as exc:
        # Upstream errors can contain implementation details; keep the public
        # response simple while retaining the exception as the server cause.
        raise HTTPException(
            status_code=502,
            detail="The assistant could not complete that request. Please try again.",
        ) from exc
