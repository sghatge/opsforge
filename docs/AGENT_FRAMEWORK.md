# OPSFORGE Agent Framework (v0.3)

How the agent layer works, what it guarantees, and how to extend it.

## Design contract

Every agent in OPSFORGE follows three rules:

1. **Declared plans.** An agent is a catalog entry with an ordered list of
   steps. Each step names exactly one tool. If it isn't in the plan, the
   agent cannot do it.
2. **Named tools.** Tools are registered functions
   `(db, task, previous_output) -> dict`. The output of step *n* is handed to
   step *n+1*, so chains compose without hidden state.
3. **Human gates.** Steps with `requires_approval: true` are never executed
   by the agent alone. The run pauses in `pending_approval` until a named
   human approves or rejects. There is no self-approval path — enforced in
   `approve_step()` and verified by tests.

## Registered agents

| Agent | Plan | Gated step |
| --- | --- | --- |
| `qa_agent` | run QA → file evidence → **QA sign-off** | yes |
| `sop_agent` | generate SOP → file evidence | — |
| `segmentation_agent` | validate audience → file evidence | — |
| `readiness_agent` | assess readiness → file evidence → **release sign-off** | yes |
| `reporting_agent` | collect metrics → compose summary → file report | — |

## Run lifecycle

```
running ──► pending_approval ──► completed
   │               │                ▲
   │               └── approve ─────┘
   │               └── reject ──► rejected (remaining steps cancelled)
   └── tool error ──► failed (error recorded on the step)
```

The orchestrator is a *persisted* state machine: a paused run survives
server restarts (state lives in SQLite) and resumes from the exact step.

## Adding a new agent (checklist)

1. Add a plan entry to `AGENT_CATALOG` in `services/agents.py`.
2. Implement the tool function(s) and register them in `TOOLS`.
3. If any step is production-impacting, mark it `requires_approval: True`.
4. Optionally add a `_sample_task()` entry so the dashboard can demo it.
5. Add tests: happy path, gate pause, approve, reject.

## Plugging in a real LLM

The provider interface is deliberately narrow:

```python
class LLMProvider:
    name = "base"
    def compose(self, instruction: str, context: dict) -> str: ...
```

Register an implementation in `PROVIDERS` and select it with
`OPSFORGE_LLM_PROVIDER=<name>`. The shipped `DeterministicLLM` makes no
network calls and is fully reproducible — suitable for demos, tests and
audited environments.

Guidance for a real provider (v0.4+):
- Key management belongs in server configuration, **never** in code or DB.
- Every provider call should be audited (`audit_event`) with inputs/outputs.
- Agent plans must not grow unbounded: compose returns text; execution still
  goes through registered tools only.

## Security posture (honest statement)

- No credentials are read, stored or transmitted in v0.3.
- All external integrations are dry-run; live calls raise `AdapterError`.
- Approval requires a name, not an identity — authentication is v0.5 work.
- Do not expose the server beyond `127.0.0.1` in its current form.
