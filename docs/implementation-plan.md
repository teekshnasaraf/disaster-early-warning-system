# Complete Implementation Plan

## Project overview and objectives

This college project explores a serverless workflow that consumes public earthquake observations and could eventually help authorized operators assess events and communicate verified emergency information. The planned system uses the USGS Earthquake GeoJSON API, Amazon EventBridge Scheduler, AWS Lambda, Amazon API Gateway, Amazon Location Service, Amazon SNS, and a verified safe-destination dataset.

The objective is an auditable, testable educational prototype, not an official warning service. It must never claim that routes are safe or that a magnitude-only heuristic predicts local impact. Deployment for real emergencies requires current authoritative shelter and hazard data, hazard-aware routing, accessibility and capacity checks, and validation by emergency authorities.

**Implemented in this repository now:** local Python standard-library fetching and normalization of USGS GeoJSON observations with source IDs, integer epoch-millisecond and UTC ISO-8601 timestamps, and optional depth; configurable freshness and duplicate policy; separate explainable heuristic risk classification; configurable preliminary impact-radius and bounding-box estimation using spherical geometry; a validated in-memory destination data contract/catalog; an injectable routing-provider interface that reports when no provider is configured; offline unit tests. No route provider, real destination inventory, AWS resources, frontend, or notifications are implemented.

## Objectives and requirements

### Functional requirements

- Fetch a configurable USGS GeoJSON earthquake feed and validate its structure.
- Normalize stable event identifiers, magnitude, place, timestamp, and longitude/latitude.
- Track observation source identity and UTC event/update timestamps; explicitly report stale, duplicate, and rejected records using configurable policy.
- Apply an explicitly configurable and documented initial risk heuristic, separate from data acquisition.
- Produce explainable risk results; missing magnitude must remain unknown rather than low.
- Validate designated destination records, retain unknown capacity/availability/provenance/freshness explicitly, and reject duplicate destination identifiers.
- Define a provider boundary for candidate-route requests without claiming a route exists or is safe when no routing provider is configured.
- Estimate a preliminary geographic radius with caller-supplied heuristic coefficients and determine candidate proximity; later phases may incorporate authoritative impact data, verified destinations, candidate routes, and reviewed notifications.
- Provide separate scheduled-monitoring and API Gateway request paths with shared, idempotent processing logic.
- Record processing outcomes and prevent duplicate notifications on retries.

### Non-functional requirements

- Use least privilege, secure configuration, HTTPS, bounded timeouts/retries, and no committed credentials.
- Keep processing modular, testable offline, observable, and cost-conscious.
- Fail conservatively on missing, invalid, stale, or uncertain information.
- Make limitations clear: no guarantee of warning completeness, impact accuracy, shelter availability, or route safety.

## Intended architecture and data flow

USGS GeoJSON is polled by Lambda on an EventBridge schedule or on demand through API Gateway. Lambda validates and normalizes events and evaluates configured thresholds. Later, an impact-estimation component and verified destination data produce candidates; Amazon Location Service calculates candidate routes; policy and human review gate any SNS notification. CloudWatch Logs and metrics support operations. Both entry points must share idempotent processing and duplicate-event controls.

### Technology stack

- **Python 3.x / AWS Lambda:** familiar, low-overhead serverless runtime and standard-library testable domain modules.
- **Python standard library (`urllib`, `json`, `unittest`):** adequate for the first feed client and tests without a dependency burden. A maintained HTTP library may be considered only if retry/session needs justify it.
- **AWS EventBridge Scheduler, API Gateway, Lambda, CloudWatch, SNS, and Amazon Location Service:** intended managed services for triggers, HTTPS access, compute, observability, messaging, and candidate route calculations.
- **Infrastructure as Code (AWS SAM or AWS CDK, selected in deployment design):** reproducible resource definitions and reviewable least-privilege policies.
- **GitHub:** source control, pull requests, issue tracking, and automated checks.
- **Frontend:** deferred; no empty application is scaffolded. An operator interface is considered only after backend contracts and user needs are agreed.

