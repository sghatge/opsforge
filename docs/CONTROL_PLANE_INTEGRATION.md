# OPSFORGE Control Plane Integration

**Status:** implementation branch; authenticated local agent client added.
**Scope:** advisory-only operations; no production connector.

## Target architecture

```
Operator
   |
   v
OPSFORGE Command Centre (private Streamlit UI)
   |  bearer-authenticated JSON over loopback / HTTPS
   v
ACC Agent Gate — authenticated OPSFORGE Agent API
   |-- Research Agent
   |-- Adobe Campaign QA Agent
   |-- CRM Operations Agent
   '-- Marketing Analytics Agent

Campaign tool requests (separate governed path):
Agent / operator -> ACC Agent Gate policy engine -> allow / allow_masked /
dry_run / needs_approval / block -> human approval -> signed permit ->
synthetic executor -> hash-chained audit
```

## System ownership

| Concern | Authoritative component |
|---|---|
| Operator workspace | sghatge/opsforge/products/command-centre |
| Agent registration and advisory execution | sghatge/acc-agent-gate/opsforge/agents |
| Authenticated agent API | sghatge/acc-agent-gate/opsforge/api.py |
| Campaign tool policy | sghatge/acc-agent-gate/policy/default.yaml |
| Campaign approval ledger | sghatge/acc-agent-gate/acc_agent_gate/approval_store.py |
| Signed execution authorization | sghatge/acc-agent-gate/acc_agent_gate/execution_authorizer.py |
| Tamper-evident Campaign audit | sghatge/acc-agent-gate/acc_agent_gate/audit.py |
| Local run ledger and evidence workflows | sghatge/opsforge/opsforge/db.py and opsforge/services/agents.py |

## Separation of responsibilities

The four specialist-agent API endpoints are advisory-only. They do not send
campaigns, mutate CRM, publish assets or deploy software. A successful agent
response is not authorization for a separate production action.

The Campaign Gate policy engine is the enforcement authority for Campaign
tool calls. The public Streamlit showcase remains synthetic-only. The new
operator UI is a separate local app and must not be deployed publicly with a
shared bearer token.

## Client safeguards

- Only four named agent routes are accepted.
- Unknown agent names fail locally before a network request.
- Requests must be JSON objects and are limited to 64 KiB.
- Remote API origins must use HTTPS; plain HTTP is allowed only for loopback.
- Bearer token must be at least 32 characters and is never written to files.
- API failures are surfaced without exposing request headers or token values.
- The UI exposes no campaign send, approval, permit, CRM-write or deployment call.
- ACC Agent Gate continues to own YAML policy, dual approval, permit binding,
  replay protection and audit verification.

## Local validation

From the opsforge repository root:

```bash
python -m unittest tests.test_agent_api_client -v
```

In the acc-agent-gate repository:

```bash
python -m pytest -q tests/test_opsforge_api.py tests/test_opsforge_agents.py
```

## Release gates

1. Local tests pass.
2. API health returns the expected four-agent allow-list.
3. Each role can invoke only its authorized agents.
4. Synthetic test payloads return advisory-only outputs.
5. No production connector or external side effect is reachable from this UI.
6. Remote deployment remains blocked until verified user identity, TLS,
   rate limiting, durable audit retention and security/privacy review are complete.
