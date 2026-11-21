import json

import pytest
from conftest import FakeLLM, make_reviews
from factories import make_result as result

from app.analyzer import ReviewAnalyzer
from app.replies import ReplyNotNeededError, ReplyWriter, ReviewNotFoundError
from app.themes import ThemeFinder


def analysed_reviews():
    return [
        result("R1", "negative", topics=("quality",), needs_reply=True),
        result("R2", "negative", topics=("delivery",), needs_reply=True),
        result("R3", "positive"),
        result("R4", status="skipped_empty"),
    ]


def themes_answer(complaints, praises):
    return json.dumps({"complaints": complaints, "praises": praises})


def test_ai_themes_use_real_ids_and_our_own_counts(cache):
    llm = FakeLLM(script=[themes_answer(
        complaints=[
            {"title": "Late delivery", "review_ids": ["2"]},
            {"title": "Broken on arrival", "review_ids": ["1", "2", "99"]},  # "99" was never sent
            {"title": "Made up", "review_ids": ["42"]},  # only unknown ids: dropped
        ],
        praises=[{"title": "Lovely colours", "review_ids": ["3"]}],
    )])

    insights = ThemeFinder(llm, cache).find(analysed_reviews())

    assert insights.source == "ai"
    assert [(t.title, t.count, t.review_ids) for t in insights.complaints] == [
        ("Broken on arrival", 2, ["R1", "R2"]),
        ("Late delivery", 1, ["R2"]),
    ]
    assert insights.praises[0].review_ids == ["R3"]


def test_themes_are_cached(cache, fake_llm):
    ThemeFinder(fake_llm, cache).find(analysed_reviews())
    second = FakeLLM()
    ThemeFinder(second, cache).find(analysed_reviews())
    assert second.stats.requests == 0


def test_themes_fall_back_to_topic_counts_when_ai_fails_twice(cache):
    llm = FakeLLM(script=["not json", '{"complaints": "nope"}'])
    insights = ThemeFinder(llm, cache).find(analysed_reviews())
    assert insights.source == "topic_counts"
    assert insights.complaints


def test_no_analysed_reviews_means_no_ai_call(cache, fake_llm):
    insights = ThemeFinder(fake_llm, cache).find([result("R1", status="skipped_empty")])
    assert insights.source == "none" and fake_llm.stats.requests == 0


@pytest.fixture
def analysed_hashes(cache):
    reviews = make_reviews("Mug arrived broken", "Lovely colour")
    ReviewAnalyzer(FakeLLM(), cache).analyze(reviews)
    return [review.text_hash for review in reviews]


def test_reply_is_generated_once_then_cached(cache, analysed_hashes):
    llm = FakeLLM()
    writer = ReplyWriter(llm, cache)

    reply, cached = writer.suggest(analysed_hashes[0])
    assert "order number" in reply and cached is False
    assert json.loads(llm.requests[0][1]["content"])["review"] == "Mug arrived broken"

    assert writer.suggest(analysed_hashes[0]) == (reply, True)
    assert llm.stats.requests == 1


def test_reply_refused_for_unknown_or_happy_reviews(cache, analysed_hashes):
    writer = ReplyWriter(FakeLLM(), cache)
    with pytest.raises(ReviewNotFoundError):
        writer.suggest("0" * 64)
    with pytest.raises(ReplyNotNeededError):
        writer.suggest(analysed_hashes[1])
