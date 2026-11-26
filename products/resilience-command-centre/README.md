# OPSFORGE Resilience Command Centre

**Operational resilience intelligence for teams that cannot afford unplanned downtime.**

A Streamlit MVP that combines public provider-status signals, explainable vendor-dependency scoring, business-continuity checklist generation and an AI security exposure self-assessment.

## Run locally

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Deploy

Deploy this folder as the app root on Streamlit Community Cloud, selecting `streamlit_app.py` as the entrypoint. Add no secrets for the current public-data MVP.

## Modules

1. **Overview** — executive view of provider signals and vendor risk.
2. **Live Signals** — public status endpoints for AWS, Azure, Google Cloud, Cloudflare, GitHub, OpenAI, Atlassian and Stripe.
3. **Vendor Risk** — editable vendor register and weighted 0–100 risk score.
4. **Continuity Builder** — service-specific response checklist and Markdown export.
5. **AI Exposure** — self-assessment of data handling, agent permissions, approvals and AI incident readiness.
6. **Methodology** — transparent weights, assumptions and limitations.

## Scoring model

| Dimension | Weight |
|---|---:|
| Business criticality | 30% |
| Dependency concentration | 25% |
| Recovery readiness gap | 20% |
| Security exposure | 15% |
| Incident exposure | 10% |

Risk bands: Low 0–29, Moderate 30–49, High 50–69, Critical 70–100.

## Data and safety boundaries

- Provider feeds are external signals, not proof of customer impact or internal system health.
- A failed feed is shown as **Unknown**, never silently treated as healthy.
- Vendor examples are synthetic and held in Streamlit session state.
- The AI exposure assessment is self-reported; it is not a penetration test or certification.
- Generated continuity checklists require business-owner review and validation against tested plans.
- No customer credentials or production data are required.

## Current limitations

- Azure feed connectivity is surfaced but its RSS incidents are not yet parsed into a normalized incident model.
- CISA KEV is linked as a trusted reference; automated enrichment is planned for the next iteration.
- No persistent database, authentication, notifications, scheduled polling or tenant isolation yet.
- Public provider endpoints may change, rate-limit or return incomplete information.

## Roadmap

- **0.1** — Streamlit command centre, public provider checks, vendor scoring, continuity builder, AI self-assessment.
- **0.2** — normalized RSS / KEV ingestion, incident history, SQLite persistence, configurable vendor catalogue.
- **0.3** — notification rules, evidence register, PDF reports, customer workspaces and access controls.
- **1.0** — authenticated multi-tenant service with tested data governance and operational controls.

Built by Sangram Ghatge as an OPSFORGE product experiment.
