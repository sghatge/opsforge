# OPSFORGE — Architecture (v0.3)

## Principles

1. **Modular services.** Every capability is an importable service module
   with a plain-function API — the HTTP layer is a thin adapter over it.
2. **Standard library only.** `http.server`, `sqlite3`, `json`, `csv`, `re`,
   `unittest`. Nothing else. Deployment is "unzip and run Python".
3. **Everything is evidence.** Processes, QA reports, SOP drafts, agent runs,
   approvals and configuration changes are all rows in the database, each
   paired with audit events.
4. **Human-controlled AI.** Agents execute plans; humans approve sensitive
   outcomes. The platform never performs a production action itself.

## Layer map

```
Browser dashboard (static/index.html)
        │  fetch JSON
        ▼
HTTP server (server.py)  ── route table, regex-matched, JSON in/out
        │
        ▼
Service modules (services/)
  processes.py    process register + CSA maturity scoring
  sop.py          SOP draft generator + evidence register
  qa.py           rule-driven campaign QA engine + rule CRUD
  segmentation.py audience/consent validation
  readiness.py    nine-point deployment gate
  roi.py          net-value ROI model
  adapters.py     mock CRM + Adobe Campaign dry-run stub
  agents.py       AGENT CATALOG · TOOL REGISTRY · orchestrator · approvals
        │
        ▼
Database (db.py)  SQLite · thread-safe · JSON-aware helpers · audit log
```

## Agent layer

- **Agent catalog** — five agents, each with a *fixed plan*: an ordered list
  of steps bound to named tools. Plans are code-reviewed artifacts, not
  improvised at runtime.
- **Tool registry** — tools are plain functions `(db, task, previous) -> dict`
  registered under explicit names. An agent can only call registered tools.
- **Orchestrator** — a persisted state machine. Runs move through
  `running → pending_approval → completed | failed | rejected`. Approval-gated
  steps pause the whole run until a named human approves.
- **Run ledger** — `agent_runs` + `agent_steps` + `approvals` tables give a
  complete, replayable execution history with inputs, outputs and timestamps.

### Approval flow

```
start_run ──► step 1 ──► step 2 ──► gated step (requires_approval)
                                          │
                            no approval ──┴── approval recorded
                                 │                │
                            run pauses        orchestrator resumes
                            (pending_approval) run completes; sign-off
                                               output names the approver
```

A rejection cancels the gated step and every remaining step, and marks the
run `rejected`. All decisions are audit-logged with the approver's name.

### AI provider

`LLMProvider` interface with a `DeterministicLLM` implementation
(template-driven, no network, no randomness). Selected via
`OPSFORGE_LLM_PROVIDER` (default `deterministic`). Future providers register
in the `PROVIDERS` dict — no other code changes.

## Integration adapters

External systems are reachable only through adapters registered in
`adapters.py`. v0.3 ships:

- `mock_crm` — deterministic synthetic CRM used for samples and tests.
- `adobe_campaign` — interface stub in permanent dry-run; live calls raise
  `AdapterError` by design until real, server-side configuration exists.

Connectivity checks persist status and write audit events; no external
network call is possible in v0.3.

## Data model (SQLite)

`processes`, `assessments`, `evidence`, `qa_rules`, `agent_runs`,
`agent_steps`, `approvals`, `adapters`, `audit_events`.

## Concurrency

`ThreadingHTTPServer` handles requests concurrently. `Database` wraps a
single connection behind an `RLock`; the orchestrator's run-context is
thread-local. All writes are short transactions committed immediately.
