"""OPSFORGE Signal-to-Execution workspace.

Free-tier, read-only signal intake with deterministic triage and a human
decision ledger. No external actions are executed by this module.
"""
from __future__ import annotations

import csv
import hashlib
import html
import io
import re
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import streamlit as st

FEEDS = {
    "Adobe Status": "https://status.adobe.com/",
    "Adobe Blog": "https://blog.adobe.com/en/topics/experience-cloud",
    "Google Workspace Updates": "https://workspaceupdates.googleblog.com/feeds/posts/default",
    "GitHub Blog": "https://github.blog/feed/",
}
# RSS/Atom endpoints are deliberately kept separate from the display labels.
FEED_URLS = {
    "Google Workspace Updates": "https://workspaceupdates.googleblog.com/feeds/posts/default",
    "GitHub Blog": "https://github.blog/feed/",
    "Microsoft 365 Blog": "https://www.microsoft.com/en-us/microsoft-365/blog/feed/",
}
KEYWORD_WEIGHTS = {
    "adobe campaign": 5, "campaign classic": 5, "crm": 2,
    "marketing automation": 3, "deliverability": 4, "email": 1,
    "sftp": 4, "security": 3, "vulnerability": 5, "incident": 4,
    "outage": 4, "service disruption": 5, "capacity": 3,
    "sla": 4, "salesforce": 2, "journey orchestration": 3,
    "streamlit": 1, "github": 1, "agent": 2, "governance": 3,
}
APPROVAL_TERMS = ("outage", "service disruption", "vulnerability", "security incident",
                  "sftp", "sla breach", "data exposure", "production failure")
AUTONOMOUS_TERMS = ("release notes", "product update", "new feature", "webinar",
                    "event", "research", "tutorial")


def _clean(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value or "")
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def _entry_date(entry: ET.Element):
    for tag in ("published", "updated", "pubDate", "date"):
        node = entry.find(".//{*}" + tag)
        if node is not None and node.text:
            try:
                dt = parsedate_to_datetime(node.text) if tag == "pubDate" else datetime.fromisoformat(node.text.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc)
            except (ValueError, TypeError, OverflowError):
                pass
    return None


def _parse_feed(source: str, url: str, hours: int = 168):
    request = urllib.request.Request(url, headers={"User-Agent": "OPSFORGE-Signal-Demo/1.0"})
    with urllib.request.urlopen(request, timeout=8) as response:
        payload = response.read(1_500_000)
    root = ET.fromstring(payload)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    rows = []
    for entry in root.findall(".//item") + root.findall(".//{*}entry"):
        title = _clean((entry.findtext("title") or "Untitled signal"))
        summary = _clean(entry.findtext("description") or entry.findtext("{*}summary") or entry.findtext("{*}content") or "")
        link_node = entry.find("link")
        link = (link_node.text or "").strip() if link_node is not None and link_node.text else ""
        if not link and link_node is not None:
            link = link_node.attrib.get("href", "")
        published = _entry_date(entry)
        if published and published < cutoff:
            continue
        combined = (title + " " + summary).lower()
        score = sum(weight for term, weight in KEYWORD_WEIGHTS.items() if term in combined)
        if score <= 0:
            continue
        rows.append({
            "id": hashlib.sha256((source + title + link).encode("utf-8")).hexdigest()[:16],
            "headline": title[:240], "summary": summary[:700], "source": source,
            "url": link, "published": published.isoformat() if published else "",
            "score": score, "classification": classify_signal(combined),
        })
    return rows


def classify_signal(text: str) -> str:
    value = (text or "").lower()
    if any(term in value for term in APPROVAL_TERMS):
        return "Approve"
    if any(term in value for term in AUTONOMOUS_TERMS):
        return "Autonomous"
    return "Notify"


def route_agent(text: str) -> str:
    value = (text or "").lower()
    if any(term in value for term in ("capacity", "workload", "sla")):
        return "Workload & SLA Analyst"
    if any(term in value for term in ("adobe campaign", "campaign classic", "deliverability", "email")):
        return "CRM & Campaign Operations Analyst"
    if any(term in value for term in ("security", "vulnerability", "sftp", "incident", "outage")):
        return "Risk & Incident Analyst"
    if any(term in value for term in ("salesforce", "journey orchestration")):
        return "Journey & MarTech Analyst"
    return "Research & Intelligence Analyst"


def suggested_action(classification: str, agent: str) -> str:
    if classification == "Autonomous":
        return "Prepare a source-linked summary and update the signal register. No external action."
    if classification == "Approve":
        return "Assess operational impact, collect evidence, draft a mitigation runbook and request named human approval."
    return f"{agent}: assess relevance, identify affected workflows and recommend a next step."


@st.cache_data(ttl=1800, show_spinner=False)
def load_signals(hours: int = 168):
    all_rows, errors = [], []
    for source, url in FEED_URLS.items():
        try:
            all_rows.extend(_parse_feed(source, url, hours))
        except (urllib.error.URLError, TimeoutError, ET.ParseError, ValueError, OSError) as exc:
            errors.append(f"{source}: {type(exc).__name__}")
    # De-duplicate by stable ID and sort by weighted relevance.
    unique = {row["id"]: row for row in all_rows}
    return sorted(unique.values(), key=lambda row: (row["score"], row["published"]), reverse=True), errors


