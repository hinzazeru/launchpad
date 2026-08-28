"""A/B the current matching prompt against a calibrated variant.

Motivation — measured, not assumed: production's score distribution is
mean 70.5, with 2,584 of 4,633 scored jobs at 70+ and 693 at 85+. When more
than half the corpus is a "strong match", the score has stopped discriminating,
and the user has to triage the shortlist by hand anyway.

maester (github.com/GabeTHEGeek/maester) tackles the same problem with two
devices this prompt lacks:

  1. Explicit anti-inflation calibration — "most listings should NOT score
     above 4.0", "never inflate the score to be encouraging".
  2. A GATE rather than a pure weighted average — if the core skills/role match
     is weak, the overall score is CAPPED, so one fatal dimension can veto
     instead of being averaged away by the other 60%.

This scores the same jobs against the same resume through the same code path,
changing ONLY the prompt text, and reports whether the distribution actually
spreads out and whether the top of the ranking changes.

Read-only: writes no MatchResult rows and does not touch job data.

Usage::

    ./venv/bin/python scripts/compare_scoring_calibration.py --limit 30
"""

import argparse
import json
import statistics
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Inserted directly above "**Response format" in both prompt variants.
# Two independent devices, testable separately. The first A/B applied BOTH and
# the result was ambiguous: spread got WORSE (sd 21.0 -> 16.4) and ordering
# barely moved (Spearman 0.932), yet the biggest drops were all genuine
# title-inflation cases (Project/Program Manager, Business Analyst scoring 76-82
# under the current prompt). The anti-inflation text appeared to be anchoring
# everything downward while the gate did the useful discriminating work — so
# they need to be measured apart.

ANTI_INFLATION = """
**CALIBRATION — READ BEFORE SCORING:**
Be honest and calibrated. Most postings should NOT score above 75. A score is a
prediction about whether applying is worth this person's limited time, not
encouragement. Never inflate to be positive; an inflated score costs the
candidate hours on an application that was never going to land.

Use the full range. If two roles differ in fit, they should differ in score —
avoid clustering everything into 70-85.
"""

def _skills_gate(ceiling: int, adj_lo: int, adj_hi: int, none_lo: int, none_hi: int) -> str:
    """Build the gate block at a given ceiling.

    The ceiling is parameterised because 55 proved too tight in testing: it held
    firm on jobs the model was confident about (Fanatics supply-chain 72->52,
    sd 1.7; CLEAR payments 76->50, sd 2.0) but produced 14-point run-to-run swings
    on genuinely transferable platform roles (Life360 Ecosystems ranged 64-78,
    sd 5.2). The hypothesis under test: a higher ceiling still demotes the
    confident vetoes below a 70 threshold, while giving ambiguous transferable
    roles room to settle instead of fighting the cap.
    """
    return f"""
**SKILLS GATE (this overrides the weighted average above):**
If the must-have skills are largely absent, OR the role's actual substance is a
different function than the candidate's background despite a similar-sounding
title, OR it demands a depth of specialisation the résumé does not evidence,
then overall_score has a CEILING of {ceiling} — a ceiling, not a fixed value. Within
that capped range still differentiate by severity: genuine adjacency with
transferable substance lands {adj_lo}-{adj_hi}; no realistic alignment lands {none_lo}-{none_hi}.
Two roles failing the gate for different reasons should rarely score identically.

This is a veto on one dimension, NOT a general instruction to score lower. A
role that genuinely fits should still score as high as it deserves — do not
deflate strong matches. Transferable platform/technical experience counts as
genuine adjacency, not as a missing specialisation.

Distinguish REAL gaps (experience the candidate genuinely lacks) from
PRESENTATION gaps (experience they have, but the résumé buries). Put real gaps
in concerns; put presentation gaps in recommendations.
"""


SKILLS_GATE = _skills_gate(55, 45, 55, 20, 35)
SKILLS_GATE_65 = _skills_gate(65, 55, 65, 25, 40)

VARIANTS = {
    "current": "",
    "gate_only": SKILLS_GATE,          # ceiling 55
    "gate_65": SKILLS_GATE_65,         # ceiling 65 — looser, under test
    "calibrated": ANTI_INFLATION + SKILLS_GATE,
}


# Verified against provider pricing pages 2026-08-27.
# gemini-3-flash-preview bills THINKING tokens as output, which is why they are
# captured separately below — an earlier cost estimate for these runs was pure
# guesswork because nothing recorded them.
MATCH_MODEL_RATES = {"in": 0.50, "out": 3.00}


