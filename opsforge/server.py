"""OPSFORGE — HTTP server and REST API.

Standard-library HTTP server (ThreadingHTTPServer). No framework, no
third-party dependencies. All production-impacting actions are gated behind
the human approval workflow exposed on agent runs.
"""

from __future__ import annotations

import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import __version__
from .db import Database
from .services import adapters as adapters_service
from .services import agents as agents_service
from .services import processes, qa as qa_service, readiness, roi, segmentation
from .services import demo as demo_service
from .services.sop import generate_sop, list_evidence

STATIC_DIR = Path(__file__).parent / "static"


class ApiError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


# ---------------------------------------------------------------------------
# route handlers — each returns (status, payload)
# ---------------------------------------------------------------------------
def health(db: Database, m, body) -> tuple[int, dict]:
    return 200, {
        "status": "ok",
        "app": "OPSFORGE",
        "version": __version__,
        "ai_provider": agents_service.get_provider().name,
        "mode": "local_mvp",
        "note": "Local MVP — not a production deployment. All external integrations run in dry-run mode.",
    }


def metrics(db: Database, m, body) -> tuple[int, dict]:
    def count(table: str, where: str = "1=1", params: tuple = ()) -> int:
        row = db.query_one(f"SELECT COUNT(*) AS n FROM {table} WHERE {where}", params)
        return int(row["n"]) if row else 0

    return 200, {
        "processes": count("processes"),
        "assessments": count("assessments"),
        "evidence_records": count("evidence"),
        "qa_rules": count("qa_rules"),
        "qa_rules_enabled": count("qa_rules", "enabled = 1"),
        "agent_runs": count("agent_runs"),
        "agent_runs_pending_approval": count("agent_runs", "status = 'pending_approval'"),
        "approvals": count("approvals"),
        "audit_events": count("audit_events"),
    }


def create_process(db: Database, m, body) -> tuple[int, dict]:
    return 201, processes.create_process(db, body)


def list_processes(db: Database, m, body) -> tuple[int, dict]:
    return 200, {"processes": processes.list_processes(db)}


def get_process(db: Database, m, body) -> tuple[int, dict]:
    return 200, processes.get_process(db, m.group(1))


def assess_process(db: Database, m, body) -> tuple[int, dict]:
    return 200, processes.assess_process(db, m.group(1), body)


def generate_sop_route(db: Database, m, body) -> tuple[int, dict]:
    return 200, generate_sop(db, body.get("process_id", ""))


def run_email_qa(db: Database, m, body) -> tuple[int, dict]:
    report = qa_service.run_email_qa(db, body.get("campaign") or body)
    if body.get("create_evidence"):
        from .services.sop import create_evidence

        create_evidence(db, {
            "kind": "qa_report",
            "title": f"QA report — {report['campaign']}",
            "payload": report,
        })
    return 200, report


def list_rules(db: Database, m, body) -> tuple[int, dict]:
    return 200, {"rules": qa_service.list_rules(db)}


def create_rule(db: Database, m, body) -> tuple[int, dict]:
    return 201, qa_service.create_rule(db, body)


def get_rule(db: Database, m, body) -> tuple[int, dict]:
    return 200, qa_service.get_rule(db, m.group(1))


def update_rule(db: Database, m, body) -> tuple[int, dict]:
    return 200, qa_service.update_rule(db, m.group(1), body)


def delete_rule(db: Database, m, body) -> tuple[int, dict]:
    return 200, qa_service.delete_rule(db, m.group(1))


def calculate_roi(db: Database, m, body) -> tuple[int, dict]:
    return 200, roi.calculate_roi(db, body)


def validate_segmentation(db: Database, m, body) -> tuple[int, dict]:
    return 200, segmentation.validate_segmentation(db, body)


def assess_deployment(db: Database, m, body) -> tuple[int, dict]:
    return 200, readiness.assess_deployment(db, body)


def list_evidence_route(db: Database, m, body) -> tuple[int, dict]:
    return 200, {"evidence": list_evidence(db)}


def create_evidence_route(db: Database, m, body) -> tuple[int, dict]:
    from .services.sop import create_evidence

    return 201, create_evidence(db, body)


def list_agents(db: Database, m, body) -> tuple[int, dict]:
    return 200, {"agents": agents_service.list_agents()}


def start_agent_run(db: Database, m, body) -> tuple[int, dict]:
    return 201, agents_service.start_run(db, m.group(1), body)


def list_runs(db: Database, m, body) -> tuple[int, dict]:
    agent_id = next((g for g in m.groups() if g), None)
    return 200, {"runs": agents_service.list_runs(db, agent_id)}


def get_run(db: Database, m, body) -> tuple[int, dict]:
    return 200, agents_service.get_run(db, m.group(1))


def approve_step(db: Database, m, body) -> tuple[int, dict]:
    run_id, seq = m.group(1), int(m.group(2))
    return 200, agents_service.approve_step(
        db, run_id, seq, body.get("approver", ""), body.get("comment", ""),
        body.get("override_reason", ""),
    )


def reject_step(db: Database, m, body) -> tuple[int, dict]:
    run_id, seq = m.group(1), int(m.group(2))
    return 200, agents_service.reject_step(
        db, run_id, seq, body.get("approver", ""), body.get("comment", "")
    )