def render_signal_pipeline():
    st.subheader("Signal → Idea → Governed decision")
    st.caption("Free RSS intake · deterministic triage · human decision record · no production execution")
    st.info("Safety boundary: this workspace never sends messages, changes campaigns, connects to SFTP, deploys code or executes CRM actions.")

    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Signal sources", str(len(FEED_URLS)))
    col_b.metric("Decision classes", "3")
    col_c.metric("External actions", "0")

    with st.sidebar:
        st.markdown("### Signal controls")
        lookback = st.selectbox("Look-back window", [24, 72, 168, 336], index=2, format_func=lambda h: f"{h} hours")
        min_score = st.slider("Minimum relevance score", 1, 12, 1)
        if st.button("Refresh signals", use_container_width=True):
            load_signals.clear()

    with st.spinner("Reading public RSS feeds…"):
        signals, errors = load_signals(lookback)
    signals = [item for item in signals if item["score"] >= min_score]

    if "opsforge_signal_decisions" not in st.session_state:
        st.session_state.opsforge_signal_decisions = []

    decisions = st.session_state.opsforge_signal_decisions
    approved_ids = {d["signal_id"] for d in decisions if d["decision"] == "Approved"}
    rejected_ids = {d["signal_id"] for d in decisions if d["decision"] == "Rejected"}

    counts = {
        "Autonomous": sum(x["classification"] == "Autonomous" for x in signals),
        "Notify": sum(x["classification"] == "Notify" for x in signals),
        "Approve": sum(x["classification"] == "Approve" for x in signals),
    }
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Relevant signals", len(signals))
    m2.metric("Autonomous", counts["Autonomous"])
    m3.metric("Notify", counts["Notify"])
    m4.metric("Approval required", counts["Approve"])

    if errors:
        with st.expander(f"Feed diagnostics ({len(errors)})"):
            for error in errors:
                st.caption(error)
    if not signals:
        st.warning("No matching signals were returned by the configured feeds. Try a longer look-back window or lower the relevance threshold.")
    else:
        st.markdown("### Layer 1 · Signal intake")
        for item in signals:
            agent = route_agent(item["headline"] + " " + item["summary"])
            decision_state = "Approved" if item["id"] in approved_ids else ("Rejected" if item["id"] in rejected_ids else "Pending")
            with st.expander(f"{item['classification']} · {item['headline']} · relevance {item['score']}"):
                st.write(item["summary"] or "No summary supplied by source.")
                st.caption(f"Source: {item['source']} · Agent route: {agent} · Decision: {decision_state}")
                if item["url"].startswith("https://"):
                    st.link_button("Open original source", item["url"])
                st.markdown("**Layer 2 · Proposed idea**")
                st.write(suggested_action(item["classification"], agent))
                st.markdown("**Layer 3 · Governance decision**")
                if item["classification"] == "Approve":
                    st.warning("Human approval required. This is a decision record only; it does not execute the proposed action.")
                elif item["classification"] == "Autonomous":
                    st.success("Low-risk information processing may be prepared automatically. External actions remain disabled.")
                else:
                    st.info("Notify: surface the finding and wait for an operator's next instruction.")

                if decision_state == "Pending":
                    with st.form(f"decision_{item['id']}"):
                        reviewer = st.text_input("Reviewer name", key=f"reviewer_{item['id']}")
                        reason = st.text_area("Decision note / rationale", key=f"reason_{item['id']}", max_chars=500)
                        left, right = st.columns(2)
                        approve = left.form_submit_button("Record approval", disabled=(item["classification"] == "Approve" and not reviewer.strip()))
                        reject = right.form_submit_button("Reject signal")
                    if approve or reject:
                        if not reviewer.strip():
                            st.error("Enter a reviewer name before recording a decision.")
                        else:
                            decisions.append({
                                "signal_id": item["id"], "headline": item["headline"],
                                "classification": item["classification"],
                                "decision": "Approved" if approve else "Rejected",
                                "reviewer": reviewer.strip(), "reason": reason.strip(),
                                "recorded_at": datetime.now(timezone.utc).isoformat(),
                            })
                            st.session_state.opsforge_signal_decisions = decisions
                            st.rerun()

    st.divider()
    st.markdown("### Decision ledger")
    st.caption("The public Streamlit demo stores decisions in the current session only. Download the CSV before ending the session; durable multi-user audit storage belongs in the secured local OPSFORGE runtime.")
    if decisions:
        csv_buffer = io.StringIO()
        writer = csv.DictWriter(csv_buffer, fieldnames=list(decisions[0].keys()))
        writer.writeheader()
        writer.writerows(decisions)
        st.download_button("Download decision ledger (CSV)", csv_buffer.getvalue(), "opsforge_signal_decisions.csv", "text/csv")
        st.dataframe(decisions, use_container_width=True, hide_index=True)
    else:
        st.caption("No decisions recorded in this session.")

    st.markdown("### Operating rules")
    st.markdown("""
- **Autonomous:** permitted for reversible, information-only preparation; no external side effects.
- **Notify:** provide evidence and recommendations; an operator decides what happens next.
- **Approve:** pause for a named human reviewer and written rationale before any future execution integration.
- **Fail closed:** unavailable feeds, ambiguous classification or missing evidence never authorise an action.
""")
