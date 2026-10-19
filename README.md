# Disaster Early Warning & Evacuation Alert Route System

A college project exploring an early-warning and evacuation-support workflow, starting with public USGS earthquake data. The repository currently contains local earthquake-feed processing, an educational risk heuristic, and a configurable preliminary geographic impact estimate. It does not send alerts, calculate evacuation routes, or connect to AWS.

## Current milestone

- Python standard-library component to fetch and normalize USGS GeoJSON earthquake events.
- Configurable, explicitly heuristic earthquake risk classification.
- Configurable preliminary impact-radius estimate, bounding box, and candidate-distance check. This is not a validated damage boundary or safety recommendation.
- Unit tests using mocked HTTP responses; no live API access is needed to run tests.

## Setup and tests

Python 3.10 or newer is recommended. No third-party packages are required.

```powershell
py -m unittest discover -s backend/tests -v
```

The fetcher can also be used from the repository root:

```powershell
$env:PYTHONPATH = "backend/src"
py -c "from disaster_fetcher import fetch_earthquakes; print(fetch_earthquakes())"
```

The default feed is the USGS past-day all-earthquakes GeoJSON feed. Set `USGS_FEED_URL` to another USGS GeoJSON feed URL when needed. Network access is required only when calling the fetcher, not when running tests.

Geographic estimation is available from `impact_estimation.py` and requires explicit `ImpactParameters` coefficients; no scientific threshold is implied. The current magnitude/depth formula is a project heuristic only. The fetcher's normalized event has latitude/longitude under `coordinates`; depth can be supplied as optional `depth_km`. No route safety, affected-area accuracy, shelter availability, or evacuation recommendation is established.

## Project documentation

- [Architecture](docs/architecture.md)
- [Complete implementation plan](docs/implementation-plan.md)

The frontend is a future phase and is intentionally not scaffolded yet. AWS resources and integrations are also planned, not implemented.
