# Disaster Early Warning & Evacuation Alert Route System

A college project exploring an early-warning and evacuation-support workflow, starting with public USGS earthquake data. The repository currently contains local earthquake-feed processing, an educational risk heuristic, a configurable preliminary geographic impact estimate, a validated destination data contract, and a routing-provider boundary. It has no real destination inventory, configured routing provider, AWS integration, or alert delivery.

## Current milestone

- Python standard-library component to fetch and normalize USGS GeoJSON earthquake observations with source IDs, UTC timestamps, and optional depth.
- Configurable, explicitly heuristic risk classification with a rule/reason result; missing magnitude is `unknown`, not low.
- Configurable freshness filtering and source-scoped duplicate resolution for normalized events.
- Configurable preliminary impact-radius estimate, bounding box, and candidate-distance check. This is not a validated damage boundary or safety recommendation.
- A validated destination record/catalog contract with strict coordinate and metadata validation. Unknown capacity, availability, provenance, and update time remain unknown; test fixtures are explicitly fictional.
- An injectable candidate-routing interface. No routing provider is configured, so route requests fail explicitly; Amazon Location Service integration remains planned.
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

A local end-to-end demonstration connecting fetching, quality filtering, heuristic risk assessment, and geographic impact estimation can be run via:

```powershell
$env:PYTHONPATH = "backend/src"
py backend/src/demo.py
```

To run offline using representative sample data without network requests:

```powershell
$env:PYTHONPATH = "backend/src"
py backend/src/demo.py --sample-data
```

The default feed is the USGS past-day all-earthquakes GeoJSON feed. Set `USGS_FEED_URL` to another USGS GeoJSON feed URL when needed. Network access is required only when calling the fetcher, not when running tests.

Geographic estimation is available from `impact_estimation.py` and requires explicit `ImpactParameters` coefficients; no scientific threshold is implied. The current magnitude/depth formula is a project heuristic only. The fetcher's normalized event has latitude/longitude under `coordinates`; depth can be supplied as optional `depth_km`. No route safety, affected-area accuracy, shelter availability, or evacuation recommendation is established.

The fetcher represents USGS `time` and `updated` as integer epoch milliseconds and UTC ISO-8601 strings. `event_quality.py` is a separate pure processing step; callers pass normalized observations to it after fetching. It uses a configurable 24-hour maximum event age by default, allows five minutes of future clock skew, and treats `(source, source_id)` as the event identity. For duplicate records, the newest `updated_ms` wins (event time is the fallback); equal versions keep the first. Freshness is determined from the earthquake origin timestamp, so a later catalogue revision does not make an old event current. The processor returns separate `accepted`, `stale`, `duplicates`, and `rejected` collections. These limits are processing policy, not scientific thresholds.

`explain_risk()` returns a classification, rule identifier, reason, inputs, and thresholds separately from the observed event. A missing magnitude returns `unknown`. The legacy `assess_risk()` function remains available and still requires a valid magnitude.

`evacuation_destinations.py` defines validated geographic coordinates, destination records, and an in-memory catalog that rejects duplicate identifiers. Capacity and availability are optional and default to `None` (unknown); provenance defaults to `"unknown"` and the update timestamp defaults to `None`. These fields are not verified by the model. The only destination examples are clearly fictional test fixtures, not real evacuation centres.

`routing.py` defines an injectable boundary for requesting a candidate route from an origin to a designated destination. No provider is configured: requesting a route without one raises `RoutingProviderUnavailableError` and does not return a route. Amazon Location Service is a future adapter, not an implemented integration. Even a future provider route would not establish destination availability, account for unreported hazards or closures, or guarantee safety. The impact heuristic is not used to select destinations or infer route safety.

## Destination source research

The intended region is Tamil Nadu, India, and the requested records are pre-designated facilities. The official [Cuddalore District disaster-management page](https://cuddalore.nic.in/disaster-management/) links its [2025 District Disaster Management Plan, Part I](https://cdn.s3waas.gov.in/s3a96b65a721e561e1e3de768ac819ffbb/uploads/2025/08/17556024033256.pdf). The plan includes named evacuation-site tables for Cuddalore District, but it is a PDF, not a statewide structured inventory. The reviewed tables do not provide verified coordinates, per-site capacity, or per-site operating status; an annual plan edition does not establish a live status-update cadence. A dataset license or reuse terms were not confirmed.

This district plan is a lead for follow-up with the responsible authorities, not a validated operational feed. No Tamil Nadu-wide site-level inventory, machine-readable API/download, coordinates, capacity, operating-status source, or reuse terms have been verified. No source adapter or real destination records are implemented. Obtain an authoritative statewide inventory or separately verified district sources, including provenance, coordinate validation, update cadence, status ownership, and usage terms, before integrating destinations.

## Project documentation

- [Architecture](docs/architecture.md)
- [Complete implementation plan](docs/implementation-plan.md)

The frontend is a future phase and is intentionally not scaffolded yet. AWS resources, Amazon Location Service integration, real destination data, and notifications are planned, not implemented.
