from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import requests
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="OPSFORGE | Resilience", page_icon="🛡️", layout="wide")

# OPSFORGE design system: dark operational canvas, high-contrast status, explicit human decisions.
st.markdown("""
<style>
:root { color-scheme: dark; }
.stApp { background: #0b1020; color: #e7edf7; }
[data-testid="stSidebar"] { background: #10182b; border-right: 1px solid #26344e; }
.block-container { padding-top: 1.4rem; max-width: 1500px; }
h1,h2,h3 { letter-spacing: -0.035em; }
.metric-card { background: linear-gradient(145deg,#151f35,#10182a); border:1px solid #293955;
 border-radius:14px; padding:16px 18px; min-height:112px; }
.metric-label { color:#91a4c2; font-size:12px; text-transform:uppercase; letter-spacing:.1em; }
.metric-value { color:#f4f7fb; font-size:30px; font-weight:750; margin-top:6px; }
.metric-note { color:#8ea0ba; font-size:12px; margin-top:3px; }
.panel { background:#111a2d; border:1px solid #293955; border-radius:14px; padding:16px; }
.small-muted { color:#91a4c2; font-size:12px; }
.status-dot { display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:7px; }
[data-testid="stDataFrame"] { border:1px solid #293955; border-radius:10px; }
.stButton>button { border-radius:9px; font-weight:650; }
</style>
""", unsafe_allow_html=True)

PROVIDERS = [
    {"name":"Amazon Web Services","url":"https://status.aws.amazon.com/data.json","kind":"AWS"},
    {"name":"Microsoft Azure","url":"https://azure.status.microsoft/en-us/status/feed/","kind":"RSS"},
    {"name":"Google Cloud","url":"https://status.cloud.google.com/incidents.json","kind":"Google"},
    {"name":"Cloudflare","url":"https://www.cloudflarestatus.com/api/v2/summary.json","kind":"Statuspage"},
    {"name":"GitHub","url":"https://www.githubstatus.com/api/v2/summary.json","kind":"Statuspage"},
    {"name":"OpenAI","url":"https://status.openai.com/api/v2/summary.json","kind":"Statuspage"},
    {"name":"Atlassian","url":"https://status.atlassian.com/api/v2/summary.json","kind":"Statuspage"},
    {"name":"Stripe","url":"https://status.stripe.com/api/v2/summary.json","kind":"Statuspage"},
]

KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"

def get_json(url: str, timeout: int = 8) -> Any:
    response = requests.get(url, timeout=timeout, headers={"User-Agent":"OPSFORGE-Resilience/0.1"})
    response.raise_for_status()
    return response.json()

def provider_status(provider: dict) -> dict:
    name, url, kind = provider["name"], provider["url"], provider["kind"]
    try:
        if kind == "Statuspage":
            payload = get_json(url)
            indicator = payload.get("status", {}).get("indicator", "unknown")
            description = payload.get("status", {}).get("description", "No status description")
            incidents = payload.get("incidents", []) or []
            return {"Provider":name,"Status":indicator.title(),"Description":description,
                    "Active incidents":len(incidents),"Updated":payload.get("page",{}).get("updated_at",""),
                    "Source":url,"Available":True}
        if kind == "Google":
            payload = get_json(url)
            active = [x for x in payload if x.get("end") is None]
            return {"Provider":name,"Status":"Investigating" if active else "Operational",
                    "Description":(active[0].get("summary","Active incident") if active else "No active incidents"),
                    "Active incidents":len(active),"Updated":datetime.now(timezone.utc).isoformat(),
                    "Source":url,"Available":True}
        if kind == "AWS":
            payload = get_json(url)
            events = payload.get("current", []) if isinstance(payload,dict) else []
            return {"Provider":name,"Status":"Review feed" if events else "No current events",
                    "Description":f"{len(events)} current event records returned",
                    "Active incidents":len(events),"Updated":datetime.now(timezone.utc).isoformat(),
                    "Source":url,"Available":True}
        # Azure RSS is deliberately labelled as feed connectivity, not inferred service health.
        response = requests.get(url, timeout=8, headers={"User-Agent":"OPSFORGE-Resilience/0.1"})
        response.raise_for_status()
        return {"Provider":name,"Status":"Feed reachable","Description":"RSS feed reachable; parse incidents in a future connector release",
                "Active incidents":0,"Updated":datetime.now(timezone.utc).isoformat(),
                "Source":url,"Available":True}
    except Exception as exc:
        return {"Provider":name,"Status":"Unknown","Description":str(exc)[:160],
                "Active incidents":0,"Updated":"","Source":url,"Available":False}

