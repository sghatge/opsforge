"""OPSFORGE public Streamlit showcase.

This is a synthetic-data demonstration of the OPSFORGE operating model.
It does not connect to Paperclip or execute agents.
"""
from datetime import datetime, timezone
import streamlit as st

st.set_page_config(page_title="OPSFORGE | AI Operations Command Centre", page_icon="🛡️", layout="wide", initial_sidebar_state="expanded")
HERO_IMAGE = "https://thumbs.wbm.im/pw/medium/c7251a6cb58068b11a9cf1163e793a48.jpg"

st.markdown("""
<style>
.block-container {padding-top:1.5rem;padding-bottom:3rem;max-width:1440px}
.hero {padding:1.6rem 1.8rem;border:1px solid rgba(128,128,128,.25);border-radius:18px;background:linear-gradient(120deg,rgba(24,86,75,.24),rgba(35,52,82,.20))}
.kicker {font-size:.78rem;letter-spacing:.16em;font-weight:700;opacity:.75}
.hero h1 {font-size:2.6rem;margin:.35rem 0}
.muted {opacity:.72}
.pill {display:inline-block;border:1px solid rgba(128,128,128,.4);border-radius:999px;padding:.2rem .65rem;font-size:.78rem;margin-right:.35rem}
.visual-card {border:1px solid rgba(128,128,128,.25);border-radius:16px;padding:1rem;background:rgba(80,100,120,.07);height:100%}
.visual-icon {font-size:2rem;line-height:1.4}
section[data-testid="stSidebar"] {border-right:1px solid rgba(128,128,128,.18)}
</style>
""", unsafe_allow_html=True)

st.sidebar.markdown("## 🛡️ OPSFORGE")
st.sidebar.caption("Autonomous AI Operations Company")
page = st.sidebar.radio("Workspace", ["Command Centre", "Agent Organisation", "Governance & Approvals", "30-Day Roadmap", "Deployment Notes"])
st.sidebar.divider()
st.sidebar.caption("SHOWCASE ENVIRONMENT")
st.sidebar.info("Synthetic demo data · No live agents · No production integrations")

hero_left, hero_right = st.columns([1.35, 1], vertical_alignment="center")
with hero_left:
    st.markdown("""
    <div class="hero">
    <div class="kicker">AI OPERATIONS · HUMAN-CONTROLLED AUTONOMY</div>
    <h1>OPSFORGE Command Centre</h1>
    <p class="muted">AI does the checking. Humans make the call.</p>
    <span class="pill">Governed agents</span><span class="pill">Approval-first workflows</span><span class="pill">Auditable operations</span>
    </div>
    """, unsafe_allow_html=True)
with hero_right:
    st.image(HERO_IMAGE, use_container_width=True)
    st.caption("Illustrative AI operations visual · Image credit: PikWizard")

if page == "Command Centre":
    st.subheader("Operating overview")
    st.caption("Illustrative indicators for the public demo. These are not live system measurements.")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Registered agent roles", "6")
    c2.metric("Governance gates", "5")
    c3.metric("Production actions", "0")
    c4.metric("Live Paperclip connection", "Not connected")
    st.divider()
    st.markdown("### The OPSFORGE operating model")
    v1, v2, v3 = st.columns(3)
    with v1:
        st.markdown('<div class="visual-card"><div class="visual-icon">🧠</div><b>Plan & orchestrate</b><p class="muted">Specialist agents analyse work, plan tasks and coordinate within defined boundaries.</p></div>', unsafe_allow_html=True)
    with v2:
        st.markdown('<div class="visual-card"><div class="visual-icon">🛡️</div><b>Govern & approve</b><p class="muted">Policy gates, least-privilege permissions and human approvals protect sensitive actions.</p></div>', unsafe_allow_html=True)
    with v3:
        st.markdown('<div class="visual-card"><div class="visual-icon">📊</div><b>Measure & improve</b><p class="muted">Evidence, quality metrics and cost reviews create a continuous improvement loop.</p></div>', unsafe_allow_html=True)
    st.divider()
    left, right = st.columns([1.35, 1])
    with left:
        st.markdown("### Operating principles")
        st.markdown("""
- **Bounded autonomy:** agents receive explicit responsibilities and tool permissions.
- **Human approval:** sensitive or irreversible actions pause for a named approver.
- **Fail-closed governance:** failed checks cannot silently become successful outcomes.
- **Evidence and auditability:** decisions, reasons and outputs should be traceable.
""")
        st.markdown("### Initial business domains")
        st.write("CRM operations · Adobe Campaign v7/v8 · Marketing automation · Enterprise AI · QA and release governance")
    with right:
        st.markdown("### Control posture")
        st.progress(1.0, text="Public showcase contains no production credentials")
        st.progress(1.0, text="Synthetic demonstration data only")
        st.progress(1.0, text="No external actions are enabled")
        st.warning("This Streamlit app is a portfolio/demo interface, not the Paperclip execution server.")

