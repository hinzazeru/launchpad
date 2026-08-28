"""Report what changed when job domains were re-extracted.

Context: `esg`, `regulatory_compliance`, `azure`, `aws`, and `gcp` existed in
``data/domain_expertise.json`` but were missing from the hardcoded list inside
``DOMAIN_EXTRACTION_PROMPT``, so Gemini was never offered them and no job could
ever be tagged with one. Three of those five are on resume_2026, meaning 21% of
the resume's domain profile matched nothing by construction.

This compares a pre-re-extraction snapshot against the current database and
reports what the fix actually recovered — specifically overlap with the active
resume, which is the number that decides whether re-extraction was worth it.

Usage::

    ./venv/bin/python scripts/report_domain_reextraction.py \\
        --before /path/to/domains_before.json \\
        --resume data/resumes/resume_2026.json
"""

import argparse
import collections
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

REVIVED = ("esg", "regulatory_compliance", "azure", "aws", "gcp")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--before", required=True, help="JSON snapshot: {job_id: [domains]}")
    ap.add_argument("--resume", default="data/resumes/resume_2026.json")
    args = ap.parse_args()

    from src.database.db import SessionLocal
    from src.database.models import JobPosting

    before = {int(k): set(v) for k, v in json.loads(Path(args.before).read_text()).items()}
    resume = set(json.loads((PROJECT_ROOT / args.resume).read_text())["skills"]["domains"])

    session = SessionLocal()
    try:
        after = {j.id: set(j.required_domains or []) for j in session.query(JobPosting).all()}
    finally:
        session.close()

    ids = sorted(set(before) & set(after))
    print(f"jobs compared: {len(ids)}   resume domains: {len(resume)}\n")

    # --- overlap with the resume, before vs after -------------------------
    ov_before = collections.Counter(len(before[i] & resume) for i in ids)
    ov_after = collections.Counter(len(after[i] & resume) for i in ids)
    print(f"{'exact resume-domain overlap':32} {'before':>8} {'after':>8} {'delta':>8}")
    for n in range(0, max(list(ov_before) + list(ov_after)) + 1):
        b, a = ov_before.get(n, 0), ov_after.get(n, 0)
        flag = "  <-- shortlist" if n >= 3 else ""
        print(f"  {n} matching domains{'':14} {b:8} {a:8} {a - b:+8}{flag}")

    gained = [i for i in ids if len(after[i] & resume) > len(before[i] & resume)]
    lost = [i for i in ids if len(after[i] & resume) < len(before[i] & resume)]
    print(f"\njobs with MORE resume overlap: {len(gained)} ({len(gained)/len(ids)*100:.1f}%)")
    print(f"jobs with LESS resume overlap: {len(lost)} ({len(lost)/len(ids)*100:.1f}%)")

    # --- the previously-unreachable keys ----------------------------------
    print("\nrevived domain keys:")
    for d in REVIVED:
        b = sum(1 for i in ids if d in before[i])
        a = sum(1 for i in ids if d in after[i])
        mark = " (on resume)" if d in resume else ""
        print(f"  {d:24} {b:5} -> {a:5}{mark}")

    # --- churn: did anything else move? ----------------------------------
    all_before = collections.Counter(d for i in ids for d in before[i])
    all_after = collections.Counter(d for i in ids for d in after[i])
    moved = sorted(
        ((d, all_after.get(d, 0) - all_before.get(d, 0)) for d in set(all_before) | set(all_after)),
        key=lambda x: abs(x[1]), reverse=True,
    )
    print("\nlargest changes across all domains (re-extraction is non-deterministic,")
    print("so some churn is expected even on keys that were always available):")
    for d, delta in moved[:12]:
        if delta:
            print(f"  {d:24} {all_before.get(d,0):5} -> {all_after.get(d,0):5} ({delta:+})")

    # --- the shortlist ----------------------------------------------------
    top = sorted(ids, key=lambda i: len(after[i] & resume), reverse=True)
    top = [i for i in top if len(after[i] & resume) >= 3]
    print(f"\njobs matching >=3 resume domains: {len(top)}")
    if top:
        from src.database.db import SessionLocal as SL
        s = SL()
        try:
            from src.database.models import JobPosting as JP
            for j in s.query(JP).filter(JP.id.in_(top[:12])).all():
                hit = sorted(set(j.required_domains or []) & resume)
                print(f"  [{len(hit)}] {j.title[:46]:46} @ {(j.company or '')[:22]:22} {hit}")
        finally:
            s.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
