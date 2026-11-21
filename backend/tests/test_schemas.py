import json

import pytest
from pydantic import ValidationError

from app.schemas import ReviewAnalysis, validate_batch_response

GOOD = {"sentiment": "negative", "topics": ["quality"], "summary": "Earbud died.", "needs_reply": True}


def item(ref, **overrides):
    return {"id": ref, **GOOD, **overrides}


def test_valid_analysis_is_accepted_and_normalised():
    analysis = ReviewAnalysis.model_validate(
        {**GOOD, "topics": ["quality", "quality", "support"], "summary": "Left earbud\n died."}
    )
    assert analysis.topics == ["quality", "support"]
    assert analysis.summary == "Left earbud died."


@pytest.mark.parametrize(
    "bad_fields",
    [
        {"sentiment": "very negative"},  # not in the allowed list
        {"sentiment": "Negative"},  # allowed values are exact
        {"topics": []},  # at least one topic
        {"topics": ["battery"]},  # unknown topic
        {"needs_reply": "true"},  # a string is not a boolean
        {"summary": "   "},  # blank summary
        {"summary": "x" * 201},  # not a one-liner
        {"confidence": 0.9},  # extra field
    ],
)
def test_invalid_analysis_is_rejected(bad_fields):
    with pytest.raises(ValidationError):
        ReviewAnalysis.model_validate({**GOOD, **bad_fields})


def test_missing_field_is_rejected():
    fields = dict(GOOD)
    del fields["needs_reply"]
    with pytest.raises(ValidationError):
        ReviewAnalysis.model_validate(fields)


def test_batch_keeps_good_items_and_reports_bad_or_missing_ones():
    raw = json.dumps({"results": [item("r1"), item("r2", sentiment="angry"), item("r9")]})

    valid, errors = validate_batch_response(raw, ["r1", "r2", "r3"])

    assert set(valid) == {"r1"}
    assert set(errors) == {"r2", "r3"}  # r9 was never sent, so it is ignored
    assert "sentiment" in errors["r2"]
    assert errors["r3"] == "missing from the AI response"


@pytest.mark.parametrize("raw", ["not json", "[1, 2]", '{"results": "nope"}', "{}"])
def test_batch_with_broken_structure_fails_every_item(raw):
    valid, errors = validate_batch_response(raw, ["r1", "r2"])
    assert valid == {}
    assert set(errors) == {"r1", "r2"}


def test_repeated_id_keeps_the_first_valid_answer():
    raw = json.dumps({"results": [item("r1", sentiment="angry"), item("r1"), item("r1", sentiment="positive")]})
    valid, errors = validate_batch_response(raw, ["r1"])
    assert valid["r1"].sentiment == "negative"
    assert errors == {}
