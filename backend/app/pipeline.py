"""One upload, end to end: cleaned rows in, everything the dashboard needs out."""

import time

from app.analyzer import Outcome, ReviewAnalyzer
from app.api_models import AnalyzeResponse, ReviewResult, ReviewStatus, RunLog
from app.cache import Cache
from app.csv_cleaner import CleanReview
from app.insights import build_product_stats, build_rating_check, build_summary, is_rating_mismatch
from app.llm_client import ChatClient
from app.themes import ThemeFinder


def run_analysis(reviews: list[CleanReview], llm: ChatClient, cache: Cache, batch_size: int) -> AnalyzeResponse:
    started = time.perf_counter()

    analyzer = ReviewAnalyzer(llm, cache, batch_size)
    unique = [review for review in reviews if review.status == "valid"]  # no empties, no duplicates
    outcomes = analyzer.analyze(unique)

    # Duplicates share the outcome of their original through the same text hash.
    results = [to_result(review, outcomes.get(review.text_hash)) for review in reviews]
    insights = ThemeFinder(llm, cache).find(results)

    counters = analyzer.counters
    return AnalyzeResponse(
        reviews=results,
        summary=build_summary(results),
        insights=insights,
        rating_check=build_rating_check(results),
        products=build_product_stats(results),
        run=RunLog(
            model=llm.model,
            unique_reviews=len(unique),
            cache_hits=counters.cache_hits,
            sent_to_ai=counters.sent_to_ai,
            ai_calls=llm.stats.requests,
            rate_limit_retries=llm.stats.backoff_retries,
            validation_retries=counters.validation_retries,
            failed=counters.failed,
            elapsed_ms=round((time.perf_counter() - started) * 1000),
        ),
    )


def to_result(review: CleanReview, outcome: Outcome | None) -> ReviewResult:
    analysis = outcome.analysis if outcome else None
    status: ReviewStatus
    if review.status in ("skipped_empty", "duplicate"):
        status = review.status
    else:
        status = "analysed" if analysis else "analysis_failed"
    return ReviewResult(
        review_id=review.review_id,
        product=review.product,
        rating=review.rating,
        rating_raw=review.rating_raw,
        date=review.date,
        text=review.text,
        text_hash=review.text_hash,
        status=status,
        duplicate_of=review.duplicate_of,
        flags=review.flags,
        analysis=analysis,
        failure_reason=outcome.failure_reason if outcome and status == "analysis_failed" else None,
        rating_mismatch=analysis is not None and is_rating_mismatch(review.rating, analysis.sentiment),
    )
