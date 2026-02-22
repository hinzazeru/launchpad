"""Salary Extraction Experiment: Regex vs Gemini.

Read-only experiment. Samples 40 jobs from the DB, runs both the existing regex
extractor and Gemini on each description, and prints a comparison table.

Output: terminal table + scripts/salary_experiment_results.csv
No DB writes.
"""

import sys
import os
import random
import time
import csv
from typing import Optional

sys.path.insert(0, os.getcwd())

from src.database.db import get_db_session
from src.database.models import JobPosting
from src.matching.skill_extractor import extract_salary_from_description
from src.config import get_config
import google.generativeai as genai

SAMPLE_SIZE = 40
GEMINI_SLEEP = 0.5  # seconds between calls — stay under 0.4s rate limit with buffer
DESCRIPTION_TRUNCATE = 3000

GEMINI_PROMPT = """\
Extract the salary or compensation from this job description.
Return ONLY the salary/range as a compact string (e.g. "$120K–$150K", "$95,000/yr", "CAD $80K–$100K").
If no salary is present, return exactly: None

Job description:
{description}"""

OUTPUT_CSV = os.path.join(os.path.dirname(__file__), "salary_experiment_results.csv")


def call_gemini(model, description: str) -> Optional[str]:
    """Ask Gemini to extract salary from description. Returns the extracted string or None."""
    prompt = GEMINI_PROMPT.format(description=description[:DESCRIPTION_TRUNCATE])
    try:
        response = model.generate_content(prompt)
        result = response.text.strip()
        if result.lower() == "none":
            return None
        return result
    except Exception as e:
        return f"ERROR: {e}"


def classify_outcome(regex_result, gemini_result) -> str:
    regex_found = regex_result is not None
    gemini_found = gemini_result is not None and not str(gemini_result).startswith("ERROR")

    if regex_found and gemini_found:
        if regex_result != gemini_result:
            return "Both found (disagree)"
        return "Both found"
    if gemini_found and not regex_found:
        return "Gemini only"
    if regex_found and not gemini_found:
        return "Regex only"
    return "Neither found"


def main():
    # ── DB sample ──────────────────────────────────────────────────────────────
    db = get_db_session()
    try:
        jobs = db.query(JobPosting).filter(JobPosting.description.isnot(None)).all()
    finally:
        db.close()

    if not jobs:
        print("No jobs with descriptions found in the database.")
        sys.exit(1)

    sample = random.sample(jobs, min(SAMPLE_SIZE, len(jobs)))
    print(f"Sampled {len(sample)} jobs from {len(jobs)} total.\n")

    # ── Gemini setup ───────────────────────────────────────────────────────────
    config = get_config()
    api_key = config.get("gemini.api_key")
    if not api_key:
        print("ERROR: gemini.api_key not configured. Set GEMINI_API_KEY env var.")
        sys.exit(1)

    model_name = config.get("gemini.matcher.model", "gemini-2.0-flash")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    print(f"Using Gemini model: {model_name}\n")

    # ── Run experiment ─────────────────────────────────────────────────────────
    rows = []
    for i, job in enumerate(sample, start=1):
        title = (job.title or "")[:30]
        company = (job.company or "")[:18]
        db_salary = job.salary or None

        regex_result = extract_salary_from_description(job.description)
        gemini_result = call_gemini(model, job.description)

        outcome = classify_outcome(regex_result, gemini_result)

        rows.append({
            "id": job.id,
            "title": job.title or "",
            "company": job.company or "",
            "db_salary": db_salary or "",
            "regex_result": regex_result or "",
            "gemini_result": gemini_result or "",
            "outcome": outcome,
        })

        # Print progress row
        print(
            f"{i:>2}. "
            f"{title:<30} "
            f"{company:<18} "
            f"DB:{str(db_salary or 'None'):<14} "
            f"Regex:{str(regex_result or 'None'):<16} "
            f"Gemini:{str(gemini_result or 'None'):<20} "
            f"→ {outcome}"
        )

        if i < len(sample):
            time.sleep(GEMINI_SLEEP)

    # ── Summary stats ──────────────────────────────────────────────────────────
    outcomes = [r["outcome"] for r in rows]
    both = sum(1 for o in outcomes if o.startswith("Both found"))
    both_disagree = sum(1 for o in outcomes if o == "Both found (disagree)")
    gemini_only = sum(1 for o in outcomes if o == "Gemini only")
    regex_only = sum(1 for o in outcomes if o == "Regex only")
    neither = sum(1 for o in outcomes if o == "Neither found")
    total = len(rows)

    print("\n" + "=" * 80)
    print(f"Total sampled : {total}")
    print(f"Both found    : {both}  ({both/total*100:.0f}%)")
    print(f"Gemini only   : {gemini_only}  ← Gemini advantage")
    print(f"Regex only    : {regex_only}  ← Regex advantage")
    print(f"Neither found : {neither}")
    print(f"Disagreements : {both_disagree}  (both found but differ)")
    print("=" * 80)

    # ── CSV output ─────────────────────────────────────────────────────────────
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["id", "title", "company", "db_salary", "regex_result", "gemini_result", "outcome"]
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nResults saved to: {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
