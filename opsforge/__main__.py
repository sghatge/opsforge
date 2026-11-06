"""OPSFORGE — entry point.

Usage:
    python -m opsforge [--port 8765] [--db opsforge.db]
"""

from __future__ import annotations

import argparse

from . import APP_NAME, TAGLINE, __version__
from .db import Database
from .server import create_server


def main() -> None:
    parser = argparse.ArgumentParser(prog="opsforge", description=f"{APP_NAME} — {TAGLINE}")
    parser.add_argument("--port", type=int, default=8765, help="HTTP port (default 8765)")
    parser.add_argument("--db", default="opsforge.db", help="SQLite database file (default ./opsforge.db)")
    parser.add_argument("--demo", action="store_true",
                        help="Seed realistic demo data on first run (skipped if the database already has data)")
    args = parser.parse_args()

    db = Database(args.db)
    if args.demo:
        from .services.demo import seed_demo

        result = seed_demo(db)
        print("Demo data : " + ("seeded — open the dashboard and explore" if result["seeded"]
                                else "already present — skipped"))

    server = create_server(db, port=args.port)
    print(f"{APP_NAME} v{__version__} — {TAGLINE}")
    print(f"Database : {args.db}")
    print(f"Dashboard: http://127.0.0.1:{args.port}")
    print("Mode     : local MVP — all external integrations dry-run, human approval required")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()


if __name__ == "__main__":
    main()
