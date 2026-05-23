# Business Memory Desktop Runtime v1

## Summary
Build a macOS-first desktop product that packages `Enterprise_KG`, `Google_Connect`, and an optional Obsidian bridge into one local-first runtime with a bootstrap app, while keeping the RevOS integration boundary as a stable HTTP API rather than raw MCP. Internally, ship a supervised multi-service stack: `Enterprise_KG API`, `Enterprise_KG MCP`, `Google_Connect read/write MCP`, `Postgres + pgvector`, `Neo4j`, and a small `memory-gateway` service. Obsidian is optional in v1 and runs through a host-side bridge because the current integration depends on the user’s local app/vault/plugin.

The implementation target for v1 is:
- macOS only
- one desktop bootstrap app for onboarding and runtime control
- hybrid local + cloud model
- Obsidian optional, not required for core function
- RevOS integrates with `memory-gateway` over HTTP
- MCP remains an internal/agent interface, not the primary RevOS contract

## Implementation Changes

### 1. Product topology
Implement a new product wrapper repo or top-level deployment repo, not inside any one existing repo, with these deployable components:

- `desktop-bootstrap`
  A signed macOS desktop app that handles onboarding, configuration, health checks, start/stop, upgrades, and diagnostics.
- `runtime-compose`
  A Docker Compose stack for local services.
- `memory-gateway`
  A new HTTP service that composes EKG, Google, and Obsidian context into RevOS-facing business memory APIs.
- `obsidian-bridge`
  A host-side helper that verifies live Obsidian connectivity and exposes a narrow local HTTP bridge to the runtime when available.

Do not try to put the Obsidian plugin/server itself into Docker. The current Obsidian MCP path is host-local and vault-specific, so the product must treat it as a local dependency with discovery and validation.

### 2. Containerized runtime
Create a Compose topology with persistent named volumes and explicit service networking:

- `postgres`
  Stores evidence, embeddings, and runtime relational state.
- `neo4j`
  Stores operational graph state.
- `enterprise_kg_api`
  FastAPI service from `Enterprise_KG`.
- `enterprise_kg_mcp`
  MCP service from `Enterprise_KG`.
- `google_connect_read_mcp`
  Read MCP server from `Google_Connect`.
- `google_connect_write_mcp`
  Write MCP server from `Google_Connect`.
- `memory_gateway`
  New orchestration and product API service.
- optional `vector/queue sidecars`
  Excluded from v1 unless required by a concrete runtime bottleneck.

Use mounted persistent volumes for:
- EKG RDF store
- EKG runtime uploads
- Postgres data
- Neo4j data
- Google OAuth token storage
- product config and logs

Do not mount the source repos directly in production mode. Build versioned images and mount only data/config/secrets.

### 3. RevOS-facing API contract
Add a stable HTTP API in `memory-gateway`. This is the contract RevOS should use in v1.

Required endpoints:
- `GET /health`
  Returns per-subsystem health, version, and degraded-mode flags.
- `POST /context/search`
  Unified search across EKG, Google, and optional Obsidian.
- `POST /context/person`
  Returns a synthesized person brief with citations and source breakdown.
- `POST /context/account`
  Returns a company/account brief with citations and source breakdown.
- `POST /context/meeting-prep`
  Returns a meeting prep bundle with emails, docs, notes, tasks, and explicit uncertainty markers.
- `POST /context/capture-note`
  Writes a note to EKG and, when enabled, mirrors to Obsidian.
- `POST /sync/google`
  Triggers Google sync jobs and returns status.
- `POST /sync/obsidian`
  Triggers Obsidian ingest or refresh when the bridge is available.
- `GET /status/connectors`
  Returns auth and connectivity status for Google, Obsidian, EKG, and storage.

Response rules:
- every synthesized result includes `citations`, `source_types`, `warnings`, and `degraded_mode`
- every write/mutation includes `performed`, `blocked_reason`, and `audit_id`
- every partial failure is explicit; no silent fallback

Do not expose raw MCP tools to RevOS in v1.

### 4. Google auth and config model
Refactor `Google_Connect` auth and config so it is product-safe for end users:

- replace repo-relative token assumptions with runtime-configurable data paths
- store OAuth refresh/access tokens in a product-managed secrets directory outside the image
- bootstrap auth through the desktop app using a local browser flow
- keep Google scopes minimal and explicit per feature set
- add a product status endpoint or probe that verifies Gmail, Calendar, Drive, and Tasks separately
- separate connector config from developer config; do not reuse the current repo `config/google_connect.yaml` directly as the end-user config format

v1 onboarding flow:
1. user installs desktop app
2. app starts local runtime
3. app opens Google auth flow
4. app stores tokens in product data dir
5. app runs connector checks
6. app marks Google surfaces as ready or degraded

### 5. Obsidian integration model
Treat Obsidian as optional in v1.

Bootstrap behavior:
- detect whether Obsidian is installed
- detect whether the required plugin/runtime bridge is available
- allow the user to choose a vault path
- validate read/write and semantic search availability
- if unavailable, continue with Google + EKG only

Implement an `obsidian-bridge` with these duties:
- discovers vault path and bridge/plugin status
- exposes a narrow local HTTP API for `health`, `list files`, `read`, `write`, and `semantic search`
- normalizes bridge failures into explicit status codes for `memory-gateway`
- never blocks core runtime startup if Obsidian is unavailable

Do not make live Obsidian dependency part of the core memory path for search or meeting prep. The gateway should enrich results with Obsidian when available and omit it cleanly otherwise.

