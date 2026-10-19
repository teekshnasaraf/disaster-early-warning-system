"""Configurable educational earthquake risk heuristic; not an official warning."""

from dataclasses import dataclass
import math
from typing import Literal

RiskLevel = Literal["low", "moderate", "high"]


@dataclass(frozen=True)
class RiskThresholds:
    """Magnitude boundaries for the simplified project-only classification."""

    moderate: float = 4.0
    high: float = 6.0

    def __post_init__(self) -> None:
        if not all(math.isfinite(value) for value in (self.moderate, self.high)):
            raise ValueError("risk thresholds must be finite numbers")
        if self.moderate >= self.high:
            raise ValueError("moderate threshold must be lower than high threshold")


def assess_risk(magnitude: float, thresholds: RiskThresholds = RiskThresholds()) -> RiskLevel:
    """Classify magnitude using project heuristics, not validated safety guidance."""
    if (
        isinstance(magnitude, bool)
        or not isinstance(magnitude, (int, float))
        or not math.isfinite(magnitude)
    ):
        raise ValueError("magnitude must be a number")
    if magnitude < 0:
        raise ValueError("magnitude must not be negative")
    if magnitude >= thresholds.high:
        return "high"
    if magnitude >= thresholds.moderate:
        return "moderate"
    return "low"