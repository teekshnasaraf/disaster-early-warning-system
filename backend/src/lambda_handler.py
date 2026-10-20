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

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LambdaConfig:
    """Server-side feed and timeout configuration for one invocation."""

    feed_url: str | None
    timeout_seconds: float

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
        return cls(feed_url=feed_url, timeout_seconds=timeout_seconds)


class LambdaFeedError(RuntimeError):
    """Controlled failure raised when the upstream USGS feed cannot be processed."""


def handler(event: object, context: object) -> dict[str, object]:
    """Fetch and process the server-configured USGS feed.

    Invocation payload and context are intentionally not used for selecting a
    feed URL. No AWS SDK, credential, persistent storage, or notification is
    required by this handler.
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
    logger.info(
        "Earthquake processing completed: %s",
        json.dumps(summary, sort_keys=True, separators=(",", ":"), allow_nan=False),
    )
    return {"status": "ok", "summary": summary}
