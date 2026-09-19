#!/usr/bin/env python3
"""Build data/responsibility_themes.json — run offline, not on any request path.

Why keywords rather than a {string: theme} map: 33,071 of the 35,707
responsibility strings in the corpus are unique sentences, and only 1,688 ever
repeat. Mapping strings one-to-one would classify almost nothing and would need
regenerating for every new posting. Themes carrying keyword patterns generalise
to text the model never saw.

One Gemini call over a frequency-weighted sample produces ~10 themes with
indicative keywords. Output is plain JSON — reviewable and hand-editable; if a
theme over-matches, delete a keyword.

Usage:
    railway run --service Postgres ./venv/bin/python scripts/build_responsibility_themes.py --dry-run
    railway run --service Postgres ./venv/bin/python scripts/build_responsibility_themes.py
"""

import argparse
import json
import logging
import os
import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.analysis.seniority_profile import RESPONSIBILITY_THEMES_PATH, parse_requirements

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("build_responsibility_themes")

SAMPLE_SIZE = 600

PROMPT = """You are grouping product-management job responsibilities into themes.

Below is a sample of responsibility statements from real job postings.

Identify 8-12 themes that together cover the great majority of them. For each
theme give lowercase keywords/phrases that reliably indicate it — these will be
used for substring matching against responsibility text, so they must be
specific enough not to fire on unrelated statements.

Rules:
- Keywords are matched as plain substrings, lowercase. Prefer distinctive stems
  ("roadmap", "backlog", "go-to-market") over generic words ("work", "team",
  "product") that appear in nearly every statement.
- 4-10 keywords per theme.
- Themes should describe WHAT THE JOB DOES, not seniority.
- Themes may overlap; a statement can match more than one.

Return ONLY JSON:
{{"themes": [{{"name": "theme name", "keywords": ["kw1", "kw2"]}}]}}

Responsibility statements:
{sample}
"""


def collect(session):
    from src.database.models import JobPosting

    rows = (
        session.query(JobPosting.structured_requirements)
        .filter(JobPosting.title.ilike("%product%"))
        .all()
    )
    counter = Counter()
    for (raw,) in rows:
        data = parse_requirements(raw)
        if not data:
            continue
        for r in data.get("key_responsibilities") or []:
            text = str(r).strip().lower()
            if text:
                counter[text] += 1
    return counter


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--local", action="store_true")
    args = ap.parse_args()

    if args.local:
        os.environ.setdefault("DATABASE_URL", "sqlite:///linkedin_job_matcher.db")
    elif os.environ.get("DATABASE_PUBLIC_URL"):
        os.environ["DATABASE_URL"] = os.environ["DATABASE_PUBLIC_URL"]

    from src.database.db import SessionLocal

    session = SessionLocal()
    try:
        counter = collect(session)
    finally:
        session.close()

    logger.info("Responsibility statements: %d total, %d distinct",
                sum(counter.values()), len(counter))

    # Frequency-weighted: every repeated statement, topped up with a random
    # sample of the singleton tail so the themes reflect the long tail too
    # rather than only the handful of boilerplate lines.
    repeated = [s for s, c in counter.most_common() if c >= 2]
    singles = [s for s, c in counter.items() if c == 1]
    random.seed(0)
    sample = repeated[:SAMPLE_SIZE // 2] + random.sample(
        singles, min(SAMPLE_SIZE - len(repeated[:SAMPLE_SIZE // 2]), len(singles))
    )
    logger.info("Sampling %d statements (%d repeated + %d from the tail)",
                len(sample), len(repeated[:SAMPLE_SIZE // 2]), len(sample) - len(repeated[:SAMPLE_SIZE // 2]))

    if args.dry_run:
        logger.info("Dry run — nothing called, nothing written.")
        for s in sample[:10]:
            logger.info("  - %s", s[:76])
        return

    from google import genai
    from google.genai import types
    from src.config import get_config
    from src.integrations.gemini_client import clean_json_text, get_rate_limiter

    config = get_config()
    api_key = config.get("gemini.api_key")
    if not api_key:
        raise SystemExit("GEMINI_API_KEY not configured")
    model = config.get("gemini.extraction_model", "gemini-3.1-flash-lite")

    client = genai.Client(api_key=api_key)
    response = get_rate_limiter(model).call_with_retry(
        client.models.generate_content,
        model=model,
        contents=PROMPT.format(sample="\n".join(f"- {s}" for s in sample)),
        config=types.GenerateContentConfig(
            temperature=0.0,
            response_mime_type="application/json",
            max_output_tokens=8000,
        ),
    )
    data = json.loads(clean_json_text(response.text))
    themes = data.get("themes") if isinstance(data, dict) else data
    if not themes:
        raise SystemExit("Gemini returned no themes")

    # Report coverage before writing: a theme set that matches nothing is worse
    # than none at all, because it renders as a confident empty section.
    matched = 0
    for stmt, count in counter.items():
        if any(any(k.lower() in stmt for k in t.get("keywords", [])) for t in themes):
            matched += count
    total = sum(counter.values())
    logger.info("Coverage: %d/%d statements match at least one theme (%.1f%%)",
                matched, total, 100.0 * matched / total)

    RESPONSIBILITY_THEMES_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESPONSIBILITY_THEMES_PATH.write_text(
        json.dumps({"themes": themes}, indent=2) + "\n"
    )
    logger.info("Wrote %s with %d themes", RESPONSIBILITY_THEMES_PATH, len(themes))
    for t in themes:
        logger.info("  %-34s %s", t.get("name", "?")[:34], ", ".join(t.get("keywords", [])[:6]))


if __name__ == "__main__":
    main()
