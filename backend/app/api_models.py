"""Shapes of the JSON the API returns. frontend/src/types.ts mirrors these."""

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas import ReviewAnalysis, Topic

ReviewStatus = Literal["analysed", "analysis_failed", "skipped_empty", "duplicate"]


class ReviewResult(BaseModel):
    review_id: str
    product: str
    rating: int | None
    rating_raw: str
    date: str | None
    text: str
    text_hash: str
    status: ReviewStatus
    duplicate_of: str | None = None
    flags: list[str] = []
    analysis: ReviewAnalysis | None = None
    failure_reason: str | None = None
    rating_mismatch: bool = False


class SentimentCounts(BaseModel):
    positive: int = 0
    neutral: int = 0
    negative: int = 0


class SentimentPercent(BaseModel):
    positive: float = 0.0
    neutral: float = 0.0
    negative: float = 0.0


class Summary(BaseModel):
    total_rows: int
    analysed: int  # unique reviews with a valid AI analysis
    skipped_empty: int
    duplicates: int
    failed: int
    needs_reply: int
    sentiment: SentimentCounts
    sentiment_percent: SentimentPercent


class InsightTheme(BaseModel):
    title: str
    count: int
    review_ids: list[str]


class Insights(BaseModel):
    complaints: list[InsightTheme]
    praises: list[InsightTheme]
    source: Literal["ai", "topic_counts", "none"]


class RatingCheck(BaseModel):
    compared: int  # analysed reviews that have a known rating
    agreeing: int
    agreement_percent: float | None
    mismatched_ids: list[str]


class TopicCount(BaseModel):
    topic: Topic
    count: int


class ProductStats(BaseModel):
    product: str
    total_rows: int
    analysed: int
    needs_reply: int
    sentiment: SentimentCounts
    top_issues: list[TopicCount]


class RunLog(BaseModel):
    model: str
    unique_reviews: int
    cache_hits: int
    sent_to_ai: int
    ai_calls: int  # HTTP requests to Groq, including retries
    rate_limit_retries: int
    validation_retries: int
    failed: int
    elapsed_ms: int


class AnalyzeResponse(BaseModel):
    reviews: list[ReviewResult]
    summary: Summary
    insights: Insights
    rating_check: RatingCheck
    products: list[ProductStats]
    run: RunLog


class ReplyRequest(BaseModel):
    text_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class ReplyResult(BaseModel):
    reply: str
    cached: bool
