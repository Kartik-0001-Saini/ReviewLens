"""What we accept back from the AI. Nothing the model returns is used until it passes these models."""

import json
from collections.abc import Iterable
from typing import Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

Sentiment = Literal["positive", "neutral", "negative"]
Topic = Literal["quality", "delivery", "price", "packaging", "support", "size_fit", "other"]

SENTIMENTS: tuple[str, ...] = get_args(Sentiment)
TOPICS: tuple[str, ...] = get_args(Topic)


class StrictModel(BaseModel):
    # strict: "true" is not a bool, 1 is not a string. extra="forbid": unknown fields are an error.
    model_config = ConfigDict(strict=True, extra="forbid")


class ReviewAnalysis(StrictModel):
    """The exact shape the AI must return for one review."""

    sentiment: Sentiment
    topics: list[Topic] = Field(min_length=1)
    summary: str = Field(min_length=1, max_length=200)
    needs_reply: bool

    @field_validator("topics")
    @classmethod
    def drop_repeated_topics(cls, topics: list[str]) -> list[str]:
        return list(dict.fromkeys(topics))

    @field_validator("summary")
    @classmethod
    def make_single_line(cls, summary: str) -> str:
        line = " ".join(summary.split())
        if not line:
            raise ValueError("summary is blank")
        return line


class Theme(StrictModel):
    title: str = Field(min_length=3, max_length=80)
    review_ids: list[str] = Field(min_length=1)


class ThemesResponse(StrictModel):
    """Top complaints and praises found across all analysed reviews."""

    complaints: list[Theme]
    praises: list[Theme]


class ReplyResponse(StrictModel):
    reply: str = Field(min_length=20, max_length=1000)


def validate_batch_response(
    raw: str, expected_ids: Iterable[str]
) -> tuple[dict[str, ReviewAnalysis], dict[str, str]]:
    """Check a batch answer item by item.

    Returns (valid analyses by id, error message by id). Every expected id ends up in exactly
    one of the two, so one bad item never throws away the good ones in the same batch.
    """
    expected = set(expected_ids)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}, dict.fromkeys(expected, "response was not valid JSON")

    items = data.get("results") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return {}, dict.fromkeys(expected, 'response has no "results" list')

    valid: dict[str, ReviewAnalysis] = {}
    errors: dict[str, str] = {}
    for item in items:
        ref = item.get("id") if isinstance(item, dict) else None
        if not isinstance(ref, str) or ref not in expected or ref in valid:
            continue  # unknown or repeated id: ignore rather than guess
        fields = {key: value for key, value in item.items() if key != "id"}
        try:
            valid[ref] = ReviewAnalysis.model_validate(fields)
            errors.pop(ref, None)
        except ValidationError as exc:
            errors[ref] = describe_validation_error(exc)

    for ref in expected - valid.keys() - errors.keys():
        errors[ref] = "missing from the AI response"
    return valid, errors


def describe_validation_error(exc: ValidationError) -> str:
    first = exc.errors()[0]
    location = ".".join(str(part) for part in first["loc"]) or "response"
    return f"{location}: {first['msg']}"
