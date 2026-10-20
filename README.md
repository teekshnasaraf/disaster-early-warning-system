# Disaster Early Warning & Evacuation Alert Route System

A college project exploring an early-warning and evacuation-support workflow, starting with public USGS earthquake data. The repository currently contains local earthquake-feed processing, a reusable processing function, a Lambda-compatible handler, an educational risk heuristic, a configurable preliminary geographic impact estimate, a validated destination data contract, and a routing-provider boundary. It has no real destination inventory, configured routing provider, deployed AWS resources, or alert delivery.

## Current milestone

- Python standard-library component to fetch and normalize USGS GeoJSON earthquake observations with source IDs, UTC timestamps, and optional depth.
- Configurable, explicitly heuristic risk classification with a rule/reason result; missing magnitude is `unknown`, not low.
- Configurable freshness filtering and source-scoped duplicate resolution for normalized events.
- Shared stateless orchestration in `earthquake_processing.py`, returning JSON-serializable event results and processing counts.
- `lambda_handler.handler(event, context)` fetches only the server-configured USGS feed, uses the shared processor, logs a concise count summary, and raises a controlled error if fetching or feed validation fails. It does not use invocation-supplied URLs, AWS credentials, or the AWS SDK.
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

The fetcher represents USGS `time` and `updated` as integer epoch milliseconds and UTC ISO-8601 strings and rejects negative magnitudes at the feed boundary; zero and positive magnitudes remain valid. `earthquake_processing.py` is the shared orchestration function used by both the CLI demo and Lambda handler. It applies `event_quality.py` first, then classifies risk and estimates impact for accepted, individually valid events. It reports accepted, stale, duplicate, and rejected counts; risk-level counts; and available/unavailable impact counts. A malformed individual record is rejected or marked as having unavailable impact, while unexpected pipeline failures propagate. The freshness policy uses a configurable 24-hour maximum event age by default, allows five minutes of future clock skew, and treats `(source, source_id)` as the event identity. For duplicate records, the newest `updated_ms` wins (event time is the fallback); equal versions keep the first. Freshness is determined from the earthquake origin timestamp, so a later catalogue revision does not make an old event current. These limits are processing policy, not scientific thresholds.

The Lambda entry point reads `USGS_FEED_URL` and optional `USGS_TIMEOUT_SECONDS` from server-side environment configuration; the fetcher defaults to the public USGS all-day feed and a 10-second timeout. Invalid timeout configuration fails explicitly. Feed/network/HTTP/JSON validation failures raise `LambdaFeedError` rather than returning a success-shaped result. The handler result contains `status: "ok"` and the concise processor summary; logs do not include the feed payload. This is locally testable code, not a deployed Lambda or a configured trigger.

### Build the Lambda ZIP locally

From the repository root in PowerShell, build the allowlisted, standard-library-only deployment package:

```powershell
.\.venv\Scripts\python.exe scripts\build_lambda_package.py
```

The output is `build\lambda-deployment.zip` (ignored by Git). Its modules are at the ZIP root, so configure the Lambda handler as `lambda_handler.handler`. The script includes only the handler and its internal imports, writes stable ZIP metadata for repeatable builds, and excludes tests, the virtual environment, Git data, fixtures, editor settings, caches, and local configuration files. Use `--output <path>` to choose a different output location.

AWS's [current Lambda runtime table](https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtimes.html) lists `python3.14` as a supported managed runtime (Amazon Linux 2023); `python3.15` is marked public preview and should not be selected for this manual deployment. Runtime support can change, so recheck the table immediately before deployment. The project has no third-party dependencies and uses syntax compatible with Python 3.10+, but local ZIP import tests do not prove compatibility with the AWS runtime; smoke-test in the selected runtime after upload.

For the first manual deployment, use Mumbai (`ap-south-1`), create a Lambda function with runtime `Python 3.14`, and use handler setting `lambda_handler.handler`. In the Lambda console's function page, choose **Code** > **Upload from** > **.zip file**, then select `build\lambda-deployment.zip` and save/deploy the code. Set `USGS_FEED_URL` to the intended server-side USGS HTTPS feed, and optionally set `USGS_TIMEOUT_SECONDS` (default 10 seconds). The timeout is a request timeout, not the Lambda timeout: configure the function timeout to exceed it plus processing/startup overhead; 30 seconds is a reasonable initial setting with the current 10-second default.

