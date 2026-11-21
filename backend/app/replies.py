"""Suggested replies, generated only when the store owner clicks the button."""

from pydantic import ValidationError

from app.analyzer import CACHE_NAMESPACE as ANALYSIS_NAMESPACE
from app.analyzer import analysis_cache_key
from app.cache import Cache
from app.llm_client import ChatClient, request_validated
from app.prompts import build_reply_messages
from app.schemas import ReplyResponse, ReviewAnalysis

CACHE_NAMESPACE = "reply"


class ReviewNotFoundError(LookupError):
    pass


class ReplyNotNeededError(ValueError):
    pass


class ReplyWriter:
    def __init__(self, llm: ChatClient, cache: Cache):
        self.llm = llm
        self.cache = cache

    def suggest(self, text_hash: str) -> tuple[str, bool]:
        """Return (reply, served_from_cache).

        The browser only sends the review's hash. The text is looked up here on the server, so this
        endpoint cannot be used to send arbitrary prompts to the AI.
        """
        key = analysis_cache_key(self.llm.model, text_hash)
        entry = self.cache.get(ANALYSIS_NAMESPACE, key)
        try:
            analysis = ReviewAnalysis.model_validate(entry["analysis"])
        except (TypeError, KeyError, ValidationError) as exc:
            raise ReviewNotFoundError("Review not found. Upload and analyse the file again.") from exc
        if not analysis.needs_reply:
            raise ReplyNotNeededError("This review was not marked as needing a reply.")

        cached = self.cache.get(CACHE_NAMESPACE, key)
        if cached and isinstance(cached.get("reply"), str):
            return cached["reply"], True

        messages = build_reply_messages(entry["product"], entry["text"], analysis.summary, analysis.topics)
        reply = request_validated(self.llm, messages, ReplyResponse).reply.strip()
        self.cache.put(CACHE_NAMESPACE, key, {"reply": reply})
        return reply, False
