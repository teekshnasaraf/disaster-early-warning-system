"""AWS Lambda entry point for local earthquake-feed processing."""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import math
import os
from typing import Mapping

from disaster_fetcher import (
    DEFAULT_TIMEOUT_SECONDS,
    EarthquakeFeedError,
    fetch_earthquakes,
)
from earthquake_processing import process_observations
from regional_relevance import ALERTABLE_REGIONAL_RELEVANCE_STATUSES

logger = logging.getLogger(__name__)
DEFAULT_ALERT_MIN_MAGNITUDE = 5.0


@dataclass(frozen=True)
class LambdaConfig:
    """Server-side feed and timeout configuration for one invocation."""

    feed_url: str | None
    timeout_seconds: float
    alerts_enabled: bool = False
    sns_topic_arn: str | None = None
    alert_min_magnitude: float = DEFAULT_ALERT_MIN_MAGNITUDE
    alert_relevance_statuses: frozenset[str] = ALERTABLE_REGIONAL_RELEVANCE_STATUSES

    @classmethod
    def from_environment(
        cls, environ: Mapping[str, str] | None = None
    ) -> LambdaConfig:
        values = os.environ if environ is None else environ
        raw_timeout = values.get("USGS_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS))
        try:
            timeout_seconds = float(raw_timeout)
        except (TypeError, ValueError) as error:
            raise ValueError("USGS_TIMEOUT_SECONDS must be a finite positive number") from error
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("USGS_TIMEOUT_SECONDS must be a finite positive number")

        feed_url = values.get("USGS_FEED_URL")
        if feed_url is not None and not feed_url.strip():
            raise ValueError("USGS_FEED_URL must not be empty")

        raw_alerts_enabled = values.get("ALERTS_ENABLED", "false").strip().lower()
        if raw_alerts_enabled not in {"true", "false"}:
            raise ValueError("ALERTS_ENABLED must be 'true' or 'false'")
        alerts_enabled = raw_alerts_enabled == "true"

        sns_topic_arn = values.get("SNS_TOPIC_ARN")
        if sns_topic_arn is not None and not sns_topic_arn.strip():
            raise ValueError("SNS_TOPIC_ARN must not be empty when provided")
        if alerts_enabled and sns_topic_arn is None:
            raise ValueError("SNS_TOPIC_ARN is required when ALERTS_ENABLED is true")

        raw_min_magnitude = values.get(
            "ALERT_MIN_MAGNITUDE", str(DEFAULT_ALERT_MIN_MAGNITUDE)
        )
        try:
            alert_min_magnitude = float(raw_min_magnitude)
        except (TypeError, ValueError) as error:
            raise ValueError("ALERT_MIN_MAGNITUDE must be a finite non-negative number") from error
        if not math.isfinite(alert_min_magnitude) or alert_min_magnitude < 0:
            raise ValueError("ALERT_MIN_MAGNITUDE must be a finite non-negative number")

        raw_statuses = values.get(
            "ALERT_RELEVANCE_STATUSES",
            ",".join(sorted(ALERTABLE_REGIONAL_RELEVANCE_STATUSES)),
        )
        alert_relevance_statuses = frozenset(
            status.strip() for status in raw_statuses.split(",") if status.strip()
        )
        if not alert_relevance_statuses or not alert_relevance_statuses.issubset(
            ALERTABLE_REGIONAL_RELEVANCE_STATUSES
        ):
            raise ValueError(
                "ALERT_RELEVANCE_STATUSES may contain only "
                "'inside_assessment_area' and 'within_heuristic_radius'"
            )

        return cls(
            feed_url=feed_url,
            timeout_seconds=timeout_seconds,
            alerts_enabled=alerts_enabled,
            sns_topic_arn=sns_topic_arn,
            alert_min_magnitude=alert_min_magnitude,
            alert_relevance_statuses=alert_relevance_statuses,
        )


class LambdaFeedError(RuntimeError):
    """Controlled failure raised when the upstream USGS feed cannot be processed."""


def _is_finite_number(value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _eligible_alerts(
    accepted: list[dict[str, object]],
    config: LambdaConfig,
) -> list[dict[str, object]]:
    eligible: list[dict[str, object]] = []
    for record in accepted:
        event = record["event"]
        risk = record["risk"]
        relevance = record["regional_relevance"]
        if not isinstance(event, Mapping) or not isinstance(risk, Mapping):
            continue
        if not isinstance(relevance, Mapping):
            continue
        magnitude = event.get("magnitude")
        if not _is_finite_number(magnitude) or magnitude < config.alert_min_magnitude:
            continue
        if relevance.get("status") not in config.alert_relevance_statuses:
            continue
        eligible.append(record)
    return eligible


def _publish_sns(topic_arn: str, subject: str, message: str) -> None:
    import boto3

    boto3.client("sns").publish(
        TopicArn=topic_arn,
        Subject=subject,
        Message=message,
    )


def _publish_demo_alerts(
    accepted: list[dict[str, object]],
    config: LambdaConfig,
) -> None:
    if not config.alerts_enabled:
        return
    if config.sns_topic_arn is None:
        raise ValueError("SNS_TOPIC_ARN is required when alerts are enabled")

    for record in _eligible_alerts(accepted, config):
        event = record["event"]
        risk = record["risk"]
        relevance = record["regional_relevance"]
        message = json.dumps(
            {
                "alert_type": "academic_demonstration",
                "disclaimer": (
                    "ACADEMIC DEMONSTRATION ONLY — NOT AN OFFICIAL "
                    "EMERGENCY WARNING."
                ),
                "event_id": event.get("source_id", event.get("id")),
                "magnitude": event.get("magnitude"),
                "risk_level": risk.get("level"),
                "regional_relevance": relevance,
            },
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        _publish_sns(
            config.sns_topic_arn,
            "Academic Demo: Tamil Nadu earthquake relevance",
            message,
        )


def handler(event: object, context: object) -> dict[str, object]:
    """Fetch and process the server-configured USGS feed.

    Invocation payload and context are intentionally not used for selecting a
    feed URL. SNS publishing is opt-in and requires explicit server-side
    configuration; notifications are academic demonstrations, not warnings.
    """
    del event, context
    config = LambdaConfig.from_environment()
    try:
        observations = fetch_earthquakes(
            feed_url=config.feed_url,
            timeout=config.timeout_seconds,
        )
    except EarthquakeFeedError as error:
        raise LambdaFeedError(f"Unable to fetch or validate the USGS feed: {error}") from error

    result = process_observations(observations)
    summary = result["summary"]
    _publish_demo_alerts(result["accepted"], config)
    logger.info(
        "Earthquake processing completed: %s",
        json.dumps(summary, sort_keys=True, separators=(",", ":"), allow_nan=False),
    )
    return {"status": "ok", "summary": summary}
