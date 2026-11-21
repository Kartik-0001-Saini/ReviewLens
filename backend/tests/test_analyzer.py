import json

import pytest
from conftest import FakeLLM, fake_analysis, make_reviews

from app.analyzer import ReviewAnalyzer
from app.llm_client import LLMBadOutputError, LLMConfigError, LLMUnavailableError

TEXTS = ("Mug arrived broken", "Lovely colour", "Handle is terrible", "Great gift", "Nice size")


def answer_with(**overrides_by_ref):
    """An analysis answer where the given refs (r1, r2...) get bad field values."""
    def respond(messages):
        items = json.loads(messages[1]["content"])["reviews"]
        return json.dumps({"results": [fake_analysis(i, **overrides_by_ref.get(i["id"], {})) for i in items]})
    return respond


def test_reviews_are_sent_in_batches(cache, fake_llm):
    outcomes = ReviewAnalyzer(fake_llm, cache, batch_size=2).analyze(make_reviews(*TEXTS))

    assert fake_llm.stats.requests == 3  # 2 + 2 + 1
    assert [len(fake_llm.sent_reviews(i)) for i in range(3)] == [2, 2, 1]
    assert all(outcome.analysis for outcome in outcomes.values())


def test_second_run_is_served_from_cache(cache, fake_llm):
    reviews = make_reviews(*TEXTS)
    ReviewAnalyzer(fake_llm, cache).analyze(reviews)

    second_llm = FakeLLM()
    analyzer = ReviewAnalyzer(second_llm, cache)
    outcomes = analyzer.analyze(reviews)

    assert second_llm.stats.requests == 0
    assert analyzer.counters.cache_hits == 5
    assert all(outcome.from_cache for outcome in outcomes.values())


def test_invalid_item_is_retried_once_alone(cache):
    llm = FakeLLM(script=[answer_with(r2={"sentiment": "angry"})])
    reviews = make_reviews("Mug arrived broken", "Lovely colour", "Great gift")
    analyzer = ReviewAnalyzer(llm, cache)

    outcomes = analyzer.analyze(reviews)

    assert llm.stats.requests == 2
    assert llm.sent_reviews(1) == ["Lovely colour"]  # only the failed review is re-sent
    assert analyzer.counters.validation_retries == 1
    assert all(outcome.analysis for outcome in outcomes.values())


def test_item_invalid_twice_is_marked_failed_and_not_cached(cache):
    bad = answer_with(r1={"topics": ["battery"]})
    llm = FakeLLM(script=[bad, bad])
    reviews = make_reviews("Battery dies fast")

    outcome = ReviewAnalyzer(llm, cache).analyze(reviews)[reviews[0].text_hash]

    assert outcome.analysis is None
    assert "topics" in outcome.failure_reason
    retry_llm = FakeLLM()
    ReviewAnalyzer(retry_llm, cache).analyze(reviews)
    assert retry_llm.stats.requests == 1  # failure was not cached, so it is asked again


def test_groq_json_failure_is_retried(cache):
    llm = FakeLLM(script=[LLMBadOutputError("the model could not produce valid JSON")])
    reviews = make_reviews("Lovely colour")

    outcomes = ReviewAnalyzer(llm, cache).analyze(reviews)

    assert outcomes[reviews[0].text_hash].analysis is not None
    assert llm.stats.requests == 2


def test_unavailable_service_fails_that_batch_and_moves_on(cache):
    llm = FakeLLM(script=[LLMUnavailableError("HTTP 503")])
    reviews = make_reviews(*TEXTS[:4])

    outcomes = ReviewAnalyzer(llm, cache, batch_size=2).analyze(reviews)

    failed = [r for r in reviews if outcomes[r.text_hash].analysis is None]
    assert [r.text for r in failed] == list(TEXTS[:2])
    assert "AI service unavailable" in outcomes[failed[0].text_hash].failure_reason
    assert llm.stats.requests == 2  # no extra validation retry for a dead service


def test_bad_key_stops_the_run(cache):
    llm = FakeLLM(script=[LLMConfigError("Invalid API Key")])
    with pytest.raises(LLMConfigError):
        ReviewAnalyzer(llm, cache).analyze(make_reviews("Lovely colour"))
