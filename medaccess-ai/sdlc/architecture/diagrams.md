# Architecture diagrams (generated)
Regenerate with `python -m app.sdlc_engine.export`.

## Patient workflow (rendered from compiled LangGraph)

```mermaid
---
config:
  flowchart:
    curve: linear
---
graph TD;
	__start__([<p>__start__</p>]):::first
	intake(intake)
	clinical_safety(clinical_safety)
	safety_interruption(safety_interruption)
	service_classification(service_classification)
	facility_discovery(facility_discovery)
	geospatial(geospatial)
	availability_search(availability_search)
	recovery(recovery)
	data_quality(data_quality)
	availability_verification(availability_verification)
	eligibility(eligibility)
	wait_time(wait_time)
	recommendation(recommendation)
	expand_search_options(expand_search_options)
	expansion_approval(expansion_approval)
	patient_review(patient_review)
	booking_preparation(booking_preparation)
	human_approval(human_approval)
	booking_handoff(booking_handoff)
	confirmation_verification(confirmation_verification)
	notification(notification)
	audit(audit)
	__end__([<p>__end__</p>]):::last
	__start__ --> intake;
	availability_search -.-> audit;
	availability_search -.-> data_quality;
	availability_search -.-> recovery;
	availability_verification -.-> audit;
	availability_verification -.-> eligibility;
	booking_handoff --> confirmation_verification;
	booking_preparation -.-> audit;
	booking_preparation -.-> human_approval;
	clinical_safety -.-> audit;
	clinical_safety -.-> safety_interruption;
	clinical_safety -.-> service_classification;
	confirmation_verification --> notification;
	data_quality -.-> audit;
	data_quality -.-> availability_verification;
	eligibility -.-> audit;
	eligibility -.-> wait_time;
	expand_search_options -.-> expansion_approval;
	expand_search_options -.-> patient_review;
	expansion_approval -.-> facility_discovery;
	expansion_approval -.-> patient_review;
	facility_discovery -.-> audit;
	facility_discovery -.-> geospatial;
	geospatial -.-> audit;
	geospatial -.-> availability_search;
	human_approval -.-> audit;
	human_approval -.-> booking_handoff;
	intake -.-> audit;
	intake -.-> clinical_safety;
	notification --> audit;
	patient_review -.-> audit;
	patient_review -.-> booking_preparation;
	recommendation -.-> audit;
	recommendation -.-> expand_search_options;
	recommendation -.-> patient_review;
	recovery -.-> audit;
	recovery -.-> data_quality;
	safety_interruption --> audit;
	service_classification -.-> audit;
	service_classification -.-> facility_discovery;
	wait_time -.-> audit;
	wait_time -.-> recommendation;
	audit --> __end__;
	classDef default fill:#f2f0ff,line-height:1.2
	classDef first fill-opacity:0
	classDef last fill:#bfb6fc

```

## AI-SDLC workflow (rendered from compiled LangGraph)

```mermaid
---
config:
  flowchart:
    curve: linear
---
graph TD;
	__start__([<p>__start__</p>]):::first
	business_requirement(business_requirement)
	requirements_analysis(requirements_analysis)
	human_clarification(human_clarification)
	architecture(architecture)
	development(development)
	qa(qa)
	simulation(simulation)
	defect_injection(defect_injection)
	monitoring(monitoring)
	root_cause(root_cause)
	fix(fix)
	regression(regression)
	request_release_approval(request_release_approval)
	release_approval(release_approval)
	deployment(deployment)
	post_release(post_release)
	__end__([<p>__end__</p>]):::last
	__start__ --> business_requirement;
	architecture --> development;
	business_requirement --> requirements_analysis;
	defect_injection --> monitoring;
	deployment --> post_release;
	development --> qa;
	fix --> regression;
	human_clarification -.-> __end__;
	human_clarification -.-> architecture;
	monitoring --> root_cause;
	qa --> simulation;
	regression --> request_release_approval;
	release_approval -.-> __end__;
	release_approval -.-> deployment;
	request_release_approval --> release_approval;
	requirements_analysis --> human_clarification;
	root_cause --> fix;
	simulation --> defect_injection;
	post_release --> __end__;
	classDef default fill:#f2f0ff,line-height:1.2
	classDef first fill-opacity:0
	classDef last fill:#bfb6fc

```

## High-level component architecture

```mermaid
flowchart LR
  UI["React frontend<br/>Christina copilot"] -->|HTTPS / JWT| API["FastAPI /api/v1"]
  API --> SUP["LangGraph supervisor<br/>patient workflow"]
  API --> SDLC["LangGraph AI-SDLC workflow"]
  SUP --> H["Agent harness<br/>budgets, allowlists, breakers"]
  SDLC --> H
  H --> MCP_appointment_availability["MCP: appointment_availability"]
  H --> MCP_facility_directory["MCP: facility_directory"]
  H --> MCP_geolocation["MCP: geolocation"]
  H --> MCP_requisition_rules["MCP: requisition_rules"]
  H --> RAG["RAG knowledge index"]
  API --> DB[("PostgreSQL / SQLite")]
  SUP --> CP[("Checkpoint store")]
  API --> OBS["OpenTelemetry / Prometheus<br/>LangSmith (redacted, opt-in)"]
```