def score_vendor(criticality: int, concentration: int, recovery: int, security: int, incident: int) -> int:
    # Inputs are 0–100 exposure values. Weights sum to 100%.
    return round(criticality*.30 + concentration*.25 + recovery*.20 + security*.15 + incident*.10)

def band(score: int) -> str:
    if score >= 70: return "CRITICAL"
    if score >= 50: return "HIGH"
    if score >= 30: return "MODERATE"
    return "LOW"

def continuity_actions(category: str, severity: str, rto: str) -> list[str]:
    common = [
        "Declare the incident owner and open a timestamped incident record.",
        "Confirm scope, affected business services, customer impact and current evidence.",
        "Use the provider's official status page and internal monitoring to validate impact.",
        "Notify the business owner and communications lead using the approved contact tree.",
        "Record decisions, timestamps, evidence links and customer-impact estimates.",
    ]
    by_type = {
        "Cloud / infrastructure":[
            "Check regional health, DNS, network, identity and dependent cloud services.",
            "Activate the documented alternate region or approved recovery environment if tested.",
            "Pause non-essential deployments and preserve logs, snapshots and configuration state.",
        ],
        "Payments":[
            "Switch to the pre-approved secondary payment route only after reconciliation checks.",
            "Queue retry-safe transactions; prevent duplicate captures and reconcile settlement.",
            "Publish customer messaging through the approved status and support channels.",
        ],
        "CRM / SaaS":[
            "Activate the approved manual or offline process for time-critical customer operations.",
            "Export or use the last verified permitted data snapshot; do not bypass access controls.",
            "Reconcile queued updates before resuming integrations and campaign execution.",
        ],
        "AI provider":[
            "Disable affected AI workflow integrations if data handling or output integrity is uncertain.",
            "Switch to an approved fallback model or manual review process.",
            "Review prompts, data disclosures, tool permissions and any downstream actions taken.",
        ],
    }
    recovery = [
        f"Target recovery time: {rto}. Confirm the business owner accepts any variance.",
        "Validate service restoration with a business transaction, not provider status alone.",
        "Reconcile backlogs, verify data integrity and obtain business-owner sign-off.",
        "Complete a blameless post-incident review and update the continuity playbook.",
    ]
    return common + by_type.get(category,[]) + recovery

def card(label: str, value: str, note: str = "") -> None:
    st.markdown(f'<div class="metric-card"><div class="metric-label">{label}</div><div class="metric-value">{value}</div><div class="metric-note">{note}</div></div>', unsafe_allow_html=True)

if "vendors" not in st.session_state:
    st.session_state.vendors = [
        {"Vendor":"AWS","Service":"Cloud hosting","Criticality":90,"Concentration":70,"Recovery gap":45,"Security exposure":25,"Incident exposure":35},
        {"Vendor":"Microsoft 365","Service":"Identity and productivity","Criticality":85,"Concentration":80,"Recovery gap":55,"Security exposure":35,"Incident exposure":25},
        {"Vendor":"Stripe","Service":"Payments","Criticality":95,"Concentration":65,"Recovery gap":40,"Security exposure":30,"Incident exposure":20},
        {"Vendor":"OpenAI","Service":"AI assistant / API","Criticality":55,"Concentration":35,"Recovery gap":60,"Security exposure":70,"Incident exposure":20},
    ]

st.sidebar.markdown("## 🛡️ OPSFORGE")
st.sidebar.caption("RESILIENCE COMMAND CENTRE · MVP 0.1")
page = st.sidebar.radio("COMMAND NAVIGATION",["Overview","Live Signals","Vendor Risk","Continuity Builder","AI Exposure","Methodology"])
st.sidebar.divider()
st.sidebar.caption("DATA POLICY")
st.sidebar.markdown("Public provider feeds. Synthetic sample vendor data. No customer credentials.")
st.sidebar.caption("Last UI refresh: " + datetime.now().astimezone().strftime("%d %b %Y · %H:%M %Z"))
st.title("OPSFORGE / RESILIENCE")
st.caption("Operational resilience intelligence for teams that cannot afford unplanned downtime.")
left,right = st.columns([3,1])
with left: st.markdown("**CONTROL ROOM**  /  LIVE SIGNALS · DEPENDENCY EXPOSURE · RECOVERY READINESS")
with right: st.caption("BUILD 0.1.0  ·  PUBLIC DATA")

