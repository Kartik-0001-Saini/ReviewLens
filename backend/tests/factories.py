"""Build API-level review results for tests without going through the whole pipeline."""

from app.api_models import ReviewResult
from app.insights import is_rating_mismatch
from app.schemas import ReviewAnalysis


def make_result(review_id, sentiment="positive", rating=None, topics=("quality",), needs_reply=False,
                status="analysed", product="Mug"):
    analysis = None
    if status in ("analysed", "duplicate"):
        analysis = ReviewAnalysis(sentiment=sentiment, topics=list(topics), summary="s", needs_reply=needs_reply)
    return ReviewResult(
        review_id=review_id, product=product, rating=rating, rating_raw=str(rating or ""), date=None,
        text="t", text_hash="h", status=status, analysis=analysis,
        rating_mismatch=analysis is not None and is_rating_mismatch(rating, sentiment),
    )
