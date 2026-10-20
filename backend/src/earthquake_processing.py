"""Shared, stateless processing for normalized earthquake observations."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import json
from typing import Any, Iterable, Mapping

from event_quality import FreshnessPolicy, process_events
from impact_estimation import ImpactParameters, estimate_impact
from regional_relevance import (
    DEFAULT_TAMIL_NADU_AREA,
    REGIONAL_RELEVANCE_STATUSES,
    TamilNaduAssessmentArea,
    assess_tamil_nadu_relevance,
)
from risk_assessment import RiskThresholds, explain_risk


@dataclass(frozen=True)
class ProcessingConfig:
    """Validated domain settings supplied to the processing pipeline."""

    freshness_policy: FreshnessPolicy = field(default_factory=FreshnessPolicy)
    risk_thresholds: RiskThresholds = field(default_factory=RiskThresholds)
    impact_parameters: ImpactParameters = field(
        default_factory=lambda: ImpactParameters(
            base_radius_km=10.0,
            magnitude_scale_km=5.0,
            depth_scale_km=10.0,
        )
    )
    tamil_nadu_area: TamilNaduAssessmentArea = field(
        default_factory=lambda: DEFAULT_TAMIL_NADU_AREA
    )

    def __post_init__(self) -> None:
        if not isinstance(self.freshness_policy, FreshnessPolicy):
            raise ValueError("freshness_policy must be a FreshnessPolicy")
        if not isinstance(self.risk_thresholds, RiskThresholds):
            raise ValueError("risk_thresholds must be a RiskThresholds")
        if not isinstance(self.impact_parameters, ImpactParameters):
            raise ValueError("impact_parameters must be an ImpactParameters")
        if not isinstance(self.tamil_nadu_area, TamilNaduAssessmentArea):
            raise ValueError("tamil_nadu_area must be a TamilNaduAssessmentArea")


def _source_id(event: Mapping[str, Any]) -> str | None:
    value = event.get("source_id", event.get("id"))
    return value if isinstance(value, str) else None


def process_observations(
    observations: Iterable[Mapping[str, Any]],
    config: ProcessingConfig = ProcessingConfig(),
    now: datetime | None = None,
) -> dict[str, Any]:
    """Quality-filter observations, then derive risk and impact results.

    Invalid records are reported in ``rejected``. A valid risk classification
    may have an unavailable impact estimate when required inputs are missing.
    Unexpected failures in the shared quality processor or configuration are
    allowed to propagate rather than being reported as successful processing.
    """
    if not isinstance(config, ProcessingConfig):
        raise ValueError("config must be a ProcessingConfig")

    records = list(observations)
    quality = process_events(records, policy=config.freshness_policy, now=now)
    accepted: list[dict[str, Any]] = []
    rejected = list(quality["rejected"])
    risk_counts = {"low": 0, "moderate": 0, "high": 0, "unknown": 0}
    impact_available = 0
    impact_unavailable = 0

    for event in quality["accepted"]:
        source_id = _source_id(event)
        try:
            serialized_event = json.loads(json.dumps(dict(event), allow_nan=False))
        except (TypeError, ValueError) as error:
            rejected.append(
                {
                    "source_id": source_id,
                    "reason": f"event is not JSON serializable: {error}",
                }
            )
            continue

        try:
            risk = explain_risk(
                serialized_event.get("magnitude"),
                thresholds=config.risk_thresholds,
            )
        except ValueError as error:
            rejected.append({"source_id": source_id, "reason": str(error)})
            continue

        impact_error = None
        try:
            impact = estimate_impact(serialized_event, config.impact_parameters)
        except ValueError as error:
            impact = None
            impact_error = str(error)
            impact_unavailable += 1
        else:
            impact_available += 1

        risk_counts[risk["level"]] += 1
        accepted.append(
            {
                "event": serialized_event,
                "risk": risk,
                "impact": impact,
                "impact_error": impact_error,
                "regional_relevance": assess_tamil_nadu_relevance(
                    serialized_event,
                    config.impact_parameters,
                    config.tamil_nadu_area,
                ),
            }
        )

    summary = {
        "received": len(records),
        "accepted": len(accepted),
        "stale": len(quality["stale"]),
        "duplicates": len(quality["duplicates"]),
        "rejected": len(rejected),
        "risk_counts": risk_counts,
        "regional_relevance_counts": {
            status: sum(
                item["regional_relevance"]["status"] == status
                for item in accepted
            )
            for status in REGIONAL_RELEVANCE_STATUSES
        },
        "impact_available": impact_available,
        "impact_unavailable": impact_unavailable,
    }
    return {
        "summary": summary,
        "accepted": accepted,
        "stale": quality["stale"],
        "duplicates": quality["duplicates"],
        "rejected": rejected,
    }