## Repository structure

```text
README.md
.gitignore
docs/
  architecture.md
  implementation-plan.md
backend/
  src/
    disaster_fetcher.py
    event_quality.py
    evacuation_destinations.py
    impact_estimation.py
    risk_assessment.py
    routing.py
  tests/
    test_evacuation_destinations.py
    test_disaster_fetcher.py
    test_event_quality.py
    test_impact_estimation.py
    test_risk_assessment.py
frontend/  # future phase; create when an interface is approved
```

The current repository contains the root documentation and the listed backend modules/tests. `frontend/` is intentionally not created until there is a concrete frontend scope.

## Phased implementation and acceptance criteria

### Phase 1: Environment and repository foundation (implemented)

**Deliverables:** Python-oriented `.gitignore`, project README, Git repository on `main`, configured existing GitHub remote, `backend/src/`, `backend/tests/`, and `docs/` structure.

**AWS resources:** None.

**Acceptance criteria:** local setup/test instructions are documented; secrets and local environments are ignored; repository history and remote were inspected before initialization; no unrelated environment configuration is changed.

### Phase 2: Architecture and delivery plan (implemented)

**Deliverables:** architecture diagram and complete phased implementation plan; explicit boundary between implemented and planned features.

**AWS resources:** None.

**Acceptance criteria:** service roles, scheduled versus manual invocation, security/error strategy, costs, testing, limitations, and future route/notification requirements are documented; no guarantee of safe routing is claimed.

### Phase 3: Local earthquake data processing (implemented)

**Deliverables:** configurable USGS feed fetcher, validated normalized observations with source IDs and UTC event/update timestamps, independent configurable risk heuristic with an explainable rule/reason result and `unknown` for missing magnitude, offline mocked unit tests.

**AWS resources:** None.

**Acceptance criteria:** handles network failure, HTTP errors, invalid JSON, malformed structures, and missing/invalid fields; source IDs are explicit; timestamps are integer epoch milliseconds plus UTC ISO-8601, and malformed/out-of-range timestamps are rejected; missing magnitude is represented as unknown, not low; tests make no network requests; risk thresholds are configurable and identified as a non-scientific project heuristic.

### Phase 4: Risk configuration and impact estimation (partially implemented)

**Implemented deliverables:** local `impact_estimation.py` accepts the existing normalized event coordinate mapping (or top-level latitude/longitude), required magnitude, and optional depth. It computes a preliminary radius from explicitly supplied `base_radius_km`, `magnitude_scale_km`, and `depth_scale_km` coefficients, provides a spherical bounding box with antimeridian/pole handling, and checks candidates using haversine distance. Unit tests cover ordinary and boundary cases, invalid/non-finite inputs, poles, and longitude wrapping. This is an illustrative configurable heuristic, not a scientifically grounded model.

**Remaining deliverables:** reviewed configuration schema, scientifically appropriate impact-model inputs, uncertainty representation, versioning/policy for calibrated thresholds, and evaluation of authoritative shaking/intensity or hazard sources, data licensing, latency, coverage, and provenance. Do not treat magnitude or the current radius formula as a local impact model.

**AWS resources:** None initially; managed configuration storage is considered only if deployment requires it.

**Acceptance criteria:** the current geometry and input validation are deterministic and tested; future impact-model assumptions, uncertainty, freshness, and provenance must also be tested and documented. No scientific or official-warning claim without appropriate validation.

### Phase 4A: Event freshness, provenance, and duplicate policy (implemented)

**Deliverables:** source-scoped identity `(source, source_id)`; UTC timestamp validation; configurable maximum event age and future clock tolerance; duplicate resolution by newest catalogue update timestamp with event-origin-time fallback; separate accepted, stale, duplicate, and rejected results. Freshness is based on event-origin time so a later catalogue revision cannot make an old earthquake appear recent. Risk explanations preserve observed values separately from derived labels and return unknown when magnitude is absent. The quality processor is currently a separate local step that callers invoke after fetching; AWS orchestration is future work.