def list_adapters(db: Database, m, body) -> tuple[int, dict]:
    return 200, {"adapters": adapters_service.list_adapters(db)}


def check_adapter(db: Database, m, body) -> tuple[int, dict]:
    return 200, adapters_service.check_adapter(db, m.group(1))


def audit_route(db: Database, m, body) -> tuple[int, dict]:
    return 200, {"events": db.audit_trail(limit=int(m.group(1) or 100))}


def seed_demo_route(db: Database, m, body) -> tuple[int, dict]:
    return 200, demo_service.seed_demo(db)


ROUTES: list[tuple[str, re.Pattern, object]] = [
    ("GET", re.compile(r"^/api/health$"), health),
    ("GET", re.compile(r"^/api/metrics$"), metrics),
    ("POST", re.compile(r"^/api/processes$"), create_process),
    ("GET", re.compile(r"^/api/processes$"), list_processes),
    ("GET", re.compile(r"^/api/processes/([\w-]+)$"), get_process),
    ("POST", re.compile(r"^/api/processes/([\w-]+)/assess$"), assess_process),
    ("POST", re.compile(r"^/api/sop/generate$"), generate_sop_route),
    ("POST", re.compile(r"^/api/qa/email$"), run_email_qa),
    ("GET", re.compile(r"^/api/qa/rules$"), list_rules),
    ("POST", re.compile(r"^/api/qa/rules$"), create_rule),
    ("GET", re.compile(r"^/api/qa/rules/([\w-]+)$"), get_rule),
    ("PUT", re.compile(r"^/api/qa/rules/([\w-]+)$"), update_rule),
    ("DELETE", re.compile(r"^/api/qa/rules/([\w-]+)$"), delete_rule),
    ("POST", re.compile(r"^/api/roi/calculate$"), calculate_roi),
    ("POST", re.compile(r"^/api/segmentation/validate$"), validate_segmentation),
    ("POST", re.compile(r"^/api/deployment/assess$"), assess_deployment),
    ("GET", re.compile(r"^/api/evidence$"), list_evidence_route),
    ("POST", re.compile(r"^/api/evidence$"), create_evidence_route),
    ("GET", re.compile(r"^/api/agents$"), list_agents),
    ("POST", re.compile(r"^/api/agents/([\w-]+)/run$"), start_agent_run),
    ("GET", re.compile(r"^/api/runs$"), list_runs),
    ("GET", re.compile(r"^/api/runs/([\w-]+)$"), get_run),
    ("POST", re.compile(r"^/api/runs/([\w-]+)/steps/(\d+)/approve$"), approve_step),
    ("POST", re.compile(r"^/api/runs/([\w-]+)/steps/(\d+)/reject$"), reject_step),
    ("GET", re.compile(r"^/api/adapters$"), list_adapters),
    ("POST", re.compile(r"^/api/adapters/([\w-]+)/check$"), check_adapter),
    ("GET", re.compile(r"^/api/audit(?:/(\d+))?$"), audit_route),
    ("POST", re.compile(r"^/api/demo/seed$"), seed_demo_route),
]


def make_handler(db: Database) -> type[BaseHTTPRequestHandler]:
    class OpsForgeHandler(BaseHTTPRequestHandler):
        server_version = f"OPSFORGE/{__version__}"

        def log_message(self, fmt: str, *args) -> None:  # quiet logs
            pass

        # -- helpers ------------------------------------------------------
        def _send_json(self, status: int, payload: dict) -> None:
            data = json.dumps(payload, default=str).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _dispatch(self, method: str) -> None:
            path = self.path.split("?")[0]
            if method == "GET" and path in ("/", "/index.html"):
                return self._serve_index()
            body: dict = {}
            if method in ("POST", "PUT", "DELETE"):
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length) if length else b""
                if raw:
                    try:
                        body = json.loads(raw)
                    except json.JSONDecodeError:
                        return self._send_json(400, {"error": "Request body must be valid JSON."})
            for route_method, pattern, handler in ROUTES:
                if route_method != method:
                    continue
                m = pattern.match(path)
                if m:
                    try:
                        status, payload = handler(db, m, body)
                        return self._send_json(status, payload)
                    except (ValueError, segmentation.csv.Error) as exc:
                        return self._send_json(400, {"error": str(exc)})
                    except LookupError as exc:
                        return self._send_json(404, {"error": str(exc)})
                    except Exception as exc:  # noqa: BLE001
                        return self._send_json(500, {"error": f"Internal error: {exc}"})
            return self._send_json(404, {"error": f"No route for {method} {path}"})

        def _serve_index(self) -> None:
            index = STATIC_DIR / "index.html"
            data = index.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:  # noqa: N802
            self._dispatch("GET")

        def do_POST(self) -> None:  # noqa: N802
            self._dispatch("POST")

        def do_PUT(self) -> None:  # noqa: N802
            self._dispatch("PUT")

        def do_DELETE(self) -> None:  # noqa: N802
            self._dispatch("DELETE")

    return OpsForgeHandler


def create_server(db: Database, host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    adapters_service.sync_registry(db)
    return ThreadingHTTPServer((host, port), make_handler(db))
