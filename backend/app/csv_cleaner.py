"""Parse an uploaded reviews CSV and clean it before anything reaches the AI.

File-level problems (not UTF-8, missing columns, no rows) raise CsvFormatError.
Row-level problems never raise: the row is kept and flagged so the dashboard can show it.
"""

import csv
import hashlib
import html
import io
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from typing import Literal

REQUIRED_COLUMNS = ("review_id", "product", "rating", "date", "review_text")
MAX_ROWS = 5000

HTML_TAG = re.compile(r"</?[a-zA-Z][^<>]*>")  # needs a letter after "<", so "I <3 it" survives
WHITESPACE = re.compile(r"\s+")
INJECTION_HINT = re.compile(
    r"ignore (all |any )?(the )?(previous|prior|above) instructions"
    r"|disregard .{0,40}instructions"
    r"|system prompt",
    re.IGNORECASE,
)

RowStatus = Literal["valid", "skipped_empty", "duplicate"]


class CsvFormatError(ValueError):
    """The file cannot be read as a reviews CSV at all."""


@dataclass
class CleanReview:
    review_id: str
    product: str
    rating: int | None  # None means unknown (missing or invalid)
    rating_raw: str
    date: str | None  # ISO date, None if missing or invalid
    text: str  # cleaned text, "" when the review is empty
    text_hash: str  # fingerprint used for duplicates and the cache, "" when empty
    status: RowStatus = "valid"
    duplicate_of: str | None = None
    flags: list[str] = field(default_factory=list)


def parse_reviews_csv(data: bytes) -> list[CleanReview]:
    """Turn raw upload bytes into cleaned reviews, marking empty rows and duplicates."""
    reader = csv.DictReader(io.StringIO(_decode(data), newline=""), restkey="_extra")
    if not reader.fieldnames:
        raise CsvFormatError("The file is empty.")
    reader.fieldnames = [name.strip().lower() for name in reader.fieldnames]
    missing = [column for column in REQUIRED_COLUMNS if column not in reader.fieldnames]
    if missing:
        raise CsvFormatError(
            f"Missing column(s): {', '.join(missing)}. Expected: {', '.join(REQUIRED_COLUMNS)}."
        )

    reviews: list[CleanReview] = []
    first_id_by_hash: dict[str, str] = {}
    try:
        for row_number, row in enumerate(reader, start=1):
            if row_number > MAX_ROWS:
                raise CsvFormatError(f"Too many rows: the limit is {MAX_ROWS} reviews per file.")
            review = clean_row(row, row_number)
            if review.status == "valid":
                original_id = first_id_by_hash.get(review.text_hash)
                if original_id is None:
                    first_id_by_hash[review.text_hash] = review.review_id
                else:
                    review.status = "duplicate"
                    review.duplicate_of = original_id
            reviews.append(review)
    except csv.Error as exc:
        raise CsvFormatError(f"The file is not a valid CSV: {exc}") from exc

    if not reviews:
        raise CsvFormatError("The file has a header row but no reviews.")
    return reviews


def clean_row(row: dict, row_number: int) -> CleanReview:
    flags: list[str] = []

    review_id = _cell(row.get("review_id"))
    if not review_id:
        review_id = f"ROW-{row_number}"
        flags.append("missing_id")

    product = _cell(row.get("product")) or "Unknown product"

    rating_raw = _cell(row.get("rating"))
    rating = parse_rating(rating_raw)
    if rating is None:
        flags.append("rating_invalid" if rating_raw else "rating_missing")

    date_raw = _cell(row.get("date"))
    review_date = parse_date(date_raw)
    if review_date is None:
        flags.append("date_invalid" if date_raw else "date_missing")

    raw_text = row.get("review_text") or ""
    extra_cells = row.get("_extra")
    if extra_cells:  # an unquoted comma split the text into extra columns: stitch it back
        raw_text = ",".join([raw_text, *(cell or "" for cell in extra_cells)])
        flags.append("extra_columns_merged")

    text, had_html = clean_text(raw_text)
    if had_html:
        flags.append("html_removed")
    if INJECTION_HINT.search(text):
        flags.append("possible_injection")

    is_empty = not has_content(text)
    return CleanReview(
        review_id=review_id,
        product=product,
        rating=rating,
        rating_raw=rating_raw,
        date=review_date,
        text="" if is_empty else text,
        text_hash="" if is_empty else fingerprint(text),
        status="skipped_empty" if is_empty else "valid",
        flags=flags,
    )


def parse_rating(raw: str) -> int | None:
    """Return a whole-number rating from 1 to 5, or None for anything else ("", "five", "4.5", "9")."""
    try:
        value = float(raw)
    except ValueError:
        return None
    if value.is_integer() and 1 <= value <= 5:
        return int(value)
    return None


def parse_date(raw: str) -> str | None:
    try:
        return date.fromisoformat(raw).isoformat()
    except ValueError:
        return None


def clean_text(raw: str) -> tuple[str, bool]:
    """Decode HTML entities, drop HTML tags and collapse whitespace. Returns (text, had_html)."""
    unescaped = unicodedata.normalize("NFC", html.unescape(raw))
    without_tags = HTML_TAG.sub(" ", unescaped)
    return WHITESPACE.sub(" ", without_tags).strip(), without_tags != unescaped


def has_content(text: str) -> bool:
    """True if there is at least one letter, digit or emoji, so "👍👍" counts but "..." does not."""
    return any(char.isalnum() or unicodedata.category(char) == "So" for char in text)


def fingerprint(text: str) -> str:
    """Case-insensitive hash of the cleaned text, used for duplicate detection and the AI cache."""
    return hashlib.sha256(text.casefold().encode("utf-8")).hexdigest()


def _decode(data: bytes) -> str:
    try:
        return data.decode("utf-8-sig")  # also strips the BOM Excel adds
    except UnicodeDecodeError as exc:
        raise CsvFormatError("The file must be UTF-8 encoded (in Excel: Save As > CSV UTF-8).") from exc


def _cell(value: str | None) -> str:
    return (value or "").strip()
