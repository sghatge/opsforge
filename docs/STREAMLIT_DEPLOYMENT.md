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
