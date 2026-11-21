import json

import httpx
import pytest
from pydantic import BaseModel

from app.llm_client import (
    GroqClient,
    LLMBadOutputError,
    LLMConfigError,
    LLMUnavailableError,
    backoff_delay,
    request_validated,
)

MESSAGES = [{"role": "user", "content": "hi"}]


def ok(content='{"ok": true}'):
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


def error(status, code="", message="boom", headers=None):
    return httpx.Response(status, json={"error": {"code": code, "message": message}}, headers=headers)


def make_client(responses, max_retries=4):
    """A GroqClient wired to a fake HTTP transport that replays `responses` in order."""
    queue = list(responses)
    sent, sleeps = [], []

    def handler(request: httpx.Request):
        sent.append(request)
        result = queue.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    client = GroqClient(
        api_key="test-key",
        model="test-model",
        max_retries=max_retries,
        sleep=sleeps.append,
        transport=httpx.MockTransport(handler),
    )
    return client, sent, sleeps


def test_rate_limit_and_server_errors_back_off_then_succeed():
    client, sent, sleeps = make_client(
        [error(429, headers={"retry-after": "3"}), error(503), ok('{"a": 1}')]
    )

    assert client.complete_json(MESSAGES) == '{"a": 1}'
    assert sleeps == [3.0, 2.0]  # server asked for 3s on the first try; then 2^1 = 2s
    assert client.stats.requests == 3
    assert client.stats.backoff_retries == 2


def test_network_errors_are_retried():
    client, _, sleeps = make_client([httpx.ConnectError("down"), ok()])
    assert client.complete_json(MESSAGES) == '{"ok": true}'
    assert sleeps == [1.0]


def test_gives_up_after_max_retries():
    client, sent, sleeps = make_client([error(500)] * 3, max_retries=2)

    with pytest.raises(LLMUnavailableError, match="gave up after 3 attempts"):
        client.complete_json(MESSAGES)
    assert sleeps == [1.0, 2.0]
    assert len(sent) == 3


def test_bad_key_fails_immediately_without_retrying():
    client, sent, sleeps = make_client([error(401, message="Invalid API Key")])

    with pytest.raises(LLMConfigError, match="Invalid API Key"):
        client.complete_json(MESSAGES)
    assert len(sent) == 1 and sleeps == []


def test_groq_json_validation_failure_is_bad_output_not_a_crash():
    client, _, _ = make_client([error(400, code="json_validate_failed")])
    with pytest.raises(LLMBadOutputError):
        client.complete_json(MESSAGES)


def test_request_uses_json_mode_and_server_side_key():
    client, sent, _ = make_client([ok()])
    client.complete_json(MESSAGES)

    body = json.loads(sent[0].content)
    assert body["response_format"] == {"type": "json_object"}
    assert body["temperature"] == 0
    assert "reasoning_effort" not in body  # only sent when configured
    assert sent[0].headers["authorization"] == "Bearer test-key"


def test_reasoning_effort_is_sent_when_configured():
    sent = []
    client = GroqClient(
        api_key="k", model="m", reasoning_effort="low",
        transport=httpx.MockTransport(lambda request: sent.append(request) or ok()),
    )
    client.complete_json(MESSAGES)
    assert json.loads(sent[0].content)["reasoning_effort"] == "low"


def test_missing_key_is_a_config_error():
    with pytest.raises(LLMConfigError):
        GroqClient(api_key="", model="m")


@pytest.mark.parametrize(
    ("attempt", "retry_after", "expected"),
    [(0, None, 1.0), (1, None, 2.0), (3, None, 8.0), (10, None, 30.0), (0, "5", 5.0), (2, "1", 4.0),
     (0, "Wed, 21 Oct 2026 07:28:00 GMT", 1.0)],
)
def test_backoff_delay(attempt, retry_after, expected):
    assert backoff_delay(attempt, retry_after) == expected


class Answer(BaseModel):
    value: int


class ScriptedClient:
    model = "fake"

    def __init__(self, answers):
        self.answers = list(answers)
        self.calls = 0

    def complete_json(self, messages):
        self.calls += 1
        return self.answers.pop(0)


def test_request_validated_retries_once_on_invalid_answer():
    client = ScriptedClient(['{"value": "not a number"}', '{"value": 7}'])
    assert request_validated(client, MESSAGES, Answer).value == 7
    assert client.calls == 2


def test_request_validated_gives_up_after_second_invalid_answer():
    client = ScriptedClient(["nope", '{"wrong": 1}', '{"value": 1}'])
    with pytest.raises(LLMBadOutputError, match="failed validation twice"):
        request_validated(client, MESSAGES, Answer)
    assert client.calls == 2
