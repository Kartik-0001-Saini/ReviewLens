import pytest
from factories import make_result as result

from app.insights import (
    build_product_stats,
    build_rating_check,
    build_summary,
    is_rating_mismatch,
    topic_count_themes,
)


@pytest.mark.parametrize(
    ("rating", "sentiment", "expected"),
    [(5, "negative", True), (4, "negative", True), (1, "positive", True), (2, "positive", True),
     (5, "positive", False), (3, "negative", False), (4, "neutral", False), (None, "negative", False)],
)
def test_rating_mismatch_only_flags_opposite_directions(rating, sentiment, expected):
    assert is_rating_mismatch(rating, sentiment) is expected


def test_summary_counts_unique_analysed_reviews_only():
    reviews = [
        result("R1", "positive"),
        result("R2", "negative", needs_reply=True),
        result("R3", "neutral"),
        result("R4", "negative", needs_reply=True, status="duplicate"),  # not counted twice
        result("R5", status="skipped_empty"),
        result("R6", status="analysis_failed"),
    ]
    summary = build_summary(reviews)

    assert (summary.total_rows, summary.analysed, summary.duplicates) == (6, 3, 1)
    assert (summary.skipped_empty, summary.failed, summary.needs_reply) == (1, 1, 1)
    assert summary.sentiment_percent.positive == 33.3
    assert summary.sentiment_percent.negative == 33.3


def test_summary_of_nothing_analysed_has_zero_percentages():
    summary = build_summary([result("R1", status="skipped_empty")])
    assert summary.analysed == 0 and summary.sentiment_percent.positive == 0.0


def test_rating_check_agreement_and_mismatches():
    reviews = [
        result("R1", "positive", rating=5),  # agrees
        result("R2", "negative", rating=5),  # mismatch (like R008)
        result("R3", "neutral", rating=3),  # agrees
        result("R4", "negative", rating=None),  # unknown rating: not compared
    ]
    check = build_rating_check(reviews)

    assert (check.compared, check.agreeing) == (3, 2)
    assert check.agreement_percent == 66.7
    assert check.mismatched_ids == ["R2"]


def test_product_stats_top_issues_come_from_complaints():
    reviews = [
        result("R1", "negative", topics=("delivery", "support"), needs_reply=True, product="Mug"),
        result("R2", "negative", topics=("delivery",), needs_reply=True, product="Mug"),
        result("R3", "positive", topics=("quality",), product="Mug"),
        result("R4", "positive", product="Shoes"),
    ]
    mug, shoes = build_product_stats(reviews)

    assert mug.product == "Mug" and mug.analysed == 3 and mug.needs_reply == 2
    assert [(i.topic, i.count) for i in mug.top_issues] == [("delivery", 2), ("support", 1)]
    assert shoes.top_issues == []


def test_topic_count_fallback_themes():
    reviews = [
        result("R1", "negative", topics=("delivery",), needs_reply=True),
        result("R2", "negative", topics=("delivery", "support"), needs_reply=True),
        result("R3", "positive", topics=("quality",)),
    ]
    insights = topic_count_themes(reviews)

    assert insights.source == "topic_counts"
    assert insights.complaints[0].title == "Delivery problems"
    assert insights.complaints[0].review_ids == ["R1", "R2"]
    assert insights.praises[0].title == "Good product quality"
