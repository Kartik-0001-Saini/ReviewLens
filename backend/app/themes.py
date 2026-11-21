"""Top 3 complaints and praises, named by the AI from the analysed review summaries.

The AI only names themes and points at review ids. We check every id, count the reviews ourselves
and rank the themes, so an invented id or an inflated count cannot reach the dashboard.
If the AI fails, the dashboard falls back to plain topic counts.
"""

import hashlib
import json

from pydantic import ValidationError

from app.api_models import InsightTheme, Insights, ReviewResult
from app.cache import Cache
from app.insights import analysed_only, topic_count_themes
from app.llm_client import ChatClient, LLMError, request_validated
from app.prompts import PROMPT_VERSION, build_themes_messages
from app.schemas import Theme, ThemesResponse

CACHE_NAMESPACE = "themes"
MAX_THEMES = 3


class ThemeFinder:
    def __init__(self, llm: ChatClient, cache: Cache):
        self.llm = llm
        self.cache = cache

    def find(self, reviews: list[ReviewResult]) -> Insights:
        analysed = analysed_only(reviews)
        if not analysed:
            return Insights(complaints=[], praises=[], source="none")

        review_by_ref = {str(i): review for i, review in enumerate(analysed, start=1)}
        payload = [
            {"id": ref, "sentiment": r.analysis.sentiment, "topics": r.analysis.topics, "summary": r.analysis.summary}
            for ref, r in review_by_ref.items()
        ]
        key = self._cache_key(payload)

        response = self._from_cache(key)
        if response is None:
            try:
                response = request_validated(self.llm, build_themes_messages(payload), ThemesResponse)
            except LLMError:
                return topic_count_themes(reviews)
            self.cache.put(CACHE_NAMESPACE, key, response.model_dump())

        complaints = _resolve(response.complaints, review_by_ref)
        praises = _resolve(response.praises, review_by_ref)
        if not complaints and not praises:  # every id the AI gave was unknown
            return topic_count_themes(reviews)
        return Insights(complaints=complaints, praises=praises, source="ai")

    def _cache_key(self, payload: list[dict]) -> str:
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        return f"{self.llm.model}|{PROMPT_VERSION}|{digest}"

    def _from_cache(self, key: str) -> ThemesResponse | None:
        entry = self.cache.get(CACHE_NAMESPACE, key)
        if entry is None:
            return None
        try:
            return ThemesResponse.model_validate(entry)
        except ValidationError:
            return None


def _resolve(themes: list[Theme], review_by_ref: dict[str, ReviewResult]) -> list[InsightTheme]:
    """Map the AI's ids back to real review ids, drop unknown ones, count and rank."""
    resolved = []
    for theme in themes:
        ids = list(dict.fromkeys(review_by_ref[ref].review_id for ref in theme.review_ids if ref in review_by_ref))
        if ids:
            resolved.append(InsightTheme(title=theme.title, count=len(ids), review_ids=ids))
    resolved.sort(key=lambda theme: theme.count, reverse=True)
    return resolved[:MAX_THEMES]
