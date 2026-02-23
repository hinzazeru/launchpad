"""Backfill matching_skills for existing Gemini match results.

Applies the same split-on-comma + deduplicate logic introduced in the engine
fix (commit 4d335c3). Two problems existed in the stored data:

1. Duplicate entries: multiple job skills mapped to the same resume skill,
   repeating it once per job_skill in matching_skills.
2. Comma-joined strings: Gemini packed multiple skills into one resume_skill
   value (e.g. "SQL, Analytics, Snowflake") instead of a single skill.

For records that have skill_matches (detailed JSON), the new matching_skills
is re-derived from that source — the same way the engine now builds it.
For records missing skill_matches, the fix is applied directly to the
existing matching_skills list.

Run against Railway Postgres:
    railway run python scripts/backfill_matching_skills.py

Run against local SQLite (dev):
    python scripts/backfill_matching_skills.py
"""

import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def _fix_skills_list(skills: list) -> list:
    """Split comma-joined skill strings and deduplicate, preserving order."""
    seen = set()
    result = []
    for skill_str in (skills or []):
        if not skill_str:
            continue
        for part in skill_str.split(","):
            part = part.strip()
            if part and part not in seen:
                seen.add(part)
                result.append(part)
    return result


CONFIDENCE_THRESHOLD = 0.75  # Must match engine.py _match_with_gemini()


def _derive_from_skill_matches(skill_matches: list) -> list:
    """Re-derive matching_skills from the stored skill_matches JSON.

    Applies the same logic as engine.py _match_with_gemini():
      - Only include entries with confidence >= CONFIDENCE_THRESHOLD
      - Split comma-joined resume_skill strings
      - Deduplicate, preserving insertion order
    """
    seen: dict = {}  # use dict to preserve insertion order (Python 3.7+)
    for m in (skill_matches or []):
        if not isinstance(m, dict):
            continue
        if (m.get("confidence") or 0) < CONFIDENCE_THRESHOLD:
            continue
        resume_skill = m.get("resume_skill") or ""
        for part in resume_skill.split(","):
            part = part.strip()
            if part:
                seen[part] = None
    return list(seen.keys())


def main() -> None:
    from src.database.db import SessionLocal
    from src.database.models import MatchResult

    db = SessionLocal()
    try:
        gemini_matches = (
            db.query(MatchResult)
            .filter(MatchResult.match_engine == "gemini")
            .all()
        )

        logger.info(f"Found {len(gemini_matches)} Gemini match results to inspect")

        updated = 0
        skipped = 0

        for mr in gemini_matches:
            original = list(mr.matching_skills or [])

            if mr.skill_matches:
                # Preferred: re-derive from the detailed skill_matches source
                new_skills = _derive_from_skill_matches(mr.skill_matches)
            else:
                # Fallback: apply split+dedup directly to the stored list
                new_skills = _fix_skills_list(original)

            if new_skills == original:
                skipped += 1
                continue

            logger.debug(
                f"  job_id={mr.job_id} | "
                f"before={len(original)} skills → after={len(new_skills)} skills"
            )
            mr.matching_skills = new_skills
            updated += 1

        db.commit()
        logger.info(
            f"Done. Updated={updated}, Already clean={skipped}, "
            f"Total={len(gemini_matches)}"
        )

    except Exception as e:
        db.rollback()
        logger.error(f"Backfill failed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