elif page == "Agent Organisation":
    st.subheader("Proposed agent organisation")
    st.caption("Roles are a proposed operating model. They are not active agents.")
    st.image(HERO_IMAGE, caption="Illustrative agent orchestration and monitoring visual · Image credit: PikWizard", use_container_width=True)
    agents = [
        ("🧭 CEO / Chief of Staff", "Strategy, planning, delegation and reporting", "Founder approval required"),
        ("🧩 CRM & MarTech Architect", "Adobe Campaign, Salesforce and journey architecture", "Proposed"),
        ("⚙️ AI Engineering Lead", "Agent development, APIs and workflow automation", "Proposed"),
        ("🛡️ QA & Governance Lead", "Testing, policy checks and release readiness", "Proposed"),
        ("🔎 Research & Intelligence Lead", "Evidence gathering, synthesis and documentation", "Proposed"),
        ("📈 Operations Analyst", "KPIs, capacity, ROI and operating reviews", "Proposed"),
    ]
    for name, remit, status in agents:
        with st.container(border=True):
            a, b = st.columns([1, 2])
            a.markdown(f"**{name}**")
            a.caption(status)
            b.write(remit)
    st.info("Create and activate agents inside your secured Paperclip instance. Do not treat this public showcase as an agent control plane.")

elif page == "Governance & Approvals":
    st.subheader("Human-in-the-loop governance")
    st.markdown('<div class="visual-card"><div class="visual-icon">🔐 &nbsp; 🧑‍⚖️ &nbsp; 📋</div><b>Policy → Human review → Auditable decision</b><p class="muted">Sensitive actions pause until an authorised person approves them.</p></div>', unsafe_allow_html=True)
    st.write("The following controls define the intended OPSFORGE approval policy.")
    controls = [
        ("Credential or secret access", "Deny by default; use managed secrets and least privilege."),
        ("Production deployment", "Require named human approval and verified rollback plan."),
        ("External communication", "Require human review before sending or publishing."),
        ("Budget expansion", "Require founder approval before increasing agent or company limits."),
        ("Failed QA override", "Require written justification and a separate audit event."),
        ("Customer or personal data", "Use synthetic data in the demo; production data requires security and privacy review."),
    ]
    for title, desc in controls:
        with st.expander(title, expanded=True):
            st.write(desc)
    st.error("No approval buttons here are connected to a live execution system. This page documents policy only.")

elif page == "30-Day Roadmap":
    st.subheader("Foundation roadmap")
    st.markdown('<div class="visual-card"><div class="visual-icon">🚀 &nbsp; 🧱 &nbsp; 🧪 &nbsp; 📈</div><b>Establish → Organise → Pilot → Validate</b><p class="muted">A controlled 30-day path from local setup to a measured test workflow.</p></div>', unsafe_allow_html=True)
    roadmap = [
        ("Days 1–3", "Environment and security baseline", "Local Paperclip + Codex setup, secrets hygiene, loopback-only access."),
        ("Days 4–7", "CEO operating model", "Company charter, agent roles, budgets and approval policy."),
        ("Days 8–14", "First specialist agents", "Add engineering and QA roles only after founder approval."),
        ("Days 15–21", "First controlled project", "Build one test-only workflow with acceptance criteria and audit evidence."),
        ("Days 22–30", "Governance and review", "Evaluate quality, costs, failure modes and next-stage investment."),
    ]
    for period, title, detail in roadmap:
        with st.container(border=True):
            st.markdown(f"**{period} · {title}**")
            st.write(detail)

elif page == "Deployment Notes":
    st.subheader("Deployment architecture")
    st.markdown('<div class="visual-card"><div class="visual-icon">🌐 GitHub &nbsp; → &nbsp; 🖥️ Streamlit &nbsp; | &nbsp; 🔒 Paperclip + Codex</div><b>Separate presentation from execution</b><p class="muted">The public showcase displays the operating model; the secured Paperclip runtime handles agent execution.</p></div>', unsafe_allow_html=True)
    st.markdown("""
| Component | Intended responsibility | Hosting |
|---|---|---|
| GitHub repository | Source code, policies, tests and documentation | GitHub |
| Streamlit showcase | Public, synthetic-data portfolio interface | Streamlit Community Cloud |
| Paperclip | Agent orchestration, tasks, approvals and runtime | Local Windows machine initially; secured VPS for remote access |
| OpenAI Codex | Agent execution harness | Configured within Paperclip |
""")
    st.warning("Paperclip is not hosted by this Streamlit app. A Paperclip instance exposed beyond localhost must use authenticated mode, HTTPS, secure secrets, backups and a hardened server.")
    st.markdown("**Local Paperclip URL:** http://localhost:3100 (only on the machine where Paperclip is running).")
    st.markdown("**Local OPSFORGE Python app:** the existing repository's native server remains separate from this Streamlit showcase.")
    st.markdown("**Deployment steps:** connect this GitHub repository to Streamlit Community Cloud, select branch main, and set the app file to streamlit_app.py.")

st.divider()
st.caption(f"OPSFORGE · Public showcase · Updated {datetime.now(timezone.utc).strftime('%Y-%m-%d')} UTC · Synthetic data only")
