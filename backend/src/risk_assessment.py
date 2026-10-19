"""Configurable educational earthquake risk heuristic; not an official warning."""

from dataclasses import dataclass
import math
from typing import Any, Literal

RiskLevel = Literal["low", "moderate", "high"]


def _is_finite_number(value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


@dataclass(frozen=True)
class RiskThresholds:
    """Magnitude boundaries for the simplified project-only classification."""

    moderate: float = 4.0
    high: float = 6.0

    def __post_init__(self) -> None:
        if not all(_is_finite_number(value) for value in (self.moderate, self.high)):
            raise ValueError("risk thresholds must be finite numbers")
        if self.moderate >= self.high:
            raise ValueError("moderate threshold must be lower than high threshold")


def assess_risk(magnitude: float, thresholds: RiskThresholds = RiskThresholds()) -> RiskLevel:
    """Return a legacy risk label for a valid magnitude.

    This magnitude-only heuristic is not evidence of damage, imminent danger,
    or safe evacuation. Use ``explain_risk`` when missing-data handling and a
    traceable rule explanation are required.
    """
    if not _is_finite_number(magnitude):
        raise ValueError("magnitude must be a number")
    if magnitude < 0:
        raise ValueError("magnitude must not be negative")
    if magnitude >= thresholds.high:
        return "high"
    if magnitude >= thresholds.moderate:
        return "moderate"
    return "low"


def explain_risk(
    magnitude: float | None,
    thresholds: RiskThresholds = RiskThresholds(),
) -> dict[str, Any]:
    """Return an explainable educational classification or ``unknown``.

    Missing magnitude is unknown rather than low risk. The result contains
    only a rule-based label and explanation, not a warning or damage estimate.
    """
    if magnitude is None:
        return {
            "level": "unknown",
            "rule": "magnitude_thresholds_v1",
            "reason": "Magnitude is unavailable; risk cannot be classified.",
            "input": {"magnitude": None},
        }

    level = assess_risk(magnitude, thresholds)
    if level == "high":
        reason = f"Magnitude {magnitude:g} meets or exceeds the configured high threshold ({thresholds.high:g})."
    elif level == "moderate":
        reason = f"Magnitude {magnitude:g} meets the configured moderate threshold ({thresholds.moderate:g}) but is below the high threshold ({thresholds.high:g})."
    else:
        reason = f"Magnitude {magnitude:g} is below the configured moderate threshold ({thresholds.moderate:g})."
    return {
        "level": level,
        "rule": "magnitude_thresholds_v1",
        "reason": reason,
        "input": {"magnitude": float(magnitude)},
        "thresholds": {"moderate": thresholds.moderate, "high": thresholds.high},
    }