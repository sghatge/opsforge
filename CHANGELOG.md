# Changelog

## v0.4.0 — Override control & redesigned dashboard
- **Failed-result override control.** Approving a gate whose run produced a
  failing Campaign QA result (`fail`) or a NOT READY readiness result
  (`not_ready`) now requires a written `override_reason` of at least 15
  characters. Without it the API returns 400 and the run stays paused.
- Overrides are stored with an `[OVERRIDE: <verdict>]` prefix on the
  approval and logged as a distinct `approval.override` audit event carrying
  the approver, verdict and reason. Normal approvals log `approval.granted`
  with the verdict.
- Run detail (`GET /api/runs/{id}`) now includes a `gate` block: verdict,
  severity (`block` / `caution` / `ok`), label and whether an override is
  required. Rejection never needs an override.
- Dashboard redesign: grouped sidebar navigation with a pending-decision
  counter, hero overview with live KPIs and recent activity, step timeline
  for runs, verdict banner on every approval, override reason box with a live
  character counter, readable audit feed with overrides highlighted, toast
  notifications, and light/dark themes.
- 7 new tests (`tests/test_override.py`); existing approval tests updated.
  72 tests in total.
- Fixed: `pyproject.toml` version now matches the package version.

## v0.3.1 — Demo mode
- `python -m opsforge --demo` seeds a realistic, de-identified sample
  environment on first run: 3 processes with maturity assessments, SOP
  drafts, passing and failing QA reports, audience validations, a readiness
  assessment, an ROI analysis, 5 agent runs (one completed with a human
  sign-off, one deliberately left awaiting the user's decision) and verified
  adapters.
- New `POST /api/demo/seed` endpoint and a "Load demo data" button on the
  dashboard Overview — seeding is idempotent and never touches existing data.
- All demo records are labelled "(demo)" and are produced through the
  platform's own services and agents, never inserted directly.
- New `tests/test_demo.py` (5 tests) covering population, idempotency,
  the pending approval flow and HTTP route behaviour.

## v0.3.0 — Enterprise AI Agent Layer

**New**
- Controlled agent architecture: five registered agents (Campaign QA, SOP
  Drafting, Audience Validation, Deployment Readiness, Operations Reporting),
  each with a fixed plan of steps bound to named tools.
- Orchestrator with a persisted run state machine and full execution ledger
  (`agent_runs`, `agent_steps`).
- Human approval workflow: approval-gated steps pause runs until a named
  person approves or rejects; agents cannot self-approve; every decision is
  audit-logged.
- Configurable QA rules engine: the nine default checks are now database
  rows with full CRUD API — QA behaviour changes without code changes.
- Integration adapters: `mock_crm` (synthetic) and `adobe_campaign` (dry-run
  interface stub); registry synced to DB, connectivity checks audited.
- Pluggable AI provider interface (`LLMProvider`) shipping a deterministic,
  template-driven implementation selected via `OPSFORGE_LLM_PROVIDER`.
- Dashboard: Agent Workspace, Run Ledger with inline approval, QA rules
  manager, adapters panel, audit trail view.
- `/api/audit` endpoint and richer `/api/metrics`.
- 60 automated tests (services, agent layer, live HTTP integration).

**Changed**
- Campaign QA engine rewritten to be rule-driven (previously a fixed checklist).
- Readiness assessment treats missing/unclear inputs as "review", not "fail".

**Stability fixes during hardening**
- Adapter connectivity check now syncs the registry first (previous versions
  could report `unverified` after a successful check).
- `/api/runs` route with no agent filter no longer errors.
- Thread-local run context for concurrent HTTP requests.

## v0.2.0 — Intelligent CRM Operations Engine
- Audience segmentation CSV validator, consent checks, volume caps.
- Nine-point deployment readiness assessment.
- Evidence register with audit events; improved SOP drafts; dashboard controls.

## v0.1.0 — MVP
- Process register, CSA assessments, SOP generator, campaign email QA,
  ROI calculator, SQLite persistence, browser dashboard, REST API.
