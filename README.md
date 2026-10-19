# Disaster Early Warning & Evacuation Alert Route System

A college project exploring an early-warning and evacuation-support workflow, starting with public USGS earthquake data. This repository currently contains only the local project foundation and a testable earthquake-feed processing milestone. It does not send alerts, calculate evacuation routes, or connect to AWS.

## Current milestone

- Python standard-library component to fetch and normalize USGS GeoJSON earthquake events.
- Configurable, explicitly heuristic earthquake risk classification.
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

## Project documentation

- [Architecture](docs/architecture.md)
- [Complete implementation plan](docs/implementation-plan.md)

The frontend is a future phase and is intentionally not scaffolded yet. AWS resources and integrations are also planned, not implemented.