### 6. EKG packaging and transport
Package `Enterprise_KG` as both:
- `api` container for product calls
- `mcp` container for agent/tool runtime use

Add or confirm:
- production Dockerfiles for API and MCP
- `.dockerignore`
- externalized env/secrets
- mounted data dirs for RDF and uploads
- real health checks that verify Neo4j, Postgres, and ontology/RDF readiness
- MCP transport remains available for agent runtimes; HTTP product integration goes to API/gateway

Do not collapse EKG MCP into the FastAPI process. Keep the current separation.

### 7. Desktop bootstrap app
Implement the bootstrap app as the user-facing control plane. It must do:

- first-run wizard
  - choose storage location
  - start local runtime
  - connect Google
  - optionally connect Obsidian
  - validate all services
- runtime control
  - start
  - stop
  - restart
  - open logs
  - export diagnostics
- upgrade flow
  - pull newer images or bundled artifacts
  - run compatibility checks
  - preserve volumes and tokens
- status dashboard
  - Google connector health
  - Obsidian bridge health
  - EKG/DB health
  - disk usage
  - last sync times

Use Docker Desktop as an explicit v1 prerequisite rather than trying to bundle a container runtime in the first release.

### 8. Sync and ingest behavior
Use this ingestion model in v1:

- Google is a first-class live connector
  - Gmail
  - Calendar
  - Drive docs/files
  - Tasks
- Obsidian is an optional memory source and note target
- EKG is the canonical business-memory core for graph/evidence workflows
- `memory-gateway` assembles unified context from all available sources

Sync rules:
- initial full sync on onboarding is opt-in and scoped
- incremental sync is the default ongoing mode
- background sync schedules are configured in the desktop app, not hard-coded in Compose
- every sync job writes structured status and metrics
- gateway uses explicit source freshness metadata in responses

### 9. Security, tenancy, and local/cloud split
Use a hybrid local + cloud model with strict boundaries:

Local-only in v1:
- Postgres data
- Neo4j data
- RDF store
- Google tokens
- Obsidian vault access
- local logs and diagnostics

Cloud-optional in v1:
- RevOS API calls into the user’s local gateway
- optional future hosted backup or telemetry, excluded from the first implementation unless separately approved

Security rules:
- no secrets in images
- no repo `.env` reuse in product builds
- signed desktop builds
- local API binds to localhost by default
- mutation endpoints require a local session token issued by the desktop app
- audit every connector mutation and note write

### 10. Deliverable sequencing
Implement in this order:

1. `runtime-compose` foundation
- production Compose
- persistent volumes
- health checks
- image builds for EKG API/MCP and Google MCP servers

2. `memory-gateway`
- health/status API
- unified search
- meeting prep
- person/account briefs
- sync triggers

3. `Google_Connect` product refactor
- runtime config paths
- token path externalization
- connector readiness probes
- onboarding-safe auth flow

4. `obsidian-bridge`
- host detection
- health/read/write/search bridge
- optional integration path

5. `desktop-bootstrap`
- onboarding
- service control
- diagnostics
- upgrade management

6. RevOS integration
- switch RevOS to gateway HTTP endpoints
- keep MCP out of the direct app boundary

## Public APIs / Interfaces
Add these new public interfaces:

- `memory-gateway` HTTP API
  This is the only new RevOS-facing product API.
- desktop app config schema
  Must define storage path, enabled connectors, sync policy, and optional vault path.
- connector status schema
  Shared status model across Google, Obsidian, EKG, Postgres, and Neo4j.
- local auth/session model
  Desktop app issues a local session token to authorize gateway mutations.

Adjust these existing interfaces:

- `Google_Connect` config/input paths
  Must stop assuming repo-local config and token files.
- `Enterprise_KG` container/runtime env
  Must support clean product env injection and persistent data mounts.
- Obsidian integration contract
  Must move from direct MCP-client configuration toward a host bridge contract usable by the gateway.

## Test Plan

### Core runtime
- Compose stack starts cleanly on a new machine with no repo checkout.
- All persistent volumes survive restart and upgrade.
- Health endpoints fail loudly when Postgres, Neo4j, or RDF data are unavailable.

### Google onboarding and sync
- New user completes Google auth from desktop app without editing files manually.
- Token refresh works after app restart.
- Gmail, Calendar, Drive, and Tasks report independent readiness/degraded states.
- Incremental sync resumes from persisted state after restart.

### Obsidian optional path
- Product works fully with Obsidian absent.
- Product detects a valid Obsidian install and vault and enables enrichment.
- Broken or missing Obsidian plugin degrades only Obsidian-backed features, not the whole runtime.
- Note write and semantic search failures are surfaced explicitly.

### Gateway behavior
- `/context/search` returns source-broken-down results with citations.
- `/context/meeting-prep` works with Google-only and with Google+Obsidian.
- Partial source failure sets warnings and degraded-mode flags.
- Mutation endpoints reject unauthenticated local calls.

### Desktop UX
- First-run wizard completes without terminal usage.
- User can restart services and export diagnostics.
- Upgrade preserves tokens, DBs, RDF, and config.

## Assumptions and Defaults
- `MCP` was the intended term.
- v1 is macOS-only.
- Docker Desktop is an acceptable prerequisite for v1.
- Obsidian remains optional.
- RevOS will call a local HTTP gateway, not embedded MCP tools.
- Hosted cloud sync/backup is out of scope for the first implementation.
- The implementation should be done in a new deployment/product repo that vendors or versions the three existing repos rather than forcing one repo to own the whole runtime.
