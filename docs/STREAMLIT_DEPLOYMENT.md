# OPSFORGE Streamlit showcase deployment

The Streamlit app in `streamlit_app.py` is a public-facing, synthetic-data showcase of the OPSFORGE operating model.

It is intentionally separate from:
- the existing local OPSFORGE Python application (port 8765 by default);
- Paperclip (agent orchestration at localhost:3100 by default).

The Streamlit showcase does **not** connect to Paperclip, execute agents, approve tasks, or access production data.

## Deploy on Streamlit Community Cloud

1. Sign in at https://share.streamlit.io/ using GitHub.
2. Authorize Streamlit to access the public repository `sghatge/opsforge`.
3. Select **Create app**.
4. Repository: `sghatge/opsforge`.
5. Branch: `main`.
6. Main file path: `streamlit_app.py`.
7. Choose an available app subdomain, for example `opsforge-command-centre`.
8. Click **Deploy** and review the build logs.

No secrets are required for this demo. Do not add OpenAI keys, Paperclip credentials, or other secrets to this public repository.

## Production architecture

Keep Paperclip on the local Windows machine for the initial trial. If remote access is later required, deploy Paperclip separately to a hardened VPS using authenticated mode, HTTPS, secure secret storage, backups, and network restrictions. Do not expose a local-trusted Paperclip instance to the public internet.

## Local preview

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run streamlit_app.py
```

The local Streamlit app normally opens at http://localhost:8501.


## Optional local signal-to-runtime connector

The Signal → Execution page can submit a selected signal to the existing local OPSFORGE agent API. This is intentionally limited to loopback HTTP and is intended only when both applications run on the same machine.

PowerShell (start the OPSFORGE API server in one terminal):
```powershell
python -m opsforge
```

In a second terminal, set the local connector and start Streamlit:
```powershell
$env:OPSFORGE_RUNTIME_URL = "http://127.0.0.1:8765"
streamlit run streamlit_app.py
```

The public Streamlit Community Cloud deployment must leave `OPSFORGE_RUNTIME_URL` unset. A cloud-hosted app cannot reach your private localhost runtime, and the connector rejects non-loopback targets. Do not expose the unauthenticated local API to the public internet.

Submitted signals use the existing `signal_triage_agent`, SQLite run ledger, evidence register, approval workflow and audit events. High-risk items pause for a named human. Approval does not execute an external action.

