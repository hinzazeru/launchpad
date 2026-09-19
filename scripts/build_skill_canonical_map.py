#!/usr/bin/env python3
"""Build data/skill_canonical_map.json — run offline, not on any request path.

Why: 579 Principal/Staff/Group postings produced 1,313 distinct must-have skill
strings. `cross-functional leadership` (131) and `cross-functional
collaboration` (38) are the same requirement counted twice; so are
`communication` (64) and `communication skills` (29), and `data analysis` (94)
vs `analytical skills` (25) vs `data-driven decision making` (41). Ranking raw
strings materially understates what these roles actually ask for.

One Gemini call folds the raw strings into ~40-60 canonical skills. The output
is plain JSON: reviewable, hand-editable, diffable. If a grouping is wrong, edit
the line — nothing needs re-running.

Usage:
    railway run --service Postgres ./venv/bin/python scripts/build_skill_canonical_map.py --dry-run
    railway run --service Postgres ./venv/bin/python scripts/build_skill_canonical_map.py
    ./venv/bin/python scripts/build_skill_canonical_map.py --local     # SQLite

Idempotent: strings already mapped are not re-sent, so a re-run after new
postings arrive costs only the delta.
"""

import argparse
import json
import logging
import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.analysis.seniority_profile import CANONICAL_MAP_PATH, parse_requirements

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("build_skill_canonical_map")

# Batch size chosen so the prompt stays well inside context while keeping the
# call count at one or two for a corpus this size.
BATCH_SIZE = 400

PROMPT = """You are normalising job-posting skill labels for a product management corpus.

Below is a list of raw skill strings extracted from job descriptions. Many are
the same underlying requirement written differently — "communication" and
"communication skills"; "cross-functional leadership" and "cross-functional
collaboration"; "data analysis", "analytical skills" and "data-driven decision
making".

Map EVERY input string to a canonical skill name.

Rules:
- Use lowercase for canonical names.
- Prefer the shortest clear phrasing ("communication", not "communication skills").
- Merge aggressively where the underlying requirement is the same, but DO NOT
  merge genuinely different skills. "product strategy" and "product roadmapping"
  are different. "sql" and "data analysis" are different.
- Keep named technologies distinct ("sql", "figma", "jira", "python").
- Aim for 40-60 distinct canonical names across the whole corpus.
- Every input string must appear exactly once as a key.

Return ONLY a JSON object mapping input string to canonical name:
{{"raw string": "canonical name", ...}}

Input strings:
{skills}
"""


def collect_raw_skills(session) -> Counter:
    """Every distinct skill string across PM postings, with frequency."""
    from src.database.models import JobPosting

    rows = (
        session.query(JobPosting.structured_requirements)
        .filter(JobPosting.title.ilike("%product%"))
        .all()
    )

    counter = Counter()
    skipped = 0
    for (raw,) in rows:
        data = parse_requirements(raw)
        if data is None:
            skipped += 1
            continue
        for field in ("must_have_skills", "nice_to_have_skills"):
            for item in data.get(field) or []:
                name = item.get("name") if isinstance(item, dict) else item
                if name and str(name).strip():
                    counter[str(name).strip().lower()] += 1

    logger.info("Scanned %d postings (%d without usable requirements)", len(rows), skipped)
    return counter


def call_gemini(batch):
    from google.genai import types
    from src.integrations.gemini_client import get_rate_limiter
    from src.config import get_config
    from google import genai

    config = get_config()
    api_key = config.get("gemini.api_key")
    if not api_key:
        raise SystemExit("GEMINI_API_KEY not configured")

    model = config.get("gemini.extraction_model", "gemini-3.1-flash-lite")
    client = genai.Client(api_key=api_key)
    limiter = get_rate_limiter(model)

    response = limiter.call_with_retry(
        client.models.generate_content,
        model=model,
        contents=PROMPT.format(skills="\n".join(batch)),
        config=types.GenerateContentConfig(
            temperature=0.0,
            response_mime_type="application/json",
            max_output_tokens=32000,
        ),
    )
    from src.integrations.gemini_client import clean_json_text
    return json.loads(clean_json_text(response.text))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="report counts, call nothing, write nothing")
    ap.add_argument("--local", action="store_true", help="use the local SQLite database")
    ap.add_argument("--min-count", type=int, default=1, help="ignore strings rarer than this")
    args = ap.parse_args()

    if args.local:
        os.environ.setdefault("DATABASE_URL", "sqlite:///linkedin_job_matcher.db")
    elif os.environ.get("DATABASE_PUBLIC_URL"):
        os.environ["DATABASE_URL"] = os.environ["DATABASE_PUBLIC_URL"]

    from src.database.db import SessionLocal

    session = SessionLocal()
    try:
        counter = collect_raw_skills(session)
    finally:
        session.close()

    raw = [s for s, c in counter.items() if c >= args.min_count]
    existing = {}
    if CANONICAL_MAP_PATH.exists():
        existing = json.loads(CANONICAL_MAP_PATH.read_text())
        logger.info("Existing map has %d entries", len(existing))

    todo = sorted(s for s in raw if s not in existing)

    logger.info("Distinct skill strings: %d (>= min-count %d)", len(raw), args.min_count)
    logger.info("Already mapped: %d", len(raw) - len(todo))
    logger.info("To send to Gemini: %d in %d batch(es)",
                len(todo), (len(todo) + BATCH_SIZE - 1) // BATCH_SIZE)

    if args.dry_run:
        logger.info("Dry run — nothing called, nothing written.")
        for s, c in counter.most_common(15):
            logger.info("  %5d  %s", c, s[:60])
        return

    if not todo:
        logger.info("Map is already complete. Nothing to do.")
        return

    mapping = dict(existing)
    for i in range(0, len(todo), BATCH_SIZE):
        batch = todo[i:i + BATCH_SIZE]
        logger.info("Batch %d: %d strings...", i // BATCH_SIZE + 1, len(batch))
        result = call_gemini(batch)
        # Only accept keys we asked about — a hallucinated key would otherwise
        # silently enter the map and never match anything.
        for k, v in result.items():
            key = str(k).strip().lower()
            if key in set(batch) and v:
                mapping[key] = str(v).strip().lower()
        logger.info("  mapped %d/%d", len([k for k in batch if k in mapping]), len(batch))

    unmapped = [s for s in todo if s not in mapping]
    if unmapped:
        logger.warning("%d strings came back unmapped (they fall through to raw): %s",
                       len(unmapped), unmapped[:5])

    CANONICAL_MAP_PATH.parent.mkdir(parents=True, exist_ok=True)
    CANONICAL_MAP_PATH.write_text(json.dumps(mapping, indent=2, sort_keys=True) + "\n")

    canonical_count = len(set(mapping.values()))
    logger.info("Wrote %s: %d raw strings -> %d canonical skills",
                CANONICAL_MAP_PATH, len(mapping), canonical_count)


if __name__ == "__main__":
    main()
