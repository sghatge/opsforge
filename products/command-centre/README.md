# OPSFORGE Command Centre — authenticated local operator UI

This app is the private operator-facing client for the four specialist-agent API
in sghatge/acc-agent-gate. It is separate from the public synthetic-data
showcase at the root of this repository.

## Architecture

- Command Centre: this Streamlit UI; submits JSON tasks to the agent API.
- Agent API: authenticated, role-aware API in sghatge/acc-agent-gate.
- Enforcement: ACC Agent Gate remains authoritative for Campaign tool policy,
  approvals, execution permits, replay protection and audit evidence.
- Agents: Research, Adobe Campaign QA, CRM Operations and Marketing Analytics.
- Production boundary: agent API routes are advisory-only. No live Campaign,
  Salesforce, CRM-write, email or deployment action is exposed.

## Run locally

Start the API from a clone of sghatge/acc-agent-gate. Generate a token:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Set that value as OPSFORGE_API_TOKEN in the API process, then run:

```bash
python -m opsforge.api
```

In a separate terminal, from the root of this sghatge/opsforge repository:

```bash
python -m pip install streamlit
# PowerShell
$env:OPSFORGE_AGENT_API_URL = "http://127.0.0.1:8765"
$env:OPSFORGE_API_TOKEN = "<same-generated-token>"
streamlit run products/command-centre/streamlit_app.py --server.address 127.0.0.1
```

The UI defaults to loopback API access. Set OPSFORGE_AGENT_API_URL to override
the API URL. The token is read from OPSFORGE_API_TOKEN or entered into the
password field; it is not written to browser storage or source files.

## Remote deployment

Do not expose this app publicly with a shared operator token. Remote deployment
requires verified user identity, per-user API credentials, TLS, exact CORS
allow-listing, rate limiting, persistent audit storage and a security review.
Prefer local loopback operation until those controls exist.

## Tests

From the repository root:

```bash
python -m unittest tests.test_agent_api_client -v
```
