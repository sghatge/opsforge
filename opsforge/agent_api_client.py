"""Fail-closed client for the authenticated OPSFORGE advisory-agent API."""
from __future__ import annotations
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

AGENTS = frozenset({"research", "crm_operations", "adobe_campaign_qa", "marketing_analytics"})
MAX_BYTES = 64 * 1024

class AgentAPIError(RuntimeError):
    pass

def _normalise_url(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AgentAPIError("API URL is required.")
    parsed = urlsplit(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise AgentAPIError("API URL must be an absolute HTTP(S) URL.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise AgentAPIError("API URL cannot contain credentials, query parameters or fragments.")
    if parsed.scheme == "http" and parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise AgentAPIError("Plain HTTP is allowed only for loopback development.")
    return value.strip().rstrip("/")

class AgentAPIClient:
    def __init__(self, base_url: str, token: str | None = None, timeout: float = 10.0):
        self.base_url = _normalise_url(base_url)
        self.token = token or ""
        self.timeout = timeout

    def health(self) -> dict[str, Any]:
        return self._send(Request(self.base_url + "/health", headers={"Accept": "application/json"}))

    def run_agent(self, agent: str, task: dict[str, Any]) -> dict[str, Any]:
        if agent not in AGENTS:
            raise AgentAPIError("Unknown agent. Request not sent.")
        if not isinstance(task, dict):
            raise AgentAPIError("Task must be a JSON object.")
        if len(self.token) < 32:
            raise AgentAPIError("A bearer token of at least 32 characters is required.")
        body = json.dumps(task, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if len(body) > MAX_BYTES:
            raise AgentAPIError("Task exceeds the 64 KiB request limit.")
        req = Request(
            self.base_url + "/api/agents/" + agent + "/run",
            data=body,
            headers={"Authorization": "Bearer " + self.token,
                     "Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        return self._send(req)

    def _send(self, request: Request) -> dict[str, Any]:
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read(MAX_BYTES + 1)
                if len(raw) > MAX_BYTES:
                    raise AgentAPIError("API response exceeded the 64 KiB client limit.")
        except HTTPError as exc:
            raise AgentAPIError("OPSFORGE API returned HTTP " + str(exc.code) + ".") from None
        except (URLError, TimeoutError, OSError):
            raise AgentAPIError("OPSFORGE API is unreachable. Check the service and URL.") from None
        try:
            result = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise AgentAPIError("OPSFORGE API returned invalid JSON.") from None
        if not isinstance(result, dict):
            raise AgentAPIError("OPSFORGE API returned an unexpected response shape.")
        return result