class UsageRecorder:
    """Wraps the raw generate_content call to capture real token usage.

    GeminiMatcher.match_job returns a parsed GeminiMatchResult and discards the
    response envelope, so usage_metadata is unreachable from the outside. Rather
    than change library code for a throwaway experiment, this wraps the client
    method the matcher calls.
    """

    def __init__(self):
        self.calls = []  # (prompt_tokens, output_tokens, thinking_tokens)

    def wrap(self, fn):
        def inner(*args, **kwargs):
            resp = fn(*args, **kwargs)
            meta = getattr(resp, "usage_metadata", None)
            if meta is not None:
                self.calls.append((
                    getattr(meta, "prompt_token_count", 0) or 0,
                    getattr(meta, "candidates_token_count", 0) or 0,
                    getattr(meta, "thoughts_token_count", 0) or 0,
                ))
            return resp
        return inner

    def totals(self):
        return (sum(c[0] for c in self.calls),
                sum(c[1] for c in self.calls),
                sum(c[2] for c in self.calls))

    def cost(self):
        pin, out, think = self.totals()
        # Thinking tokens are billed at the output rate. Some SDK versions fold
        # them into candidates_token_count already; guard against double count.
        billed_out = out if think and think <= out else out + think
        return (pin / 1e6) * MATCH_MODEL_RATES["in"] + (billed_out / 1e6) * MATCH_MODEL_RATES["out"]


def build_variant(original: str, block: str) -> str:
    if not block:
        return original
    marker = "**Response format"
    assert marker in original, "prompt shape changed; update the insertion marker"
    head, sep, tail = original.partition(marker)
    return head + block + "\n" + sep + tail


