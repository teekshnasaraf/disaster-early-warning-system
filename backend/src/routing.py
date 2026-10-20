"""Provider boundary for requesting candidate routes to designated destinations."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from evacuation_destinations import Coordinates, Destination


class RoutingProvider(Protocol):
    """Interface implemented by a future routing service adapter."""

    def request_route(
        self, origin: Coordinates, destination: Destination
    ) -> Mapping[str, object]:
        """Request a provider route response; this does not establish route safety."""
        ...


class RoutingProviderUnavailableError(RuntimeError):
    """Raised when route calculation is requested without a configured provider."""


def request_candidate_route(
    provider: RoutingProvider | None,
    origin: Coordinates,
    destination: Destination,
) -> Mapping[str, object]:
    """Request a candidate route without implying that it is safe.

    No provider is configured by this project. A future adapter may use
    Amazon Location Service, but route results still require hazard review.
    """
    if provider is None:
        raise RoutingProviderUnavailableError(
            "no routing provider is configured; no route was calculated"
        )
    if destination.available is False:
        raise ValueError("cannot request a route to a destination marked unavailable")
    return provider.request_route(origin, destination)
