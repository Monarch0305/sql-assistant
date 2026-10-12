"""Provider interface and Groq chat-completions client for the SQL agent."""
from __future__ import annotations

import os
from typing import Any, Protocol, Sequence


class ChatProvider(Protocol):
    """Minimal interface consumed by the agent loop."""

    model: str

    def complete(
        self,
        messages: Sequence[dict[str, Any]],
        tools: Sequence[dict[str, Any]] | None = None,
    ) -> Any:
        """Return the provider's assistant message for this turn."""
        ...


class GroqProvider:
    """Groq implementation; credentials and model are read from environment."""

    def __init__(self, model: str | None = None, api_key: str | None = None) -> None:
        try:
            from groq import Groq
        except ImportError as exc:
            raise RuntimeError(
                "Groq's Python package is missing. Install it with `pip install -r requirements.txt`."
            ) from exc

        key = api_key or os.getenv("GROQ_API_KEY")
        if not key:
            raise RuntimeError(
                "GROQ_API_KEY is not set. Add it to your local .env file or environment."
            )

        self.model = model or os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
        # One bounded attempt avoids hidden SDK retries multiplying usage.
        self._client = Groq(api_key=key, timeout=12.0, max_retries=0)

    def complete(
        self,
        messages: Sequence[dict[str, Any]],
        tools: Sequence[dict[str, Any]] | None = None,
    ) -> Any:
        """Send one chat turn and return the assistant message object.

        When tools are supplied, the response can contain a tool call instead of
        final text. The loop is responsible for executing tools and adding their
        results to the next messages list.
        """
        request: dict[str, Any] = {
            "model": self.model,
            "messages": list(messages),
            "max_completion_tokens": 700,
        }
        if tools:
            request["tools"] = list(tools)
            request["tool_choice"] = "auto"

        response = self._client.chat.completions.create(**request)
        return response.choices[0].message


def create_provider(
    name: str | None = None,
    model: str | None = None,
) -> ChatProvider:
    """Construct the configured provider; defaults to Groq."""
    provider_name = (name or os.getenv("LLM_PROVIDER", "groq")).strip().lower()
    if provider_name == "groq":
        return GroqProvider(model=model)
    raise ValueError(
        f"Unsupported LLM_PROVIDER {provider_name!r}. Available providers: groq."
    )
