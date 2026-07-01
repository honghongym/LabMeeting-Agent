from __future__ import annotations

from app.core.enums import ConfidenceTendency


BANNED_BINARY_JUDGEMENT_TERMS = (
    "pass",
    "fail",
    "approved",
    "rejected",
    "通过",
    "不通过",
    "合格",
    "不合格",
    "建议通过",
)


def validate_confidence_tendency(value: str) -> ConfidenceTendency:
    try:
        return ConfidenceTendency(value)
    except ValueError as exc:
        raise ValueError(f"Invalid confidence_tendency: {value}") from exc


def assert_no_binary_defense_judgement(text: str) -> None:
    lowered = text.lower()
    for term in BANNED_BINARY_JUDGEMENT_TERMS:
        if term.lower() in lowered:
            raise ValueError(f"Defense report contains banned binary judgement: {term}")

