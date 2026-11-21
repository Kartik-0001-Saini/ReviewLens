"""Shared test helpers. No test here talks to the real Groq API."""

import json

import pytest

from app.cache import Cache
from app.csv_cleaner import CleanReview, fingerprint
from app.llm_client import CallStats
from app.prompts import ANALYSIS_SYSTEM_PROMPT, REPLY_SYSTEM_PROMPT, THEMES_SYSTEM_PROMPT

NEGATIVE_WORDS = ("broken", "terrible", "stopped", "never", "wrong", "rude", "used", "tight")


class FakeLLM:
    """Stands in for Groq. Gives valid answers unless `script` says otherwise.

    `script` is a queue consumed first: each entry is a raw string to return,
    an exception to raise, or a function(messages) -> str.
    """

    model = "fake-model"

    def __init__(self, script=None):
        self.stats = CallStats()
        self.requests = []
        self.script = list(script or [])

    def complete_json(self, messages):
        self.stats.requests += 1
        self.requests.append(messages)
        if self.script:
            step = self.script.pop(0)
            if isinstance(step, Exception):
                raise step
            return step(messages) if callable(step) else step
        return default_answer(messages)

    def sent_reviews(self, request_index):
        """The review texts that went out in one analysis request."""
        data = json.loads(self.requests[request_index][1]["content"])
        return [item["text"] for item in data["reviews"]]


def fake_analysis(item, **overrides):
    negative = any(word in item["text"].lower() for word in NEGATIVE_WORDS)
    return {
        "id": item["id"],
        "sentiment": "negative" if negative else "positive",
        "topics": ["quality"],
        "summary": f"Summary: {item['text'][:30]}",
        "needs_reply": negative,
        **overrides,
    }


def default_answer(messages):
    system = messages[0]["content"]
    data = json.loads(messages[1]["content"])
    if system == ANALYSIS_SYSTEM_PROMPT:
        return json.dumps({"results": [fake_analysis(item) for item in data["reviews"]]})
    if system == THEMES_SYSTEM_PROMPT:
        ids = [review["id"] for review in data["reviews"]]
        return json.dumps({
            "complaints": [{"title": "Items arrive broken", "review_ids": ids[:2]}],
            "praises": [{"title": "Comfortable and well made", "review_ids": ids[2:3]}],
        })
    if system == REPLY_SYSTEM_PROMPT:
        return json.dumps({"reply": "Sorry about this. Please contact support with your order number."})
    raise AssertionError("unexpected prompt")


def make_reviews(*texts, product="Mug"):
    return [
        CleanReview(
            review_id=f"A{i}", product=product, rating=None, rating_raw="", date=None,
            text=text, text_hash=fingerprint(text),
        )
        for i, text in enumerate(texts, start=1)
    ]


@pytest.fixture
def cache(tmp_path):
    return Cache(tmp_path / "cache.db")


@pytest.fixture
def fake_llm():
    return FakeLLM()
