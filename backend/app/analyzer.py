"""Send unique reviews to the AI in small batches, validate every answer, and cache the good ones."""

from collections.abc import Sequence
from dataclasses import dataclass

from pydantic import ValidationError

from app.cache import Cache
from app.csv_cleaner import CleanReview
from app.llm_client import ChatClient, LLMBadOutputError, LLMUnavailableError
from app.prompts import PROMPT_VERSION, build_analysis_messages
from app.schemas import ReviewAnalysis, validate_batch_response

CACHE_NAMESPACE = "analysis"


def analysis_cache_key(model: str, text_hash: str) -> str:
    """Same text + same model + same prompt = same answer, so the AI is not asked again."""
    return f"{model}|{PROMPT_VERSION}|{text_hash}"


@dataclass
class Outcome:
    analysis: ReviewAnalysis | None  # None means analysis_failed
    failure_reason: str | None = None
    from_cache: bool = False


@dataclass
class AnalyzerCounters:
    cache_hits: int = 0
    sent_to_ai: int = 0
    validation_retries: int = 0
    failed: int = 0


class ReviewAnalyzer:
    def __init__(self, llm: ChatClient, cache: Cache, batch_size: int = 5):
        self.llm = llm
        self.cache = cache
        self.batch_size = batch_size
        self.counters = AnalyzerCounters()

    def analyze(self, reviews: Sequence[CleanReview]) -> dict[str, Outcome]:
        """Analyse unique, non-empty reviews. Returns one Outcome per text_hash."""
        outcomes: dict[str, Outcome] = {}
        pending: list[CleanReview] = []
        for review in reviews:
            cached = self._from_cache(review.text_hash)
            if cached:
                outcomes[review.text_hash] = Outcome(cached, from_cache=True)
                self.counters.cache_hits += 1
            else:
                pending.append(review)

        # Batches go out one after another, never all at once.
        for start in range(0, len(pending), self.batch_size):
            outcomes.update(self._analyze_batch(pending[start : start + self.batch_size]))
        return outcomes

    def _analyze_batch(self, batch: list[CleanReview]) -> dict[str, Outcome]:
        self.counters.sent_to_ai += len(batch)
        analyses: dict[str, ReviewAnalysis] = {}
        try:
            analyses, errors = self._ask(batch)
            if errors:  # retry once, only with the reviews that came back invalid or missing
                self.counters.validation_retries += 1
                retried, errors = self._ask([r for r in batch if r.text_hash in errors])
                analyses.update(retried)
        except LLMUnavailableError as exc:
            # Backoff already retried the request several times; the service is down, so stop here.
            errors = {r.text_hash: f"AI service unavailable: {exc}" for r in batch if r.text_hash not in analyses}

        outcomes: dict[str, Outcome] = {}
        for review in batch:
            analysis = analyses.get(review.text_hash)
            if analysis:
                self._save(review, analysis)
                outcomes[review.text_hash] = Outcome(analysis)
            else:  # failures are not cached, so the next upload tries again
                self.counters.failed += 1
                outcomes[review.text_hash] = Outcome(None, failure_reason=errors.get(review.text_hash))
        return outcomes

    def _ask(self, batch: list[CleanReview]) -> tuple[dict[str, ReviewAnalysis], dict[str, str]]:
        """One AI request. Reviews get short ids (r1, r2...) so the CSV's own ids never reach the model."""
        hash_by_ref = {f"r{i}": review.text_hash for i, review in enumerate(batch, start=1)}
        messages = build_analysis_messages([(ref, review.text) for ref, review in zip(hash_by_ref, batch)])
        try:
            valid, errors = validate_batch_response(self.llm.complete_json(messages), hash_by_ref)
        except LLMBadOutputError as exc:
            valid, errors = {}, dict.fromkeys(hash_by_ref, str(exc))
        return (
            {hash_by_ref[ref]: analysis for ref, analysis in valid.items()},
            {hash_by_ref[ref]: message for ref, message in errors.items()},
        )

    def _from_cache(self, text_hash: str) -> ReviewAnalysis | None:
        entry = self.cache.get(CACHE_NAMESPACE, analysis_cache_key(self.llm.model, text_hash))
        if entry is None:
            return None
        try:  # cached data is re-validated too: a damaged entry just means "analyse again"
            return ReviewAnalysis.model_validate(entry["analysis"])
        except (KeyError, TypeError, ValidationError):
            return None

    def _save(self, review: CleanReview, analysis: ReviewAnalysis) -> None:
        self.cache.put(
            CACHE_NAMESPACE,
            analysis_cache_key(self.llm.model, review.text_hash),
            # text and product are kept so a reply can be written later from just the hash
            {"text": review.text, "product": review.product, "analysis": analysis.model_dump()},
        )
