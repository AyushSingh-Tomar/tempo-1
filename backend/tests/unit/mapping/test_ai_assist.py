"""Whatever the model says is validated by Python before it can become a mapping proposal."""

from __future__ import annotations

from bordereaux.mapping.ai_assist import ColumnToResolve, parse_decisions

FIELD_TYPES = {"gross_premium": "DECIMAL", "commission": "DECIMAL", "insured_name": "STRING", "inception_date": "DATE"}
SENT = {c: ColumnToResolve(c, "no_dictionary_match") for c in ("Amount 1", "Amount 2", "Who")}
COLUMN_TYPES = {"Amount 1": "DECIMAL", "Amount 2": "DECIMAL", "Who": "STRING"}


def parse(decisions, taken=frozenset()):
    return parse_decisions(
        {"decisions": decisions},
        sent=SENT,
        field_types=FIELD_TYPES,
        column_types=COLUMN_TYPES,
        taken=set(taken),
    )


def test_valid_decision_is_accepted_and_clamped() -> None:
    accepted, notes = parse([{"source_column": "Amount 1", "target_field": "gross_premium", "confidence": 7, "reason": "sum"}])
    assert accepted["Amount 1"].target_field == "gross_premium"
    assert accepted["Amount 1"].confidence == 1.0
    assert not notes


def test_hallucinated_field_is_discarded() -> None:
    accepted, notes = parse([{"source_column": "Amount 1", "target_field": "gross_prem_fantasy", "confidence": 0.9}])
    assert accepted == {}
    assert "not a target field" in notes[0]


def test_field_already_mapped_elsewhere_is_discarded() -> None:
    accepted, notes = parse([{"source_column": "Amount 1", "target_field": "gross_premium", "confidence": 0.9}], taken={"gross_premium"})
    assert accepted == {} and "already mapped" in notes[0]


def test_text_column_cannot_become_an_amount() -> None:
    accepted, notes = parse([{"source_column": "Who", "target_field": "gross_premium", "confidence": 0.9}])
    assert accepted == {} and "do not fit" in notes[0]


def test_unknown_source_column_is_ignored() -> None:
    accepted, notes = parse([{"source_column": "Made Up", "target_field": "commission", "confidence": 0.9}])
    assert accepted == {} and "unknown column" in notes[0]


def test_two_columns_for_one_field_keeps_the_more_confident() -> None:
    accepted, _ = parse(
        [
            {"source_column": "Amount 1", "target_field": "gross_premium", "confidence": 0.6},
            {"source_column": "Amount 2", "target_field": "gross_premium", "confidence": 0.9},
        ]
    )
    assert list(accepted) == ["Amount 2"]


def test_null_target_is_a_valid_no_match_answer() -> None:
    accepted, _ = parse([{"source_column": "Amount 1", "target_field": None, "confidence": 0.3, "reason": "claims data"}])
    assert accepted["Amount 1"].target_field is None


def test_garbage_reply_yields_nothing_and_a_note() -> None:
    accepted, notes = parse_decisions("nope", sent=SENT, field_types=FIELD_TYPES, column_types=COLUMN_TYPES, taken=set())
    assert accepted == {} and notes
