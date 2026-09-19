#!/usr/bin/env python3
"""Pin the score-canary job set -> data/canary_jobs.json.

Run once. Re-run only to deliberately re-pin — changing the set resets the
comparison, since a different set of jobs is a different measurement.

Jobs are identified by (title, company), not job_id, so the same file resolves
in local SQLite and production Postgres.

Usage:
    railway run --service Postgres ./venv/bin/python scripts/build_canary_set.py --dry-run
    railway run --service Postgres ./venv/bin/python scripts/build_canary_set.py
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.matching.canary import CANARY_SET_PATH, DEFAULT_SET_SIZE, select_canary_jobs

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("build_canary_set")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", type=int, default=DEFAULT_SET_SIZE)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--local", action="store_true")
    ap.add_argument("--force", action="store_true",
                    help="overwrite an existing set (resets the baseline series)")
    args = ap.parse_args()

    if args.local:
        os.environ.setdefault("DATABASE_URL", "sqlite:///linkedin_job_matcher.db")
    elif os.environ.get("DATABASE_PUBLIC_URL"):
        os.environ["DATABASE_URL"] = os.environ["DATABASE_PUBLIC_URL"]

    if CANARY_SET_PATH.exists() and not args.force and not args.dry_run:
        raise SystemExit(
            f"{CANARY_SET_PATH} already exists. Re-pinning resets the drift series — "
            f"pass --force if that is what you want."
        )

    from src.database.db import SessionLocal

    db = SessionLocal()
    try:
        picked = select_canary_jobs(db, args.size)
    finally:
        db.close()

    if not picked:
        raise SystemExit("No eligible jobs found (need a scored job with a 200+ char description)")

    logger.info("Selected %d jobs:", len(picked))
    for p in picked:
        logger.info("  %-44s %s", p["title"][:44], p["company"][:24])

    if args.dry_run:
        logger.info("Dry run — nothing written.")
        return

    CANARY_SET_PATH.parent.mkdir(parents=True, exist_ok=True)
    CANARY_SET_PATH.write_text(json.dumps({"jobs": picked}, indent=2) + "\n")
    logger.info("Wrote %s", CANARY_SET_PATH)


if __name__ == "__main__":
    main()