## Search and booking-handoff sequence

```mermaid
sequenceDiagram
  actor P as Patient
  participant C as Christina (UI)
  participant A as FastAPI
  participant G as LangGraph
  participant T as Tools (MCP)
  participant H as Human approval
  P->>C: I need an MRI near Toronto
  C->>A: POST /copilot/chat
  A->>G: start workflow
  G->>G: intake, clinical safety, classification
  G->>T: directory, geo, availability, rules
  T-->>G: typed results (untrusted output sanitised)
  G->>G: verify, eligibility, wait-time, rank
  G-->>A: recommendations (verified vs unverified)
  A-->>C: results + DEMO label
  P->>C: Prepare booking handoff
  C->>A: POST /bookings/request
  A->>G: booking workflow
  G->>H: interrupt() approval
  P->>A: POST /approvals/{id}/decision
  A->>G: resume (Command)
  G-->>C: handoff instructions (NOT_CONFIRMED)
```

## Data flow and privacy controls

```mermaid
flowchart TB
  IN["Patient input"] --> SAFE{"Safety screen"}
  SAFE -->|urgent| EMG["Emergency guidance"]
  SAFE --> MIN["Data minimisation<br/>(service, coarse location, radius)"]
  MIN --> ST[("Workflow state<br/>no free text")]
  ST --> AUD[("Hash-chained audit<br/>redacted")]
  ST --> TEL["Telemetry export<br/>redaction before export"]
  SRC["Availability sources"] -->|untrusted| SAN["Sanitiser"]
  SAN --> ST
```

## Agent-to-tool permissions (from registry)

```mermaid
flowchart LR
  supervisor["Supervisor Agent"]
  intake["Patient Intake Agent"]
  intake -.-> T_geo_resolve_location(["geo.resolve_location"])
  clinical_safety["Clinical Safety Agent"]
  service_classification["Service Classification Agent"]
  facility_discovery["Facility Discovery Agent"]
  facility_discovery -.-> T_directory_search_facilities(["directory.search_facilities"])
  geospatial["Geospatial Intelligence Agent"]
  geospatial -.-> T_geo_filter_by_radius(["geo.filter_by_radius"])
  availability_search["Appointment Availability Agent"]
  availability_search -.-> T_availability_fetch_slots(["availability.fetch_slots"])
  availability_verification["Availability Verification Agent"]
  availability_verification -.-> T_availability_verify_slots(["availability.verify_slots"])
  eligibility["Requisition Eligibility Agent"]
  eligibility -.-> T_requisition_evaluate(["requisition.evaluate"])
  wait_time["Wait-Time Intelligence Agent"]
  recommendation["Recommendation Agent"]
  booking_assistance["Booking Assistance Agent"]
  booking_assistance -.-> T_booking_prepare_handoff(["booking.prepare_handoff"])
  notification["Notification Agent"]
  notification -.-> T_notification_send(["notification.send"])
  rag_knowledge["RAG Knowledge Agent"]
  rag_knowledge -.-> T_knowledge_search(["knowledge.search"])
  data_quality["Data Quality Agent"]
  privacy_security["Privacy and Security Agent"]
  human_approval["Human Approval Agent"]
  audit["Audit Agent"]
  monitoring["Monitoring Agent"]
  recovery["Recovery Agent"]
  recovery -.-> T_availability_fetch_slots(["availability.fetch_slots"])
```

## Local deployment (Docker Compose)

```mermaid
flowchart LR
  subgraph Docker Compose
    FE["frontend (nginx)"] --> BE["backend (uvicorn)"]
    BE --> PG[("postgres:16")]
    BE --> RD[("redis:7")]
    PR["prometheus (profile: monitoring)"] --> BE
    GF["grafana (profile: monitoring)"] --> PR
  end
  U["Browser"] --> FE
```

## Security boundaries

```mermaid
flowchart LR
  subgraph Untrusted
    B["Browser"]
    EXT["External sources / MCP output"]
  end
  subgraph Trusted backend
    API["API: authn (JWT), RBAC, rate limit, validation"]
    WF["Workflows: tool allowlists, approvals, budgets"]
    SEC["Secrets: env / secret store only"]
  end
  subgraph Data
    DB[("DB: encrypted sensitive fields")]
  end
  B -->|TLS| API
  API --> WF
  EXT -->|sanitised| WF
  WF --> DB
  SEC -.-> WF
  WF -->|redacted only| OBS["Observability vendors"]
```
