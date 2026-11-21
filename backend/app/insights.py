"""Dashboard numbers, computed in plain code from the validated analyses (no AI involved)."""

from collections import Counter

from app.api_models import (
    InsightTheme,
    Insights,
    ProductStats,
    RatingCheck,
    ReviewResult,
    SentimentCounts,
    SentimentPercent,
    Summary,
    TopicCount,
)

EXPECTED_SENTIMENT = {1: "negative", 2: "negative", 3: "neutral", 4: "positive", 5: "positive"}

COMPLAINT_LABELS = {
    "quality": "Product quality problems",
    "delivery": "Delivery problems",
    "price": "Price feels too high",
    "packaging": "Damaged or poor packaging",
    "support": "Slow or unhelpful support",
    "size_fit": "Wrong size or fit",
    "other": "Other issues",
}
PRAISE_LABELS = {
    "quality": "Good product quality",
    "delivery": "Fast delivery",
    "price": "Good value for money",
    "packaging": "Good packaging",
    "support": "Helpful support",
    "size_fit": "Right size and fit",
    "other": "Other praise",
}


def analysed_only(reviews: list[ReviewResult]) -> list[ReviewResult]:
    """Unique reviews with a valid analysis. Duplicates are left out so nothing is counted twice."""
    return [r for r in reviews if r.status == "analysed" and r.analysis is not None]


def is_complaint(review: ReviewResult) -> bool:
    return review.analysis is not None and (review.analysis.needs_reply or review.analysis.sentiment == "negative")


def is_rating_mismatch(rating: int | None, sentiment: str) -> bool:
    """Stars and text point in opposite directions, e.g. 5 stars with a negative review (R008)."""
    if rating is None:
        return False
    return (rating >= 4 and sentiment == "negative") or (rating <= 2 and sentiment == "positive")


def build_summary(reviews: list[ReviewResult]) -> Summary:
    analysed = analysed_only(reviews)
    statuses = Counter(review.status for review in reviews)
    sentiment = count_sentiments(analysed)
    return Summary(
        total_rows=len(reviews),
        analysed=len(analysed),
        skipped_empty=statuses["skipped_empty"],
        duplicates=statuses["duplicate"],
        failed=statuses["analysis_failed"],
        needs_reply=sum(review.analysis.needs_reply for review in analysed),
        sentiment=sentiment,
        sentiment_percent=SentimentPercent(
            positive=percent(sentiment.positive, len(analysed)),
            neutral=percent(sentiment.neutral, len(analysed)),
            negative=percent(sentiment.negative, len(analysed)),
        ),
    )


def build_rating_check(reviews: list[ReviewResult]) -> RatingCheck:
    rated = [review for review in analysed_only(reviews) if review.rating is not None]
    agreeing = sum(EXPECTED_SENTIMENT[review.rating] == review.analysis.sentiment for review in rated)
    return RatingCheck(
        compared=len(rated),
        agreeing=agreeing,
        agreement_percent=percent(agreeing, len(rated)) if rated else None,
        mismatched_ids=[review.review_id for review in rated if review.rating_mismatch],
    )


def build_product_stats(reviews: list[ReviewResult]) -> list[ProductStats]:
    stats = []
    for product in dict.fromkeys(review.product for review in reviews):  # keeps first-seen order
        rows = [review for review in reviews if review.product == product]
        analysed = analysed_only(rows)
        issues = Counter(topic for review in analysed if is_complaint(review) for topic in review.analysis.topics)
        stats.append(
            ProductStats(
                product=product,
                total_rows=len(rows),
                analysed=len(analysed),
                needs_reply=sum(review.analysis.needs_reply for review in analysed),
                sentiment=count_sentiments(analysed),
                top_issues=[TopicCount(topic=topic, count=count) for topic, count in issues.most_common(3)],
            )
        )
    return stats


def topic_count_themes(reviews: list[ReviewResult]) -> Insights:
    """Fallback for the top complaints and praises when the AI themes are unavailable."""
    analysed = analysed_only(reviews)
    complaints = [review for review in analysed if is_complaint(review)]
    praises = [review for review in analysed if review.analysis.sentiment == "positive"]
    return Insights(
        complaints=_top_topics(complaints, COMPLAINT_LABELS),
        praises=_top_topics(praises, PRAISE_LABELS),
        source="topic_counts" if analysed else "none",
    )


def count_sentiments(reviews: list[ReviewResult]) -> SentimentCounts:
    counts = Counter(review.analysis.sentiment for review in reviews)
    return SentimentCounts(positive=counts["positive"], neutral=counts["neutral"], negative=counts["negative"])


def percent(part: int, whole: int) -> float:
    return round(100 * part / whole, 1) if whole else 0.0


def _top_topics(reviews: list[ReviewResult], labels: dict[str, str]) -> list[InsightTheme]:
    ids_by_topic: dict[str, list[str]] = {}
    for review in reviews:
        for topic in review.analysis.topics:
            ids_by_topic.setdefault(topic, []).append(review.review_id)
    ranked = sorted(ids_by_topic.items(), key=lambda item: len(item[1]), reverse=True)[:3]
    return [InsightTheme(title=labels[topic], count=len(ids), review_ids=ids) for topic, ids in ranked]
