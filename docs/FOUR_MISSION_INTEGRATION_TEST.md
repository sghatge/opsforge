# Four-mission integration smoke test

This test validates the actual HTTP boundary between the OPSFORGE Command
Centre client and the authenticated advisory-agent API in
[sghatge/acc-agent-gate](https://github.com/sghatge/acc-agent-gate).

## Coverage

1. Public health endpoint advertises all four agents and `advisory_only` scope.
2. Unauthenticated agent request is rejected with HTTP 401.
3. M01 Research validates a synthetic source reference.
4. M02 Adobe Campaign QA accepts a clean synthetic delivery but stops at
   `eligible_for_human_review`; it cannot approve or send.
5. M03 CRM Operations returns an advisory draft only.
6. M04 Marketing Analytics returns deterministic KPIs (fixture delivery rate:
   98.0%).

The test disables Gemini and uses synthetic data. It does not connect to
Adobe Campaign, Salesforce, production CRM, email, SFTP, or deployment tools.

## Run locally

Start the API from a clone of
[sghatge/acc-agent-gate](https://github.com/sghatge/acc-agent-gate), using its
[API runbook](https://github.com/sghatge/acc-agent-gate/blob/main/docs/opsforge-api.md).
Configure a local operator token of at least 32 characters.

In a second terminal, from the OPSFORGE repository root:

```powershell
$env:OPSFORGE_AGENT_API_URL = "http://127.0.0.1:8765"
$env:OPSFORGE_API_TOKEN = Read-Host "OPSFORGE API token"
python scripts/opsforge_integration_smoke.py
Remove-Item Env:OPSFORGE_API_TOKEN
```

Expected terminal conclusion:

```
FULL STOP: 6 integration checks passed. Synthetic data only.
```

The test exits non-zero on any failed check. It never prints or stores the
bearer token. For a hosted API, use its HTTPS origin and inject the token
through a protected environment variable; never commit credentials.

## Acceptance boundary

A successful run proves the four synthetic API journeys and the tested
authentication/advisory response contract. It does not prove enterprise SSO,
production data residency, immutable audit retention, or production-system
connectivity. Those remain separate release gates.