The function needs outbound HTTPS (TCP 443) to the configured USGS endpoint. A function not attached to your VPC uses Lambda-managed networking; if attached to a VPC, private-subnet routing, DNS, security-group egress, and a NAT gateway or equivalent internet egress must be configured. A public subnet alone does not provide internet access to the function. Its execution role needs CloudWatch Logs permissions (`logs:CreateLogGroup`, `logs:CreateLogStream`, and `logs:PutLogEvents`); scope them to the function's log group where practical, or pre-create the log group and omit `logs:CreateLogGroup`. AWS's `AWSLambdaBasicExecutionRole` is the standard broader managed option for basic logs.

No AWS resources have been deployed. Live alerts, routing, database writes, API access, and scheduled execution are not part of this milestone. Each invocation fetches and processes the feed independently; there is no persistent deduplication across invocations. Invocation retries may therefore reprocess the same events. Add persistent idempotency before introducing any side effects.

`explain_risk()` returns a classification, rule identifier, reason, inputs, and thresholds separately from the observed event. A missing magnitude returns `unknown`. The legacy `assess_risk()` function remains available and still requires a valid magnitude.

`evacuation_destinations.py` defines validated geographic coordinates, destination records, and an in-memory catalog that rejects duplicate identifiers. Capacity and availability are optional and default to `None` (unknown); provenance defaults to `"unknown"` and the update timestamp defaults to `None`. These fields are not verified by the model. The only destination examples are clearly fictional test fixtures, not real evacuation centres.

`routing.py` defines an injectable boundary for requesting a candidate route from an origin to a designated destination. No provider is configured: requesting a route without one raises `RoutingProviderUnavailableError` and does not return a route. Amazon Location Service is a future adapter, not an implemented integration. Even a future provider route would not establish destination availability, account for unreported hazards or closures, or guarantee safety. The impact heuristic is not used to select destinations or infer route safety.

## Destination source research

The intended region is Tamil Nadu, India, and the requested records are pre-designated facilities. Research of official district-administration publications found plan-based site lists, but no verified statewide machine-readable shelter inventory or API.

The strongest pilot lead is Ramanathapuram District's [2026–27 Disaster Management Plan](https://cdn.s3waas.gov.in/s3f9b902fc3289af4dd08de5d1de54f68f/uploads/2026/09/17899791746482.pdf), linked from the [district disaster-management page](https://ramanathapuram.nic.in/disaster-management/). Its "Multipurpose Evacuation Shelter Locations Details" table lists 23 site entries with serial number, taluk, habitation, type, and a numerical capacity field. The unit for capacity is not stated. The table does not provide verified coordinates, street addresses, persistent facility identifiers, or current per-site operating status. The PDF is not a structured feed, its publication does not establish a live refresh cadence, and reuse terms were not confirmed. This is a candidate source for an authority-verified pilot, not operational destination data.

Other sources reviewed:

- [Cuddalore District disaster-management page](https://cuddalore.nic.in/disaster-management/) links the [2025 plan, Part I](https://cdn.s3waas.gov.in/s3a96b65a721e561e1e3de768ac819ffbb/uploads/2025/08/17556024033256.pdf), with named site tables for Cuddalore but no verified coordinates, per-site capacity/status, structured download, or confirmed reuse terms.
- [Mayiladuthurai District disaster-management page](https://mayiladuthurai.nic.in/disaster-management/) links the [2025 District Disaster Management Plan](https://cdn.s3waas.gov.in/s33871bd64012152bfb53fdf04b401193f/uploads/2025/10/17611130429410.pdf). Its multipurpose evacuation-centre table lists four entries by taluk, village, location, and centre type. Coordinates, stable identifiers, per-site capacity/status, live update cadence, and reuse terms were not confirmed.
- [Thoothukudi District disaster-management page](https://thoothukudi.nic.in/disaster-management/) links a Google My Maps layer labelled "Relief Shelters"; its KML export was reported to contain point names and coordinates. The reviewed source does not establish that these are verified pre-designated facilities, nor provide stable IDs, capacity, operating status, map update date, or accountable data ownership. Google Maps terms restrict copying and mass downloading; this map is not treated as an openly reusable inventory.

Ramanathapuram is the recommended **research pilot district**, based on the reviewed 2026–27 official plan's explicit site-level evacuation designation and capacity field. Before implementation, the District Administration must confirm capacity units and values, provide authoritative coordinates and stable identifiers, confirm source ownership and update cadence, identify the source for current site status, and clarify license/attribution and reuse conditions. No adapter, real destination records, or claim of site availability is implemented.

## Project documentation

- [Architecture](docs/architecture.md)
- [Complete implementation plan](docs/implementation-plan.md)

The frontend is a future phase and is intentionally not scaffolded yet. AWS resources, Amazon Location Service integration, real destination data, and notifications are planned, not implemented.
