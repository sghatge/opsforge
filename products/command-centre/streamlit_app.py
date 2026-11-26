"""Private/local OPSFORGE Command Centre for the authenticated specialist-agent API."""
from __future__ import annotations
import json
import os
import sys
from pathlib import Path
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from opsforge.agent_api_client import AGENTS, AgentAPIClient, AgentAPIError

st.set_page_config(page_title="OPSFORGE | Command Centre", page_icon="🛡️", layout="wide")
st.markdown("""
<style>
.stApp{background:#0b1020;color:#e7edf7}
[data-testid="stSidebar"]{background:#10182b;border-right:1px solid #26344e}
.block-container{max-width:1400px;padding-top:1.5rem}
.hero{padding:1.2rem 1.4rem;border:1px solid #293955;border-radius:16px;background:linear-gradient(120deg,#14243b,#10182a)}
.muted{color:#9aacc5}
</style>
""", unsafe_allow_html=True)
st.markdown('<div class="hero"><div class="muted">OPSFORGE · GOVERNED AGENT OPERATIONS</div><h1>Command Centre</h1><p class="muted">One operator workspace. Four specialist agents. Authenticated, advisory-only execution.</p></div>', unsafe_allow_html=True)
st.warning("Advisory-only API. This UI cannot send campaigns, write to production CRM, issue permits, approve requests or deploy software.")

with st.sidebar:
    st.subheader("Connection")
    api_url = st.text_input("Agent API URL", value=os.getenv("OPSFORGE_AGENT_API_URL", "http://127.0.0.1:8765"))
    token = st.text_input("Bearer token", value=os.getenv("OPSFORGE_API_TOKEN", ""), type="password")
    st.caption("Token remains in session memory; never commit it.")
    if st.button("Check API health", use_container_width=True):
        try:
            health = AgentAPIClient(api_url).health()
            st.success("API: " + str(health.get("status", "unknown")))
            st.json(health)
        except AgentAPIError as exc:
            st.error(str(exc))

labels = {
    "research": "01 · Research Agent",
    "adobe_campaign_qa": "02 · Adobe Campaign QA Agent",
    "crm_operations": "03 · CRM Operations Agent",
    "marketing_analytics": "04 · Marketing Analytics Agent",
}
agent = st.selectbox("Specialist agent", list(AGENTS), format_func=labels.get)
samples = {
    "research": {"question": "Assess the supplied operational question using only provided sources.", "sources": []},
    "adobe_campaign_qa": {"delivery": {"subject": "Synthetic QA sample", "body": "Legal entity Example Ltd. UnsubscriptionLink", "consent_filter": True, "proof_sent": True, "seed_list": ["seed@example.test"], "typology": "TY_MARKETING", "scheduled_local": "2026-11-27 10:00"}},
    "crm_operations": {"objective": "Recommend controls for a synthetic CRM operations workflow.", "context": {"platform": "Adobe Campaign Classic", "environment": "synthetic"}},
    "marketing_analytics": {"period": "Synthetic sample", "campaigns": [{"name": "Sample launch", "sends": 10000, "delivered": 9800, "opens": 4900, "clicks": 980, "conversions": 98, "bounces": 200, "revenue": 250000}]},
}
left, right = st.columns([1.15, 1])
with left:
    st.subheader("Task input")
    task_text = st.text_area("JSON task", value=json.dumps(samples[agent], indent=2), height=340, key="task_" + agent)
    run = st.button("Run selected agent", type="primary", use_container_width=True)
with right:
    st.subheader("Operating boundaries")
    st.markdown("""
- Research: analysis of supplied sources.
- Campaign QA: deterministic checks; eligible for human review is not send approval.
- CRM Operations: recommendations only.
- Marketing Analytics: deterministic calculations; narrative is not evidence.
""")
    st.info("ACC Agent Gate remains the separate enforcement authority for Campaign tool actions.")
    st.caption("No external side effect is reachable from this dashboard.")

if run:
    try:
        task = json.loads(task_text)
        if not isinstance(task, dict):
            raise AgentAPIError("Task JSON must be an object.")
        with st.spinner("Running advisory agent…"):
            result = AgentAPIClient(api_url, token).run_agent(agent, task)
    except json.JSONDecodeError:
        st.error("Invalid JSON. Correct the task before running.")
    except AgentAPIError as exc:
        st.error(str(exc))
    else:
        st.session_state["opsforge_last_result"] = result
        st.session_state["opsforge_last_agent"] = agent
        st.success("Agent request completed. No production action was executed.")

if st.session_state.get("opsforge_last_result") is not None:
    st.divider()
    st.subheader("Latest result · " + labels.get(st.session_state.get("opsforge_last_agent"), "Agent"))
    st.caption("Execution scope: advisory only")
    st.json(st.session_state["opsforge_last_result"])
