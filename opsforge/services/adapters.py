"""OPSFORGE — integration adapters.

Enterprise integrations are isolated behind explicit adapters. Two ship with
v0.3:

* ``mock_crm``        — deterministic synthetic CRM (safe for demos/tests).
* ``adobe_campaign``  — interface stub in permanent dry-run mode until real
  credentials are supplied through configuration (never hard-coded).

No adapter can reach an external system in v0.3. Connectivity checks record
evidence but never transmit data.
"""

from __future__ import annotations

import json

from ..db import Database, now


class AdapterError(Exception):
    pass


class BaseAdapter:
    name = "base"
    kind = "generic"
    mode = "dry_run"
    capabilities: tuple = ()

    def check_connection(self) -> dict:
        return {
            "adapter": self.name,
            "mode": self.mode,
            "status": "dry_run_ok",
            "checked_at": now(),
            "note": "No external calls made in dry-run mode.",
        }


class MockCRMAdapter(BaseAdapter):
    name = "mock_crm"
    kind = "crm"
    mode = "mock"
    capabilities = ("list_campaigns", "get_campaign")

    def list_campaigns(self) -> list[dict]:
        return [
            {"id": "CMP-1001", "name": "Autumn Newsletter", "channel": "email"},
            {"id": "CMP-1002", "name": "Winback Series", "channel": "email"},
        ]

    def get_campaign(self, campaign_id: str) -> dict:
        sample = {
            "CMP-1001": {
                "name": "Autumn Newsletter",
                "subject": "Your autumn update from the team",
                "html": "<html><head><title>Autumn</title></head><body>Hello <% FirstName %>, <a href='https://example.com/unsubscribe'>unsubscribe</a></body></html>",
                "urls": ["https://example.com/offer", "https://example.com/unsubscribe"],
                "personalization": "<% FirstName %>",
                "tracking": True,
                "consent": True,
            },
            "CMP-1002": {
                "name": "Winback Series — bad sample",
                "subject": "ACT NOW free!!!",
                "html": "<html><body>Hello <% FirstName <a href='ftp://bad'>x</a></body></html>",
                "urls": ["https://example.com/offer", "not-a-url"],
                "personalization": "<% FirstName",
                "tracking": False,
                "consent": True,
            },
        }
        if campaign_id not in sample:
            raise AdapterError(f"Campaign {campaign_id} not found in mock CRM.")
        return sample[campaign_id]


class AdobeCampaignAdapter(BaseAdapter):
    name = "adobe_campaign"
    kind = "crm"
    mode = "dry_run"
    capabilities = ("check_connection",)

    def check_connection(self) -> dict:
        return {
            "adapter": self.name,
            "mode": self.mode,
            "status": "dry_run_ok",
            "checked_at": now(),
            "note": (
                "Interface verified in dry-run. Live Adobe Campaign V7/V8 connectivity "
                "requires server configuration and is intentionally not enabled in v0.3."
            ),
        }

    def require_live(self) -> None:
        raise AdapterError("Adobe Campaign live calls are disabled in v0.3 (dry-run only).")


REGISTRY: dict[str, BaseAdapter] = {
    a.name: a for a in (MockCRMAdapter(), AdobeCampaignAdapter())
}


def sync_registry(db: Database) -> None:
    for adapter in REGISTRY.values():
        existing = db.query_one("SELECT name FROM adapters WHERE name = ?", (adapter.name,))
        if existing is None:
            db.execute(
                "INSERT INTO adapters (name, kind, mode, capabilities, status, last_check)"
                " VALUES (?, ?, ?, ?, 'unverified', '')",
                (adapter.name, adapter.kind, adapter.mode, json.dumps(list(adapter.capabilities))),
            )


def list_adapters(db: Database) -> list[dict]:
    sync_registry(db)
    rows = db.query("SELECT * FROM adapters ORDER BY name")
    for r in rows:
        r["capabilities"] = json.loads(r["capabilities"])
    return rows


def check_adapter(db: Database, name: str) -> dict:
    sync_registry(db)
    adapter = REGISTRY.get(name)
    if adapter is None:
        raise LookupError(f"Adapter '{name}' is not registered.")
    result = adapter.check_connection()
    db.execute(
        "UPDATE adapters SET status = ?, last_check = ? WHERE name = ?",
        (result["status"], str(result["checked_at"]), name),
    )
    db.audit("adapter.checked", {"adapter": name, "status": result["status"]})
    return result