**AWS resources:** None. The processor is in-memory and does not persist duplicate state between executions.

**Acceptance criteria:** deterministic offline tests cover stale boundaries, source-scoped duplicate IDs, update-version selection, missing identities/timestamps, invalid/future timestamps, malformed records, and explainable unknown risk. No magnitude-only result is presented as proof of damage, imminent danger, or route safety.

### Phase 5: Destination-data and safety policy (partially implemented)

**Implemented deliverables:** `evacuation_destinations.py` provides validated coordinates, destination identity/name/type, optional non-negative capacity, tri-state availability (`True`, `False`, or `None` for unknown), data-source label, and an optional timezone-aware update timestamp. The in-memory catalog rejects duplicate identifiers. Missing capacity/availability/update time and unknown provenance remain explicitly unknown; structural validation does not verify source reliability or the truth of supplied values. Tests use clearly labeled fictional records only; no real centres are included.

**Source investigation (2026-10-20; requested region: Tamil Nadu, India):** no statewide machine-readable shelter inventory or API was verified. Official district plans provide useful leads, but none reviewed meets the coordinate, status, and reuse requirements for direct ingestion.

- **Ramanathapuram — recommended research pilot:** the [district disaster-management page](https://ramanathapuram.nic.in/disaster-management/) links the [2026–27 District Disaster Management Plan](https://cdn.s3waas.gov.in/s3f9b902fc3289af4dd08de5d1de54f68f/uploads/2026/09/17899791746482.pdf). The "Multipurpose Evacuation Shelter Locations Details – 23" table has 23 site-level entries and fields for serial number, taluk, habitation, type, and numerical capacity. The table does not state the capacity unit. Verified coordinates, street addresses, persistent identifiers, and current per-site status are absent from the reviewed table. The PDF is not a structured API/download; its title/year does not prove a live inventory refresh cadence. Dataset license/reuse terms were not confirmed.
- **Mayiladuthurai:** the [district disaster-management page](https://mayiladuthurai.nic.in/disaster-management/) links the [2025 District Disaster Management Plan](https://cdn.s3waas.gov.in/s33871bd64012152bfb53fdf04b401193f/uploads/2025/10/17611130429410.pdf). Its multipurpose evacuation-centre table lists four sites by taluk, village, location, and centre type. The reviewed table does not establish coordinates, persistent site IDs, per-site capacity/status, live update cadence, or reuse terms.
- **Cuddalore:** the [district disaster-management page](https://cuddalore.nic.in/disaster-management/) links the [2025 plan, Part I](https://cdn.s3waas.gov.in/s3a96b65a721e561e1e3de768ac819ffbb/uploads/2025/08/17556024033256.pdf), with named evacuation sites in PDF tables. Verified coordinates, per-site capacity/status, structured access, and reuse terms were not established.
- **Thoothukudi geospatial lead:** the [district disaster-management page](https://thoothukudi.nic.in/disaster-management/) links a Google My Maps layer labelled "Relief Shelters"; its KML export has point names and coordinates. The reviewed material does not verify that the points are pre-designated operational centres or provide stable IDs, capacity, status, update date, or accountable map-data ownership. Google Maps [additional terms](https://www.google.com/help/terms_maps/) restrict copying and mass downloading; this is not treated as an open/reusable shelter inventory.

Ramanathapuram is the recommended **research pilot**, not an approved operational source: its recent plan has explicit site-level evacuation designation and a capacity field, more useful for validating the model contract than the other reviewed plan tables. Before any adapter, the District Administration must confirm capacity units/values, authoritative coordinates and stable IDs, accountable data owner, refresh cadence, current-status source/owner, and license/attribution and reuse permissions. No adapter or real destination records are implemented; unknown availability must not be presented as available.

**Remaining deliverables:** obtain an authoritative Tamil Nadu-wide inventory or separately verified district sources; confirm named-site identity, coordinates, accountable source, data/API or download method, license/attribution, update cadence, per-site capacity, status ownership, and accessibility/services/eligibility. Only implement an adapter after the selected source is authorized and can map reliably to the validated model.

**AWS resources:** None for the current in-memory contract. Select a low-cost storage option only after data ownership, freshness, and access requirements are understood.

**Acceptance criteria:** implemented records reject invalid coordinates/metadata and duplicate identifiers; tests cover unknown and unavailable status. Before operational use, no destination may be presented as available without a freshness and verification policy, missing or stale operational data must fail closed, and emergency-authority review must define ownership.

### Phase 6: Candidate routing with Amazon Location Service (partially implemented)

**Implemented deliverables:** `routing.py` defines a `RoutingProvider` protocol and `request_candidate_route()` boundary. With no provider configured, requests raise `RoutingProviderUnavailableError`; the application calculates no route. It also refuses a destination explicitly marked unavailable. Tests verify both conditions. No AWS credentials or third-party dependencies are required.

**Remaining deliverables:** Amazon Location Service adapter and candidate-route response contract, distance/travel estimates, and tests using mocked service responses. Compare routes with authoritative hazard/closure information and clearly label unresolved hazards. Location Service calculates candidate routes; it does not certify that a route avoids active hazards or is safe. Include accessibility and transport-mode assumptions.

**AWS resources:** None for the implemented interface. Amazon Location Service resources/configuration and narrowly scoped Lambda IAM permissions only after account, region, pricing, data-provider, and policy review.

**Acceptance criteria:** implemented behavior explicitly reports no route when no provider is configured and does not request a route for a destination marked unavailable. Future candidate routes are never described as guaranteed safe; unavailable hazard/closure data blocks or visibly qualifies recommendations; test service failures, no-route responses, and malformed data; estimate and monitor request costs.

### Phase 7: AWS processing service and scheduled monitoring (planned)

**Deliverables:** Lambda handler packaging shared with tested domain modules; EventBridge Scheduler configuration; bounded polling cadence, feed selection, timeout/backoff policy, event version tracking, idempotency store design, and CloudWatch structured logs/metrics/alarms.

**AWS resources:** AWS Lambda, EventBridge Scheduler, CloudWatch Logs/metrics/alarms, and only the minimum state store needed for deduplication; IAM execution role scoped to those resources.

**Acceptance criteria:** scheduler invokes the handler at the configured cadence; errors do not create an alert storm; retries and dead-letter/failure handling are bounded; duplicate/revised events are handled deterministically; deployment and teardown are repeatable and cost estimates approved.

### Phase 8: API Gateway manual/integration endpoint (planned)

**Deliverables:** versioned endpoint contract, request validation, response/error schema, authorization approach, throttling, and Lambda integration. Proposed initial contract: `POST /v1/earthquakes/process` accepts an optional feed selector and dry-run flag; `GET /health` reports service health without exposing secrets. The processing route should default to dry-run/no notification until an explicitly authorized workflow exists.

**AWS resources:** Amazon API Gateway and Lambda integration, logging, usage/throttling controls, and IAM/resource policies as appropriate.

**Acceptance criteria:** authenticated/authorized access appropriate to use, validated bounded input, no arbitrary URL fetching, useful non-sensitive errors, and tests for success, invalid input, throttling, and upstream failures. API invocation is separate from the EventBridge schedule but reuses processing logic.

### Phase 9: Notification workflow with Amazon SNS (planned)

**Deliverables:** notification policy, consent/recipient management plan, message templates, operator approval gate, idempotency keys, delivery status/error handling, suppression/cooldown policy, and opt-out/retention process.

**AWS resources:** SNS topic/subscriptions and least-privilege publish IAM permission only after privacy, consent, cost, and emergency-authority review.

**Acceptance criteria:** dry-run and test destinations precede real recipients; no duplicate alert on retry; messages include source/time/uncertainty and direct recipients to authoritative emergency guidance; no notification based solely on unvalidated heuristic; no personal recipient data in logs.

### Phase 10: Frontend/operator experience (planned, conditional)

**Deliverables:** only after user research and API contract approval, build a minimal accessible operator interface for reviewing events, uncertainty, candidate destinations/routes, and notification approval. The frontend is deferred and no AWS resources are assumed until its hosting/authentication needs are decided.

**Acceptance criteria:** keyboard and screen-reader access, clear distinction between observations and recommendations, explicit uncertainty and data freshness, role-based authorization, and usability review with intended users.

### Phase 11: Verification, deployment, and final demonstration (planned)

**Deliverables:** reproducible IaC deployment, runbook, teardown instructions, cost summary, test evidence, demo dataset/scenario, known-limitations checklist, and final presentation.

**AWS resources:** only the reviewed resources from accepted preceding phases, preferably in a dedicated low-cost development environment with budgets and teardown.

**Acceptance criteria:** tests and security checks pass; deployment is repeatable; monitoring and rollback/teardown are demonstrated; demo clearly labels simulated versus live behavior and does not send unsolicited real alerts. Emergency authorities validate any operational claims before real-world use.

## Integration strategies

### USGS API

Use an official USGS GeoJSON feed URL configured without credentials. Set a finite timeout, send a descriptive user agent where appropriate, validate content and schema, retain source IDs and event/update timestamps in UTC, and respect public service capacity with conservative cadence and exponential backoff/jitter on transient failures. The local policy uses origin time for freshness and catalogue update time only to choose among duplicate versions. Its configurable age/skew limits are data-quality policy, not hazard thresholds. Do not retry permanent client errors indefinitely. Never assume every earthquake is represented immediately or that feed magnitude is sufficient for impact assessment.

### Risk and geographic impact

Keep source observations, freshness/deduplication decisions, risk classification, and impact estimation separate. `explain_risk()` includes a rule ID, reason, inputs, thresholds, and a level; a missing magnitude is unknown. The legacy `assess_risk()` remains for callers that have a validated magnitude. Neither API creates an official warning. The implemented radius heuristic is `(base_radius_km + magnitude_scale_km * max(magnitude, 0)) / (1 + depth_km / depth_scale_km)`, with depth treated as zero when absent. Its coefficients are explicitly supplied by the caller and are demonstration parameters, not invented scientific thresholds. The bounding box uses a spherical Earth envelope; longitude bounds wrap at the antimeridian and expand to all longitudes when a pole is reached. Candidate membership uses great-circle haversine distance. These outputs identify geometry relative to the heuristic only. Before any geographic recommendation, select and validate authoritative shaking/intensity or hazard data; account for distance, depth, local conditions, uncertainty, data freshness, and model coverage. Fail closed or require human review when material inputs are missing.

### Destinations and routes

The local destination record validates structure only; it does not obtain, verify, or refresh destinations. Its optional capacity and availability values default to unknown, as do update timestamps and provenance when absent. Test fixtures are fictional. Obtain operational data from accountable authorities and record provenance and refresh/status dates. Amazon Location Service is not connected; the local routing interface raises an explicit error when no provider is injected. A future adapter may calculate candidate routes between coordinates, but this does not make a route hazard-aware or certify safety. Route screening requires current authoritative closures/hazards and human emergency-policy review. Label routes as candidates and provide a fallback to official guidance when data is incomplete.

### Notifications

SNS is a later delivery transport, not an alert policy. Require authorized approval, recipient consent and subscription management, reviewed templates, source/time/uncertainty, cooldown/suppression, idempotency, and delivery-failure monitoring. Begin with dry-run or controlled test subscribers; never notify real recipients during the current milestone.

### EventBridge and API Gateway

Use EventBridge Scheduler for independent periodic polling with a modest configurable cadence, timezone/UTC clarity, bounded retries, and failure destination. Use API Gateway for explicit authenticated manual/integration requests with input validation and throttling. Both should invoke the same idempotent domain workflow; API requests must not silently change the scheduled cadence or bypass notification approval.

## Reliability, security, and testing

- **Errors and retries:** classify transient network/5xx/rate-limit failures separately from invalid input/schema and permanent HTTP failures. Use bounded exponential backoff with jitter; honor service retry guidance. Set timeouts at each network/service boundary and return actionable, non-sensitive errors.
- **Logging/monitoring:** structured logs with correlation, invocation, and event IDs; metrics for fetch success/failure, events processed, deduplication, routing outcomes, and notification delivery. Avoid secrets and personal data; set retention and alarms.
- **Duplicate prevention:** persist processed event IDs plus relevant update/version state and notification idempotency keys. Define how revised USGS event magnitude/location updates are processed without duplicate messaging. Use conditional writes/transactions where available.
- **Current local data quality:** `event_quality.py` is a pure in-memory processor; it validates timestamps, uses configurable age/skew limits, and resolves duplicate versions deterministically. It does not persist seen IDs across separate runs, so durable idempotency remains a deployment-phase requirement.
- **IAM/security:** separate deployment and runtime roles; least-privilege resource-scoped permissions for logs, state, Location, and SNS; protect API Gateway with appropriate authentication, authorization, throttling, and TLS; use managed secrets only if a future integration requires them. Do not commit `.env`, credentials, tokens, keys, or generated sensitive data.
- **Unit tests:** standard-library `unittest` for parsing, validation, threshold boundaries, malformed responses, timeouts, HTTP errors, and duplicate logic, with mocked HTTP/AWS boundaries.
- **Integration tests:** deploy to a dedicated test environment with controlled AWS resources, test IAM and service contracts, use test-only SNS subscriptions, and clean up afterward. Keep default tests offline and free of AWS cost.
- **End-to-end tests:** exercise scheduled and API Gateway paths through a sandbox feed/fixture, idempotency store, candidate route adapter, and test notification sink. Test failure/retry paths and ensure no production recipients are contacted.

## Three-member GitHub collaboration workflow

- Protect `main`; require reviewed pull requests and passing tests. Never force-push shared branches.
- Member 1 owns feed ingestion, normalization, and source-data tests; Member 2 owns risk/impact and destination/route domain contracts; Member 3 owns AWS infrastructure, API/scheduling, observability, and integration tests. Rotate review and demo responsibilities; agree on interfaces before parallel implementation.
- Use short-lived branches named `feature/<topic>`, `docs/<topic>`, or `fix/<topic>`, focused commits, and issues with acceptance criteria. Require at least one teammate review, no secrets, and green CI before merge.
- Rebase/merge according to team policy without rewriting shared `main`; resolve conflicts in pull requests. Tag demonstrable milestones and record deployment/test evidence in the README or release notes.

## Cost controls

Keep local tests free of AWS calls. Use AWS budgets/billing alerts before deployment, a dedicated development account or sandbox, the lowest suitable invocation frequency, bounded log retention, small function timeouts/memory appropriate to measurements, and test-only subscriptions. Monitor Location requests, API Gateway/Lambda invocations, log ingestion, and state-store usage. Avoid always-on infrastructure, set teardown dates, and delete temporary resources after demonstrations. Validate current regional pricing before approving each phase; do not create paid resources as part of the current milestone.

## Risks, limitations, and future enhancements

Risks include delayed or unavailable feeds, evolving event revisions, false positives/negatives from simplistic thresholds, missing local hazard context, stale or inaccessible shelters, unsafe route assumptions, notification delays/duplication, privacy/consent obligations, and cloud cost or IAM misconfiguration. Mitigations include explicit uncertainty, conservative fail-closed behavior, human approval, verified data ownership, idempotency, least privilege, sandbox testing, and authority review.

Future work may include validated intensity/hazard data, additional hazard sources, shelter capacity/status integration, hazard-aware closure screening, accessibility-aware routing, multilingual accessible notifications, delivery acknowledgements, an operator interface, and collaboration with emergency-management authorities. These are proposals, not current capabilities.