def load_resume_profile(path: Path) -> dict:
    """Flatten the résumé JSON the same way the search pipeline does."""
    data = json.loads(path.read_text())
    skills_by_cat = data.get("skills", {})
    flat, domains = [], []
    for cat, values in skills_by_cat.items():
        if cat == "domains":
            domains = list(values)
        else:
            flat.extend(values)

    years = 0.0
    roles = []
    for exp in data.get("experience", []):
        roles.append(f"{exp.get('title','')} at {exp.get('company','')}")
        start, end = exp.get("start_date"), exp.get("end_date")
        if start:
            try:
                sy, sm = (int(x) for x in start.split("-")[:2])
                if end and end.lower() not in ("present", "current"):
                    ey, em = (int(x) for x in end.split("-")[:2])
                else:
                    from datetime import datetime

                    now = datetime.now()
                    ey, em = now.year, now.month
                years += max(0, (ey - sy) * 12 + (em - sm)) / 12
            except (ValueError, TypeError):
                pass
    return {
        "resume_skills": flat,
        "experience_years": round(years, 1),
        "resume_domains": domains,
        "recent_roles": roles[:3],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=30)
    ap.add_argument("--resume", default="data/resumes/resume_2026.json")
    ap.add_argument("--variants", default="current,gate_only",
                    help="comma-separated subset of: current, gate_only, calibrated")
    ap.add_argument("--sample", choices=["recent", "random"], default="random",
                    help="'random' avoids the date-ordering skew that made a small "
                         "recent-only slice all wrong-function roles")
    ap.add_argument("--seed", type=int, default=42, help="random sample seed")
    ap.add_argument("--recency-days", type=int, default=None,
                    help="only jobs posted within N days (matches the pipeline's "
                         "own max_job_age_days filter)")
    args = ap.parse_args()

    from src.database.db import SessionLocal
    from src.database.models import JobPosting
    from src.matching import gemini_matcher as gm

    profile = load_resume_profile(PROJECT_ROOT / args.resume)
    import os
    dburl = os.environ.get("DATABASE_URL", "sqlite (local)")
    kind = "POSTGRES (production)" if dburl.startswith("postgres") else "sqlite (local)"
    print(f"database: {kind} — READ ONLY, no MatchResult rows are written")
    print(f"resume: {args.resume}")
    print(f"  {len(profile['resume_skills'])} skills, {profile['experience_years']} yrs, "
          f"{len(profile['resume_domains'])} domains\n")

    session = SessionLocal()
    try:
        q = session.query(JobPosting).filter(JobPosting.description.isnot(None))
        if args.recency_days:
            from datetime import datetime, timedelta, timezone
            cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=args.recency_days)
            q = q.filter(JobPosting.posting_date >= cutoff)
        if args.sample == "recent":
            q = q.order_by(JobPosting.posting_date.desc()).limit(args.limit * 3)
        pool = [
            (j.id, j.title, j.company, j.description, j.structured_requirements)
            for j in q.all()
            if len(j.description or "") > 400
        ]
    finally:
        session.close()

    if args.sample == "random":
        import random
        random.Random(args.seed).shuffle(pool)
    jobs = pool[: args.limit]
    print(f"  sampling {len(jobs)} of {len(pool)} eligible jobs ({args.sample})")

    matcher = gm.GeminiMatcher()
    if not matcher.is_available():
        print("Gemini not available", file=sys.stderr)
        return 1

    _raw_generate = matcher.client.models.generate_content
    orig_struct, orig_simple = gm.AI_MATCH_PROMPT, gm.AI_MATCH_SIMPLE_PROMPT
    names = [v.strip() for v in args.variants.split(",") if v.strip()]
    for v in names:
        assert v in VARIANTS, f"unknown variant {v}; choose from {list(VARIANTS)}"

    results = {v: {} for v in names}
    usage = {}
    for label in names:
        rec = UsageRecorder()
        usage[label] = rec
        matcher.client.models.generate_content = rec.wrap(_raw_generate)
        block = VARIANTS[label]
        gm.AI_MATCH_PROMPT = build_variant(orig_struct, block)
        gm.AI_MATCH_SIMPLE_PROMPT = build_variant(orig_simple, block)
        print(f"  scoring {len(jobs)} jobs [{label}] ", end="", flush=True)
        for jid, title, company, desc, reqs in jobs:
            try:
                r = matcher.match_job(
                    resume_skills=profile["resume_skills"],
                    experience_years=profile["experience_years"],
                    resume_domains=profile["resume_domains"],
                    recent_roles=profile["recent_roles"],
                    job_title=title,
                    company=company,
                    job_description=desc,
                    structured_requirements=reqs,
                )
                results[label][jid] = r.overall_score if r else None
            except Exception as e:
                print(f"\n    ! job {jid}: {type(e).__name__}: {e}"[:120])
                results[label][jid] = None
            print(".", end="", flush=True)
        print()
    gm.AI_MATCH_PROMPT, gm.AI_MATCH_SIMPLE_PROMPT = orig_struct, orig_simple
    matcher.client.models.generate_content = _raw_generate

    print(f"\n{'-' * 72}\nTOKENS & COST (measured, not estimated)")
    print(f"{'variant':14} {'calls':>6} {'in':>9} {'out':>9} {'thinking':>9} {'cost $':>9}")
    grand = 0.0
    for label in names:
        rec = usage[label]
        pin, out, think = rec.totals()
        grand += rec.cost()
        print(f"{label:14} {len(rec.calls):6} {pin:9} {out:9} {think:9} {rec.cost():9.4f}")
    print(f"{'TOTAL':14} {'':6} {'':9} {'':9} {'':9} {grand:9.4f}")
    if names:
        per = grand / max(sum(len(usage[l].calls) for l in names), 1)
        print(f"per call: ${per:.5f}   ->  1000 calls would cost ${per * 1000:.2f}")

    ids = [j[0] for j in jobs
           if all(results[v].get(j[0]) is not None for v in names)]
    if not ids:
        print("no comparable results", file=sys.stderr)
        return 1

    base, comp = names[0], names[-1]
    cur = [results[base][i] for i in ids]
    cal = [results[comp][i] for i in ids]

    print(f"\n{'=' * 72}\n{'metric':28} {base:>12} {comp:>12}")
    def row(name, f):
        print(f"{name:28} {f(cur):>12.1f} {f(cal):>12.1f}")
    row("mean", statistics.mean)
    row("median", statistics.median)
    row("std dev (spread)", statistics.pstdev)
    row("min", min)
    row("max", max)
    for thr in (85, 75, 70, 60):
        c = sum(1 for x in cur if x >= thr); k = sum(1 for x in cal if x >= thr)
        print(f"{'>= ' + str(thr):28} {c:>7} ({c/len(cur)*100:3.0f}%) {k:>7} ({k/len(cal)*100:3.0f}%)")

    # Rank agreement: does the ORDER change, or just the absolute numbers?
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i], reverse=True)
        r = [0] * len(v)
        for pos, i in enumerate(order):
            r[i] = pos
        return r
    rc, rk = ranks(cur), ranks(cal)
    n = len(ids)
    d2 = sum((a - b) ** 2 for a, b in zip(rc, rk))
    rho = 1 - (6 * d2) / (n * (n * n - 1)) if n > 1 else 1.0
    print(f"\nSpearman rank correlation: {rho:.3f}  "
          f"(1.0 = identical ordering, only the numbers moved)")

    print(f"\nbiggest movers ({comp} - {base}):")
    moves = sorted(zip(ids, cur, cal), key=lambda t: t[2] - t[1])
    session = SessionLocal()
    try:
        from src.database.models import JobPosting as JP
        titles = {j.id: (j.title, j.company)
                  for j in session.query(JP).filter(JP.id.in_([m[0] for m in moves])).all()}
    finally:
        session.close()
    for jid, c, k in moves[:5] + moves[-5:]:
        t, co = titles.get(jid, ("?", "?"))
        print(f"  {k - c:+6.0f}  {c:5.0f} -> {k:5.0f}  {t[:40]:40} @ {co[:20]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
