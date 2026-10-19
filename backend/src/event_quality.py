"""Freshness and duplicate handling for normalized disaster observations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import math
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class FreshnessPolicy:
    """Age limit and allowed clock skew for observed event records."""

    max_age: timedelta = timedelta(hours=24)
    future_tolerance: timedelta = timedelta(minutes=5)

    def __post_init__(self) -> None:
        if self.max_age <= timedelta(0):
            raise ValueError("max_age must be greater than zero")
        if self.future_tolerance < timedelta(0):
            raise ValueError("future_tolerance must not be negative")


def _timestamp_ms(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a finite integer epoch-millisecond timestamp")
    try:
        is_finite = math.isfinite(value)
    except OverflowError:
        is_finite = False
    if not is_finite:
        raise ValueError(f"{field} must be a finite integer epoch-millisecond timestamp")
    if isinstance(value, float) and not value.is_integer():
        raise ValueError(f"{field} must be a finite integer epoch-millisecond timestamp")
    milliseconds = int(value)
    try:
        datetime.fromtimestamp(milliseconds / 1000, tz=timezone.utc)
    except (OverflowError, OSError, ValueError) as error:
        raise ValueError(f"{field} is outside the supported timestamp range") from error
    return milliseconds


def _record_timestamp(event: Mapping[str, Any], field: str) -> int:
    value = event.get(field)
    if value is None and field == "updated_ms":
        return _timestamp_ms(event["timestamp_ms"], "timestamp_ms")
    return _timestamp_ms(value, field)


def process_events(
    events: Iterable[Mapping[str, Any]],
    policy: FreshnessPolicy = FreshnessPolicy(),
    now: datetime | None = None,
) -> dict[str, list[Any]]:
    """Validate, de-duplicate, and freshness-filter normalized observations.

    Event identity is the pair ``(source, source_id)``. For duplicates the
    record with the greatest ``updated_ms`` wins; missing update times fall
    back to ``timestamp_ms``, and equal versions keep the first occurrence.
    Freshness is based on event origin time (``timestamp_ms``), so a catalogue
    revision does not make an old earthquake appear recent.
    Invalid records are reported rather than being silently admitted.
    """
    if not isinstance(policy, FreshnessPolicy):
        raise ValueError("policy must be a FreshnessPolicy")
    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None or current_time.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    current_time = current_time.astimezone(timezone.utc)
    future_tolerance_ms = policy.future_tolerance.total_seconds() * 1000
    max_age_ms = policy.max_age.total_seconds() * 1000
    current_ms = current_time.timestamp() * 1000

    winners: dict[tuple[str, str], tuple[int, Mapping[str, Any]]] = {}
    rejected: list[dict[str, Any]] = []
    duplicates: list[dict[str, Any]] = []

    for index, event in enumerate(events):
        if not isinstance(event, Mapping):
            rejected.append({"index": index, "reason": "event must be a mapping"})
            continue

        source = event.get("source")
        source_id = event.get("source_id")
        if not isinstance(source, str) or not source.strip():
            rejected.append({"index": index, "reason": "missing source identifier"})
            continue
        if not isinstance(source_id, str) or not source_id.strip():
            rejected.append({"index": index, "reason": "missing event source_id"})
            continue

        try:
            timestamp_ms = _record_timestamp(event, "timestamp_ms")
            updated_ms = _record_timestamp(event, "updated_ms")
        except (KeyError, ValueError) as error:
            rejected.append({"index": index, "source_id": source_id, "reason": str(error)})
            continue

        identity = (source.strip(), source_id.strip())
        if timestamp_ms - current_ms > future_tolerance_ms:
            rejected.append({"index": index, "source": identity[0], "source_id": identity[1], "reason": "record timestamp is in the future"})
            continue
        version = updated_ms if event.get("updated_ms") is not None else timestamp_ms
        if updated_ms - current_ms > future_tolerance_ms:
            rejected.append({"index": index, "source": identity[0], "source_id": identity[1], "reason": "update timestamp is in the future"})
            continue
        previous = winners.get(identity)
        if previous is None:
            winners[identity] = (version, event)
        elif version > previous[0]:
            duplicates.append({"source": identity[0], "source_id": identity[1], "action": "replaced_by_newer_record"})
            winners[identity] = (version, event)
        else:
            duplicates.append({"source": identity[0], "source_id": identity[1], "action": "discarded_duplicate"})

    accepted: list[Mapping[str, Any]] = []
    stale: list[dict[str, Any]] = []

    for (source, source_id), (_version, event) in winners.items():
        try:
            record_ms = _record_timestamp(event, "timestamp_ms")
        except (KeyError, ValueError) as error:
            rejected.append({"source": source, "source_id": source_id, "reason": str(error)})
            continue
        age_ms = current_ms - record_ms
        if age_ms < -future_tolerance_ms:
            rejected.append({"source": source, "source_id": source_id, "reason": "record timestamp is in the future"})
        elif age_ms > max_age_ms:
            stale.append({"source": source, "source_id": source_id, "age_seconds": age_ms / 1000})
        else:
            accepted.append(event)

    return {"accepted": accepted, "stale": stale, "duplicates": duplicates, "rejected": rejected}