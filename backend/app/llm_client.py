"""Small Groq client (OpenAI-compatible chat API) with exponential backoff.

Plain httpx instead of an SDK, so the retry behaviour is ours: visible, testable and easy to change.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.schemas import describe_validation_error

RETRYABLE_STATUS = {429, 500, 502, 503, 504}
MAX_BACKOFF_SECONDS = 30.0

Message = dict[str, str]
ModelT = TypeVar("ModelT", bound=BaseModel)


class LLMError(Exception):
    """Anything that went wrong while asking the AI."""


class LLMConfigError(LLMError):
    """The request was rejected (bad key, unknown model). Retrying will not help."""


class LLMUnavailableError(LLMError):
    """Rate limits, server errors or network problems outlasted every retry."""


class LLMBadOutputError(LLMError):
    """The model answered, but not with usable JSON."""


@dataclass
class CallStats:
    requests: int = 0  # HTTP requests actually sent, including retries
    backoff_retries: int = 0


class ChatClient(Protocol):
    """What the rest of the app needs from an AI client (tests plug in a fake)."""

    model: str
    stats: CallStats

    def complete_json(self, messages: list[Message]) -> str: ...


class GroqClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://api.groq.com/openai/v1",
        timeout: float = 60.0,
        max_retries: int = 4,
        base_delay: float = 1.0,
        reasoning_effort: str = "",
        sleep: Callable[[float], None] = time.sleep,
        transport: httpx.BaseTransport | None = None,
    ):
        if not api_key:
            raise LLMConfigError("GROQ_API_KEY is not set on the server.")
        self.model = model
        self.reasoning_effort = reasoning_effort
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.stats = CallStats()
        self._sleep = sleep
        self._http = httpx.Client(
            base_url=base_url,
            timeout=timeout,
            transport=transport,
            headers={"Authorization": f"Bearer {api_key}"},
        )

    def close(self) -> None:
        self._http.close()

    def complete_json(self, messages: list[Message]) -> str:
        """Run one chat completion in JSON mode and return the raw text the model produced."""
        body = {
            "model": self.model,
            "messages": messages,
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        if self.reasoning_effort:  # only for reasoning models (gpt-oss, qwen); fewer hidden tokens = fewer 429s
            body["reasoning_effort"] = self.reasoning_effort
        attempt = 0
        while True:
            self.stats.requests += 1
            try:
                return self._send(body)
            except _RetryableError as exc:
                if attempt >= self.max_retries:
                    raise LLMUnavailableError(f"{exc} (gave up after {attempt + 1} attempts)") from exc
                self.stats.backoff_retries += 1
                self._sleep(backoff_delay(attempt, exc.retry_after, self.base_delay))
                attempt += 1

    def _send(self, body: dict) -> str:
        try:
            response = self._http.post("/chat/completions", json=body)
        except httpx.TransportError as exc:  # timeouts, DNS failures, dropped connections
            raise _RetryableError(f"network error ({type(exc).__name__})") from exc

        if response.status_code == 200:
            return _message_content(response)

        code, message = _error_info(response)
        if response.status_code in RETRYABLE_STATUS:
            raise _RetryableError(
                f"Groq returned HTTP {response.status_code}: {message}",
                retry_after=response.headers.get("retry-after"),
            )
        if code == "json_validate_failed":  # JSON mode: Groq refuses to return broken JSON
            raise LLMBadOutputError("the model could not produce valid JSON")
        raise LLMConfigError(f"Groq rejected the request (HTTP {response.status_code}): {message}")


def backoff_delay(attempt: int, retry_after: str | None = None, base_delay: float = 1.0) -> float:
    """Wait 1s, 2s, 4s, 8s... (capped). If the server says how long to wait, wait at least that."""
    delay = base_delay * 2**attempt
    if retry_after:
        try:
            delay = max(delay, float(retry_after))
        except ValueError:
            pass  # Retry-After may be an HTTP date; the exponential delay is fine then
    return min(delay, MAX_BACKOFF_SECONDS)


def request_validated(client: ChatClient, messages: list[Message], schema: type[ModelT]) -> ModelT:
    """Ask for JSON matching `schema`. If the answer is invalid, retry once, then give up."""
    problem = ""
    for _ in range(2):
        try:
            return schema.model_validate_json(client.complete_json(messages))
        except ValidationError as exc:
            problem = describe_validation_error(exc)
        except LLMBadOutputError as exc:
            problem = str(exc)
    raise LLMBadOutputError(f"AI answer failed validation twice ({problem})")


class _RetryableError(Exception):
    def __init__(self, message: str, retry_after: str | None = None):
        super().__init__(message)
        self.retry_after = retry_after


def _message_content(response: httpx.Response) -> str:
    try:
        content = response.json()["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise LLMBadOutputError("unexpected response format from Groq") from exc
    if not isinstance(content, str) or not content.strip():
        raise LLMBadOutputError("the model returned an empty answer")
    return content


def _error_info(response: httpx.Response) -> tuple[str, str]:
    """(error code, short message) from a Groq error body. Never includes request headers."""
    try:
        error = response.json()["error"]
        return str(error.get("code") or ""), str(error.get("message") or "")[:300]
    except (ValueError, KeyError, TypeError, AttributeError):
        return "", response.text[:300]
