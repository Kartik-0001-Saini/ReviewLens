from pathlib import Path

import pytest

from app.csv_cleaner import CsvFormatError, clean_text, parse_rating, parse_reviews_csv

SAMPLE_CSV = Path(__file__).resolve().parents[2] / "reviews.csv"
HEADER = "review_id,product,rating,date,review_text\n"


def parse(body: str):
    return parse_reviews_csv((HEADER + body).encode("utf-8"))


def by_id(reviews):
    return {review.review_id: review for review in reviews}


def test_sample_file_messy_rows_are_handled():
    reviews = by_id(parse_reviews_csv(SAMPLE_CSV.read_bytes()))

    assert len(reviews) == 30
    assert reviews["R005"].status == "skipped_empty"  # empty text
    assert reviews["R009"].status == "valid"  # emoji-only is still a review
    assert reviews["R010"].rating is None and "rating_missing" in reviews["R010"].flags
    assert reviews["R022"].rating is None and "rating_invalid" in reviews["R022"].flags
    assert reviews["R022"].rating_raw == "five"
    assert reviews["R015"].status == "duplicate" and reviews["R015"].duplicate_of == "R012"
    assert "possible_injection" in reviews["R012"].flags
    assert reviews["R024"].text.startswith("Love it! Keeps") and "html_removed" in reviews["R024"].flags
    assert reviews["R016"].text == "आवाज़ अच्छी है लेकिन बैटरी जल्दी खत्म हो जाती है।"


def test_duplicates_ignore_case_and_spacing():
    reviews = parse('A1,Mug,5,2026-10-01,"Great   mug"\nA2,Mug,4,2026-10-02,"great mug "\n')
    assert reviews[1].status == "duplicate"
    assert reviews[1].duplicate_of == "A1"
    assert reviews[0].text_hash == reviews[1].text_hash


def test_review_text_spanning_several_lines_is_one_review():
    reviews = parse('A1,Mug,5,2026-10-01,"Line one\nline two"\nA2,Mug,4,2026-10-02,"Next"\n')
    assert [r.review_id for r in reviews] == ["A1", "A2"]
    assert reviews[0].text == "Line one line two"


def test_punctuation_only_text_counts_as_empty():
    assert parse('A1,Mug,5,2026-10-01,"..."\n')[0].status == "skipped_empty"


def test_unquoted_comma_in_text_is_stitched_back():
    review = parse("A1,Mug,5,2026-10-01,Nice mug, but small\n")[0]
    assert review.text == "Nice mug, but small"
    assert "extra_columns_merged" in review.flags


def test_missing_id_product_and_bad_date_are_flagged_not_fatal():
    review = parse(',,3,not-a-date,"Fine"\n')[0]
    assert review.review_id == "ROW-1"
    assert review.product == "Unknown product"
    assert review.date is None
    assert {"missing_id", "date_invalid"} <= set(review.flags)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("5", 5), ("1", 1), (" 4 ", 4), ("4.0", 4), ("4.5", None), ("0", None), ("6", None),
     ("five", None), ("", None), ("nan", None)],
)
def test_parse_rating(raw, expected):
    assert parse_rating(raw) == expected


def test_clean_text_keeps_less_than_signs_that_are_not_tags():
    assert clean_text("I <3 this &amp; that")[0] == "I <3 this & that"


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (b"", "empty"),
        (b"id,text\n1,hello\n", "Missing column"),
        (HEADER.encode(), "no reviews"),
        ("review_id,product,rating,date,review_text\nA1,Mug,5,2026-10-01,café\n".encode("latin-1"), "UTF-8"),
    ],
)
def test_unreadable_files_raise_a_clear_error(data, message):
    with pytest.raises(CsvFormatError, match=message):
        parse_reviews_csv(data)


def test_header_names_are_trimmed_and_case_insensitive():
    data = b"\xef\xbb\xbf Review_ID ,Product,Rating,Date,Review_Text\nA1,Mug,5,2026-10-01,Nice\n"
    assert parse_reviews_csv(data)[0].review_id == "A1"
