# Disaster Early Warning & Evacuation Alert Route System

A college project exploring an early-warning and evacuation-support workflow, starting with public USGS earthquake data. The repository currently contains local earthquake-feed processing, an educational risk heuristic, and a configurable preliminary geographic impact estimate. It does not send alerts, calculate evacuation routes, or connect to AWS.

## Current milestone

- Python standard-library component to fetch and normalize USGS GeoJSON earthquake observations with source IDs, UTC timestamps, and optional depth.
- Configurable, explicitly heuristic risk classification with a rule/reason result; missing magnitude is `unknown`, not low.
- Configurable freshness filtering and source-scoped duplicate resolution for normalized events.
- Configurable preliminary impact-radius estimate, bounding box, and candidate-distance check. This is not a validated damage boundary or safety recommendation.
- Unit tests using mocked HTTP responses; no live API access is needed to run tests.

## Setup and tests

Python 3.10 or newer is recommended. No third-party packages are required.

```powershell
$env:PYTHONPATH = "backend/src"
py -m unittest discover -s backend/tests -v
```

The fetcher can also be used from the repository root:

```powershell
$env:PYTHONPATH = "backend/src"
py -c "from disaster_fetcher import fetch_earthquakes; print(fetch_earthquakes())"
```

The default feed is the USGS past-day all-earthquakes GeoJSON feed. Set `USGS_FEED_URL` to another USGS GeoJSON feed URL when needed. Network access is required only when calling the fetcher, not when running tests.

Geographic estimation is available from `impact_estimation.py` and requires explicit `ImpactParameters` coefficients; no scientific threshold is implied. The current magnitude/depth formula is a project heuristic only. The fetcher's normalized event has latitude/longitude under `coordinates`; depth can be supplied as optional `depth_km`. No route safety, affected-area accuracy, shelter availability, or evacuation recommendation is established.

The fetcher represents USGS `time` and `updated` as integer epoch milliseconds and UTC ISO-8601 strings. `event_quality.py` is a separate pure processing step; callers pass normalized observations to it after fetching. It uses a configurable 24-hour maximum event age by default, allows five minutes of future clock skew, and treats `(source, source_id)` as the event identity. For duplicate records, the newest `updated_ms` wins (event time is the fallback); equal versions keep the first. Freshness is determined from the earthquake origin timestamp, so a later catalogue revision does not make an old event current. The processor returns separate `accepted`, `stale`, `duplicates`, and `rejected` collections. These limits are processing policy, not scientific thresholds.

`explain_risk()` returns a classification, rule identifier, reason, inputs, and thresholds separately from the observed event. A missing magnitude returns `unknown`. The legacy `assess_risk()` function remains available and still requires a valid magnitude.

## Project documentation

- [Architecture](docs/architecture.md)
- [Complete implementation plan](docs/implementation-plan.md)

The frontend is a future phase and is intentionally not scaffolded yet. AWS resources and integrations are also planned, not implemented.