if page in ("Overview","Live Signals"):
    st.subheader("External service health")
    if st.button("↻ Refresh provider signals", type="primary"):
        st.cache_data.clear()
    @st.cache_data(ttl=180, show_spinner=False)
    def load_status():
        return [provider_status(p) for p in PROVIDERS]
    with st.spinner("Checking public provider feeds…"):
        statuses = load_status()
    df_status = pd.DataFrame(statuses)
    active = int(df_status["Active incidents"].fillna(0).sum())
    unknown = int((df_status["Status"]=="Unknown").sum())
    operational = int((df_status["Status"]=="Operational").sum())
    a,b,c,d = st.columns(4)
    with a: card("PROVIDERS MONITORED",str(len(statuses)),"Public endpoints configured")
    with b: card("ACTIVE INCIDENT RECORDS",str(active),"Provider-reported records; not customer impact")
    with c: card("UNKNOWN FEEDS",str(unknown),"Connectivity or parsing unavailable")
    with d: card("OPERATIONAL",str(operational),"Explicit provider operational status")
    st.dataframe(df_status[["Provider","Status","Description","Active incidents","Available"]],
                 use_container_width=True, hide_index=True)
    st.caption("Provider status is an external signal only. Confirm customer impact using your own telemetry and provider communications.")
    if page == "Live Signals":
        st.subheader("Source register")
        st.dataframe(df_status[["Provider","Source","Updated"]],use_container_width=True,hide_index=True)
        st.markdown("[CISA Known Exploited Vulnerabilities catalogue](https://www.cisa.gov/known-exploited-vulnerabilities-catalog)")

if page in ("Overview","Vendor Risk"):
    if page == "Vendor Risk": st.subheader("Vendor dependency risk register")
    vendors = pd.DataFrame(st.session_state.vendors)
    vendors["Risk score"] = vendors.apply(lambda r: score_vendor(r["Criticality"],r["Concentration"],r["Recovery gap"],r["Security exposure"],r["Incident exposure"]),axis=1)
    vendors["Risk band"] = vendors["Risk score"].apply(band)
    if page == "Overview":
        st.subheader("Dependency exposure")
        x,y = st.columns(2)
        with x: card("VENDORS IN REGISTER",str(len(vendors)),"Includes editable synthetic examples")
        with y: card("HIGH / CRITICAL",str(int(vendors["Risk band"].isin(["HIGH","CRITICAL"]).sum())),"Prioritise mitigation and recovery tests")
    st.dataframe(vendors[["Vendor","Service","Risk score","Risk band"]].sort_values("Risk score",ascending=False),
                 use_container_width=True,hide_index=True)
    fig = px.bar(vendors.sort_values("Risk score"),x="Risk score",y="Vendor",color="Risk band",orientation="h",
                 range_x=[0,100],title="Explainable vendor risk score")
    fig.update_layout(paper_bgcolor="#0b1020",plot_bgcolor="#0b1020",font_color="#e7edf7",margin=dict(l=10,r=10,t=45,b=10))
    st.plotly_chart(fig,use_container_width=True)
    with st.expander("＋ Add or assess a vendor"):
        with st.form("vendor_form"):
            name = st.text_input("Vendor name")
            service = st.text_input("Business service")
            c1,c2 = st.columns(2)
            criticality = c1.slider("Business criticality",0,100,70)
            concentration = c2.slider("Dependency concentration",0,100,50)
            recovery = c1.slider("Recovery readiness gap",0,100,40)
            security = c2.slider("Security exposure",0,100,35)
            incident = c1.slider("Incident exposure",0,100,20)
            submitted = st.form_submit_button("Add vendor to register",type="primary")
        if submitted:
            if not name.strip(): st.error("Enter a vendor name.")
            else:
                st.session_state.vendors.append({"Vendor":name.strip(),"Service":service.strip() or "Unspecified",
                    "Criticality":criticality,"Concentration":concentration,"Recovery gap":recovery,
                    "Security exposure":security,"Incident exposure":incident})
                st.success("Vendor added. Risk score recalculated.")
                st.rerun()
    st.download_button("Download vendor risk register (CSV)",vendors.to_csv(index=False).encode("utf-8"),
                       "opsforge_vendor_risk_register.csv","text/csv")

if page == "Continuity Builder":
    st.subheader("Business continuity playbook generator")
    st.write("Generate an actionable first-response checklist. Assign owners and validate against your approved continuity plan before use.")
    with st.form("continuity_form"):
        category = st.selectbox("Affected service category",["Cloud / infrastructure","Payments","CRM / SaaS","AI provider"])
        severity = st.select_slider("Incident severity",options=["SEV-4","SEV-3","SEV-2","SEV-1"],value="SEV-2")
        rto = st.selectbox("Recovery time objective",["1 hour","4 hours","8 hours","24 hours","72 hours"])
        owner = st.text_input("Incident owner / role",placeholder="e.g. IT Operations Lead")
        service_name = st.text_input("Affected business service",placeholder="e.g. Online checkout")
        generate = st.form_submit_button("Generate continuity checklist",type="primary")
    if generate:
        st.session_state.continuity = {"category":category,"severity":severity,"rto":rto,"owner":owner or "Unassigned","service":service_name or "Unspecified",
                                        "actions":continuity_actions(category,severity,rto)}
    if "continuity" in st.session_state:
        p = st.session_state.continuity
        st.markdown(f"### {p['severity']} · {p['service']}")
        st.caption(f"Category: {p['category']}  |  Incident owner: {p['owner']}  |  RTO: {p['rto']}")
        checklist = "\n".join([f"- [ ] {x}" for x in p["actions"]])
        st.markdown(checklist)
        st.download_button("Download checklist (Markdown)",checklist.encode("utf-8"),"continuity-checklist.md","text/markdown")
        st.warning("This is a starter checklist, not a substitute for a tested, organisation-approved business continuity or disaster recovery plan.")

