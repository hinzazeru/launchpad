"""Measure run-to-run consistency of Gemini domain extraction.

Re-extracting 704 jobs with a corrected prompt produced changes far larger than
the prompt edit could explain: `data_engineering` fell 180 -> 38 and `ai_ml`
265 -> 149, on keys that were always available. Two explanations fit —
either the model's answers are simply unstable run to run, or the stored
"before" state was produced by a different model/prompt generation and was never
a comparable baseline.

This distinguishes them: extract the SAME jobs N times with the IDENTICAL prompt
in a single session, and measure how much the answers disagree with themselves.
Whatever instability shows up here is a floor on the noise in any before/after
comparison — churn below it is meaningless.

Read-only. Writes nothing to the database.

Usage::

    ./venv/bin/python scripts/measure_domain_consistency.py --limit 20 --runs 2
"""

import argparse
import statistics
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def jaccard(a: set, b: set) -> float:
    """1.0 = identical, 0.0 = no overlap. Two empty sets count as identical."""
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--runs", type=int, default=2)
    args = ap.parse_args()

    from src.database.db import SessionLocal
    from src.database.models import JobPosting
    from src.integrations.gemini_client import GeminiDomainExtractor

    extractor = GeminiDomainExtractor()
    if not extractor.is_available():
        print("Gemini not available", file=sys.stderr)
        return 1

    session = SessionLocal()
    try:
        jobs = (
            session.query(JobPosting)
            .filter(JobPosting.description.isnot(None))
            .order_by(JobPosting.id.desc())
            .limit(args.limit)
            .all()
        )
        # Detach the fields we need so the session can close.
        jobs = [(j.id, j.title, j.company, j.description, set(j.required_domains or []))
                for j in jobs]
    finally:
        session.close()

    print(f"{len(jobs)} jobs x {args.runs} runs, identical prompt each time\n")

    results = {}  # job_id -> list[set]
    for run in range(1, args.runs + 1):
        print(f"  run {run}/{args.runs} ", end="", flush=True)
        for job_id, title, company, description, _stored in jobs:
            out = extractor.extract_domains(
                description=description, company=company, title=title
            )
            results.setdefault(job_id, []).append(set(out.get("domains") or []))
            print(".", end="", flush=True)
        print()

    # --- self-consistency across runs -------------------------------------
    sims, identical = [], 0
    for job_id, runs in results.items():
        pairs = [
            jaccard(runs[i], runs[j])
            for i in range(len(runs))
            for j in range(i + 1, len(runs))
        ]
        s = statistics.mean(pairs) if pairs else 1.0
        sims.append(s)
        if s == 1.0:
            identical += 1

    print(f"\n{'=' * 68}")
    print("SELF-CONSISTENCY (same prompt, same job, different calls)")
    print(f"  mean Jaccard similarity : {statistics.mean(sims):.3f}")
    print(f"  median                  : {statistics.median(sims):.3f}")
    print(f"  identical across runs   : {identical}/{len(sims)} jobs "
          f"({identical / len(sims) * 100:.0f}%)")

    # --- per-key volatility ----------------------------------------------
    flips = Counter()
    for runs in results.values():
        union = set().union(*runs)
        for key in union:
            if not all(key in r for r in runs):
                flips[key] += 1
    if flips:
        print("\n  keys that appeared in some runs but not others:")
        for key, n in flips.most_common(12):
            print(f"    {key:24} unstable on {n} job(s)")

    # --- comparison against what is stored --------------------------------
    stored_sims = []
    for job_id, title, company, description, stored in jobs:
        stored_sims.append(jaccard(stored, results[job_id][0]))
    print(f"\n  vs currently STORED domains: mean Jaccard "
          f"{statistics.mean(stored_sims):.3f}")

    print(f"\n{'=' * 68}")
    mean = statistics.mean(sims)
    if mean < 0.75:
        print("READ: extraction is substantially unstable run-to-run. Before/after")
        print("      comparisons at this noise level cannot attribute change to a")
        print("      prompt edit. Consider lowering temperature or accepting that")
        print("      domain tags are approximate.")
    elif mean < 0.9:
        print("READ: moderate instability. Small before/after deltas are noise;")
        print("      only large, directional shifts are meaningful.")
    else:
        print("READ: extraction is stable. Large before/after churn is therefore")
        print("      NOT run-to-run variance — it points at the stored baseline")
        print("      having been produced by a different model or prompt.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
