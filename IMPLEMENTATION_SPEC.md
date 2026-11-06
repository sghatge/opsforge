# OPSFORGE — API Reference (v0.3)

All endpoints accept and return JSON. Errors: `400` validation,
`404` unknown resource, `500` internal.

## Platform

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Status, version, active AI provider |
| GET | `/api/metrics` | Record counts incl. runs awaiting approval |
| GET | `/api/audit` | Audit event trail (most recent first) |

## Operations intelligence

| Method | Path | Purpose |
| --- | --- | --- |
| GET / POST | `/api/processes` | List / register processes |
| GET | `/api/processes/{id}` | Process detail |
| POST | `/api/processes/{id}/assess` | CSA scoring, 5 dimensions × 1–5 |
| POST | `/api/sop/generate` | SOP draft from `process_id` |

## Quality & campaigns

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/qa/email` | Run all enabled QA rules on a campaign payload; `create_evidence: true` files a QA report |
| GET / POST | `/api/qa/rules` | List / create QA rules |
| GET / PUT / DELETE | `/api/qa/rules/{id}` | Inspect / update / delete a rule |
| POST | `/api/segmentation/validate` | Audience CSV validation (`csv`, optional `volume_cap`) |
| POST | `/api/deployment/assess` | Nine-point readiness gate |
| POST | `/api/roi/calculate` | Net-value ROI model |
| GET / POST | `/api/evidence` | Evidence register |

## Agent layer (new in v0.3)

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/agents` | Agent catalog with plans and approval gates |
| POST | `/api/agents/{agent_id}/run` | Start a run. Body: task object, or `{"use_sample": true}` |
| GET | `/api/runs` | Run ledger (compact view) |
| GET | `/api/runs/{id}` | Full run detail: steps, outputs, approvals |
| POST | `/api/runs/{id}/steps/{seq}/approve` | Approve a gated step. Requires `approver` (a named human) |
| POST | `/api/runs/{id}/steps/{seq}/reject` | Reject — cancels the step and the run |

Run statuses: `running`, `pending_approval`, `completed`, `failed`, `rejected`.
Step statuses: `pending`, `pending_approval`, `running`, `done`, `failed`, `cancelled`.

## Adapters

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/adapters` | Registered adapters, modes and last check |
| POST | `/api/adapters/{name}/check` | Connectivity check (dry-run only in v0.3) |

## Example: full approval round trip

```bash
# 1. start a QA agent run with the built-in sample
RUN=$(curl -s -X POST localhost:8765/api/agents/qa_agent/run \
     -H 'Content-Type: application/json' -d '{"use_sample": true}')
# → status: pending_approval (the sign-off step is gated)

# 2. a named human approves
curl -s -X POST localhost:8765/api/runs/<run_id>/steps/3/approve \
     -H 'Content-Type: application/json' \
     -d '{"approver": "Sangram", "comment": "accepted"}'
# → run completes; sign-off output records the approver
```
