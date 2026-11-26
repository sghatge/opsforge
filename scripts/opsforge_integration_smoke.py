#!/usr/bin/env python3
"""Four-mission OPSFORGE ↔ ACC Agent Gate API integration smoke test.

Uses synthetic payloads only. No Gemini, production CRM, Adobe Campaign,
email, workflow, deployment, or external write action is invoked.

Run:
  OPSFORGE_AGENT_API_URL=http://127.0.0.1:8765 \
  OPSFORGE_API_TOKEN=<operator-token> \
  python scripts/opsforge_integration_smoke.py
"""
from __future__ import annotations

import os
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from opsforge.agent_api_client import AgentAPIClient, AgentAPIError


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def verify_unauthenticated_request_is_rejected(base_url: str) -> None:
    request = Request(
        base_url + "/api/agents/research/run",
        data=b'{"question":"synthetic auth probe","sources":["fixture"]}',
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=10) as response:
            status = response.status
    except HTTPError as exc:
        status = exc.code
        exc.read()
    require(status == 401, f"Unauthenticated request expected HTTP 401; received {status}.")


def main() -> int:
    base_url = os.getenv("OPSFORGE_AGENT_API_URL", "http://127.0.0.1:8765")
    token = os.getenv("OPSFORGE_API_TOKEN", "")
    if len(token) < 32:
        print("BLOCKED: set OPSFORGE_API_TOKEN (minimum 32 characters).", file=sys.stderr)
        return 2

    try:
        client = AgentAPIClient(base_url, token=token, timeout=10)
        health = client.health()
        require(health.get("status") == "healthy", "API health status is not healthy.")
        require(health.get("execution_scope") == "advisory_only", "API is not marked advisory_only.")
        expected_agents = {
            "research", "adobe_campaign_qa", "crm_operations", "marketing_analytics"
        }
        require(expected_agents.issubset(set(health.get("agents", []))),
                "Health response does not advertise all four missions.")
        print("PASS  API health + four-mission registry")

        verify_unauthenticated_request_is_rejected(client.base_url)
        print("PASS  unauthenticated request rejected (HTTP 401)")

        research = client.run_agent("research", {
            "question": "Validate the purpose of a campaign QA checklist.",
            "sources": ["synthetic://qa-checklist-fixture"],
            "use_gemini": False,
        })
        require(research.get("authorization", {}).get("role") == "operator",
                "Research response did not identify the operator role.")
        require(research.get("execution_scope") == "advisory_only",
                "Research response escaped advisory-only scope.")
        require(research.get("result", {}).get("source_count") == 1,
                "Research agent did not validate the synthetic source.")
        print("PASS  M01 Research")

        qa = client.run_agent("adobe_campaign_qa", {
            "delivery": {
                "id": "OPSFORGE_SYNTHETIC_QA_001",
                "internal_name": "OPSFORGE_SYNTHETIC_QA_001",
                "market": "HR",
                "label": "Synthetic QA fixture",
                "subject": "Synthetic campaign preview",
                "preheader": "Synthetic preheader",
                "body": "<p>1.234,00 €</p><footer>Legal entity HR</footer>"
                        "<a href='#'>UnsubscriptionLink</a>",
                "target_count": 1000,
                "scheduled_local": "2026-12-01 10:00",
                "typology": "TY_MARKETING_EU",
                "proof_sent": True,
                "seed_list": True,
                "consent_filter": True,
            },
            "use_gemini": False,
        })
        qa_result = qa.get("result", {})
        require(qa.get("execution_scope") == "advisory_only",
                "Campaign QA response escaped advisory-only scope.")
        require(qa_result.get("blockers") == [], "Synthetic clean QA fixture has blockers.")
        require(qa_result.get("send_recommendation") == "eligible_for_human_review",
                "QA must stop at human review; it must never approve or send.")
        print("PASS  M02 Adobe Campaign QA (human review only; no send)")

        crm = client.run_agent("crm_operations", {
            "objective": "Reduce pre-send campaign QA defects.",
            "context": {"platform": "synthetic", "markets": ["HR", "SI"]},
            "constraints": ["No production access", "No CRM writes"],
            "use_gemini": False,
        })
        crm_result = crm.get("result", {})
        require(crm.get("execution_scope") == "advisory_only",
                "CRM Operations response escaped advisory-only scope.")
        require(crm_result.get("status") == "draft",
                "CRM Operations should validate an advisory draft without Gemini.")
        print("PASS  M03 CRM Operations (advisory only)")

        analytics = client.run_agent("marketing_analytics", {
            "period": "Synthetic integration fixture",
            "campaigns": [{
                "name": "Synthetic Launch",
                "sends": 10000,
                "delivered": 9800,
                "opens": 4900,
                "clicks": 980,
                "conversions": 98,
                "bounces": 200,
                "revenue": 250000,
            }],
            "use_gemini": False,
        })
        analytics_result = analytics.get("result", {})
        require(analytics.get("execution_scope") == "advisory_only",
                "Marketing Analytics response escaped advisory-only scope.")
        require(analytics_result.get("overall", {}).get("delivery_rate_pct") == 98.0,
                "Deterministic delivery-rate calculation did not match 98.0%.")
        print("PASS  M04 Marketing Analytics (deterministic KPI)")

        print("\nFULL STOP: 6 integration checks passed. Synthetic data only.")
        print("No production Adobe Campaign, CRM, email, or workflow action was executed.")
        return 0
    except (AgentAPIError, AssertionError, OSError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