if page == "AI Exposure":
    st.subheader("AI security exposure assessment")
    st.write("A lightweight self-assessment of governance and operational controls. It is not a penetration test or security certification.")
    with st.form("ai_assessment"):
        questions = [
            ("Sensitive data entered into public AI tools without an approved policy?", "data"),
            ("AI tools or agents have broad access to business systems or files?", "access"),
            ("AI-generated actions can execute without human approval?", "actions"),
            ("No inventory exists for third-party AI providers and subprocessors?", "inventory"),
            ("No documented process exists for AI incident response or vendor exit?", "response"),
            ("Employees lack recurring AI phishing and prompt-injection awareness?", "awareness"),
        ]
        answers = {}
        for question,key in questions:
            answers[key] = st.radio(question,["No / controlled","Partially / inconsistent","Yes / unknown"],horizontal=True,key="q_"+key)
        assess = st.form_submit_button("Calculate exposure",type="primary")
    if assess:
        points = {"No / controlled":0,"Partially / inconsistent":10,"Yes / unknown":20}
        score = sum(points[v] for v in answers.values())
        st.session_state.ai_result = {"score":score,"answers":answers}
    if "ai_result" in st.session_state:
        result = st.session_state.ai_result
        score = result["score"]
        st.metric("AI exposure score",f"{score}/120")
        st.progress(score/120)
        st.markdown(f"**Exposure band: {('LOW' if score < 30 else 'MODERATE' if score < 60 else 'HIGH' if score < 90 else 'CRITICAL')}**")
        recs = []
        if result["answers"]["data"] != "No / controlled": recs.append("Publish an approved-use policy and prohibit entry of restricted data into unapproved AI tools.")
        if result["answers"]["access"] != "No / controlled": recs.append("Apply least privilege, scoped credentials, tool allowlists and periodic access reviews.")
        if result["answers"]["actions"] != "No / controlled": recs.append("Require named human approval for external, financial, destructive or customer-impacting agent actions.")
        if result["answers"]["inventory"] != "No / controlled": recs.append("Maintain an AI provider, model, data-flow and subprocessor inventory.")
        if result["answers"]["response"] != "No / controlled": recs.append("Document AI incident escalation, kill-switch, evidence retention and vendor exit procedures.")
        if result["answers"]["awareness"] != "No / controlled": recs.append("Train staff to identify AI-enabled impersonation, phishing and prompt-injection attempts.")
        for item in recs: st.markdown("- "+item)
        if not recs: st.success("All assessed controls were marked controlled. Validate with evidence and periodic testing.")

if page == "Methodology":
    st.subheader("Scoring methodology and operating boundaries")
    st.markdown("""
**Vendor risk score (0–100)**

| Dimension | Weight | Meaning |
|---|---:|---|
| Business criticality | 30% | Impact if the service is unavailable |
| Dependency concentration | 25% | Reliance on one provider or failure domain |
| Recovery readiness gap | 20% | Weakness in tested recovery capability |
| Security exposure | 15% | Known control and access weaknesses |
| Incident exposure | 10% | Relevant incident history / exposure |

Higher inputs increase risk. The score is a prioritisation aid, not an actuarial probability or compliance rating.

**Data and safety boundaries**
- Provider status is sourced from public endpoints and may be delayed, incomplete or unavailable.
- Feed failure is labelled Unknown; it is never silently treated as healthy.
- The sample vendor register is synthetic and stored in the Streamlit session.
- No credentials, customer data, personal data or production telemetry are collected.
- Continuity checklists require owner review and validation against tested procedures.
- AI exposure results are self-reported and do not establish that a system is secure.
""")
    st.markdown("[CISA Known Exploited Vulnerabilities](https://www.cisa.gov/known-exploited-vulnerabilities-catalog) · [Atlassian Statuspage API](https://developer.statuspage.io/) · [Streamlit documentation](https://docs.streamlit.io/)")

st.divider()
st.caption("OPSFORGE RESILIENCE · 0.1.0 · Public-feed intelligence + explainable rules + human-owned decisions.")
