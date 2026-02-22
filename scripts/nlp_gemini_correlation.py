"""NLP vs Gemini Score Correlation Analysis.

Read-only experiment. Re-runs NLP matching on jobs that were previously matched
with Gemini, then computes correlation statistics between the two scoring approaches.

This helps determine whether NLP scores are a reliable predictor of Gemini scores —
a prerequisite for using NLP as a gating signal to prioritize which jobs get Gemini
matching (to manage rate limits).

Key insight: when match_engine='gemini', the DB match_score is the Gemini score.
NLP was never run, so we can't read both from the DB — we must re-run NLP here.

Output: terminal table + scripts/nlp_gemini_correlation_results.csv
No DB writes.

Usage:
    ./venv/bin/python scripts/nlp_gemini_correlation.py
    ./venv/bin/python scripts/nlp_gemini_correlation.py --limit 50
"""

import sys
import os
import csv
import argparse
import math
from typing import List, Optional, Tuple

sys.path.insert(0, os.getcwd())

OUTPUT_CSV = os.path.join(os.path.dirname(__file__), "nlp_gemini_correlation_results.csv")


# ── Correlation helpers ────────────────────────────────────────────────────────

def _mean(xs: List[float]) -> float:
    return sum(xs) / len(xs)


def _pearson_manual(xs: List[float], ys: List[float]) -> float:
    """Manual Pearson r."""
    n = len(xs)
    if n < 2:
        return float("nan")
    mx, my = _mean(xs), _mean(ys)
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if sx == 0 or sy == 0:
        return float("nan")
    return cov / (sx * sy)


def _rank(xs: List[float]) -> List[float]:
    """Return fractional rank for each element (1-based, ties averaged)."""
    indexed = sorted(enumerate(xs), key=lambda iv: iv[1])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(indexed):
        j = i
        while j < len(indexed) - 1 and indexed[j + 1][1] == indexed[i][1]:
            j += 1
        avg_rank = (i + j) / 2 + 1  # 1-based
        for k in range(i, j + 1):
            ranks[indexed[k][0]] = avg_rank
        i = j + 1
    return ranks


def compute_correlation(
    nlp_scores: List[float], gemini_scores: List[float]
) -> Tuple[float, float, Optional[float], Optional[float]]:
    """Return (pearson_r, spearman_rho, p_pearson, p_spearman).

    Uses scipy if available; falls back to manual calculation (p-values omitted).
    """
    try:
        from scipy.stats import pearsonr, spearmanr
        pr, p_p = pearsonr(nlp_scores, gemini_scores)
        sr, p_s = spearmanr(nlp_scores, gemini_scores)
        return float(pr), float(sr), float(p_p), float(p_s)
    except ImportError:
        pr = _pearson_manual(nlp_scores, gemini_scores)
        sr = _pearson_manual(_rank(nlp_scores), _rank(gemini_scores))
        return pr, sr, None, None


def top_n_agreement(
    nlp_scores: List[float], gemini_scores: List[float], n: int
) -> Optional[float]:
    """% of Gemini top-N jobs that also appear in NLP top-N."""
    if len(nlp_scores) < n:
        return None
    idx = list(range(len(nlp_scores)))
    gemini_top = set(sorted(idx, key=lambda i: gemini_scores[i], reverse=True)[:n])
    nlp_top = set(sorted(idx, key=lambda i: nlp_scores[i], reverse=True)[:n])
    return len(gemini_top & nlp_top) / n * 100


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Correlate NLP vs Gemini match scores.")
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Cap number of records to process (default: all)"
    )
    args = parser.parse_args()

    # ── Query Gemini-matched records ───────────────────────────────────────────
    # Use raw SQL throughout to avoid ORM failures when the local SQLite schema
    # is behind models.py (columns like user_status / is_repost may not exist).
    print("Loading Gemini-matched records from database...")
    import json
    from types import SimpleNamespace
    from sqlalchemy import text
    from src.database.db import get_db_session

    def _json(val):
        """Decode a JSON column that may already be parsed or still a string."""
        if val is None:
            return None
        if isinstance(val, (list, dict)):
            return val
        try:
            return json.loads(val)
        except (TypeError, ValueError):
            return val

    db = get_db_session()
    try:
        limit_clause = f"LIMIT {args.limit}" if args.limit else ""
        mr_rows = db.execute(text(f"""
            SELECT id, job_id, resume_id, ai_match_score
            FROM match_results
            WHERE match_engine = 'gemini'
              AND ai_match_score IS NOT NULL
            ORDER BY generated_date DESC
            {limit_clause}
        """)).fetchall()

        if not mr_rows:
            print("No Gemini-matched records found. Run some Gemini matches first.")
            sys.exit(1)

        # Collect unique job/resume IDs, then batch-fetch via raw SQL
        job_ids = list({row[1] for row in mr_rows})
        resume_ids = list({row[2] for row in mr_rows})

        placeholders_j = ",".join(str(i) for i in job_ids)
        job_rows = db.execute(text(f"""
            SELECT id, title, company, description, experience_required,
                   structured_requirements, required_skills, required_domains
            FROM job_postings
            WHERE id IN ({placeholders_j})
        """)).fetchall()

        placeholders_r = ",".join(str(i) for i in resume_ids)
        resume_rows = db.execute(text(f"""
            SELECT id, skills, experience_years, domains, job_titles
            FROM resumes
            WHERE id IN ({placeholders_r})
        """)).fetchall()
    finally:
        db.close()

    # Build lookup dicts of plain SimpleNamespace objects (no ORM, no session needed)
    jobs_by_id = {}
    for r in job_rows:
        jid, title, company, desc, exp_req, struct_req, req_skills, req_domains = r
        jobs_by_id[jid] = SimpleNamespace(
            title=title,
            company=company,
            description=desc,
            experience_required=exp_req,
            structured_requirements=_json(struct_req),
            required_skills=_json(req_skills) or [],
            required_domains=_json(req_domains) or [],
        )

    resumes_by_id = {}
    for r in resume_rows:
        rid, skills, exp_years, domains, job_titles = r
        resumes_by_id[rid] = SimpleNamespace(
            skills=_json(skills) or [],
            experience_years=exp_years,
            domains=_json(domains) or [],
            job_titles=_json(job_titles) or [],
        )

    records = []
    for mr_id, job_id, resume_id, gemini_score in mr_rows:
        job = jobs_by_id.get(job_id)
        resume = resumes_by_id.get(resume_id)
        if job is None or resume is None:
            continue
        records.append({
            "mr_id": mr_id,
            "gemini_score": gemini_score,  # 0-100
            "job": job,
            "resume": resume,
            "job_title": job.title or "",
            "company": job.company or "",
        })

    print(f"Found {len(records)} Gemini-matched records.\n")
    print(
        "NOTE: SentenceTransformer will pre-cache ~183 skill embeddings on first run.\n"
        "      This may take ~1-2 minutes.\n"
    )

    # ── Initialize NLP matcher ─────────────────────────────────────────────────
    print("Initializing NLP matcher (loading sentence-transformers model)...")
    from src.matching.engine import JobMatcher
    nlp_matcher = JobMatcher(mode="nlp")
    print("NLP matcher ready.\n")

    # ── Re-run NLP on each job ─────────────────────────────────────────────────
    rows = []
    nlp_scores: List[float] = []
    gemini_scores: List[float] = []

    header = (
        f"{'#':>4}  "
        f"{'Title':<34}  "
        f"{'Company':<22}  "
        f"{'NLP':>6}  "
        f"{'Gemini':>7}  "
        f"{'Delta':>7}"
    )
    print(header)
    print("-" * len(header))

    for i, rec in enumerate(records, start=1):
        nlp_result = nlp_matcher.match_job(rec["resume"], rec["job"])
        nlp_score = round(nlp_result["overall_score"] * 100, 1)
        gemini_score = round(rec["gemini_score"], 1)
        delta = round(nlp_score - gemini_score, 1)

        nlp_scores.append(nlp_score)
        gemini_scores.append(gemini_score)

        title = rec["job_title"][:34]
        company = rec["company"][:22]

        print(
            f"{i:>4}.  "
            f"{title:<34}  "
            f"{company:<22}  "
            f"{nlp_score:>6.1f}  "
            f"{gemini_score:>7.1f}  "
            f"{delta:>+7.1f}"
        )

        rows.append({
            "match_result_id": rec["mr_id"],
            "job_title": rec["job_title"],
            "company": rec["company"],
            "nlp_score": nlp_score,
            "gemini_score": gemini_score,
            "delta": delta,
        })

    # ── Statistics ─────────────────────────────────────────────────────────────
    n = len(rows)
    pearson_r, spearman_rho, p_pearson, p_spearman = compute_correlation(nlp_scores, gemini_scores)
    mae = sum(abs(r["delta"]) for r in rows) / n
    rmse = math.sqrt(sum(r["delta"] ** 2 for r in rows) / n)
    agree_10 = top_n_agreement(nlp_scores, gemini_scores, 10)
    agree_20 = top_n_agreement(nlp_scores, gemini_scores, 20)

    sep = "=" * (len(header))
    print(f"\n{sep}")
    print(f"Records analysed : {n}")

    p_str = f"  (p={p_pearson:.4f})" if p_pearson is not None else "  (scipy not available)"
    print(f"Pearson r        : {pearson_r:.3f}{p_str}")

    p_str = f"  (p={p_spearman:.4f})" if p_spearman is not None else "  (scipy not available)"
    print(f"Spearman ρ       : {spearman_rho:.3f}{p_str}")

    print(f"Mean Abs Error   : {mae:.1f} pts")
    print(f"RMSE             : {rmse:.1f} pts")
    if agree_10 is not None:
        print(f"Top-10 agreement : {agree_10:.0f}%  (overlap between NLP top-10 and Gemini top-10)")
    else:
        print("Top-10 agreement : N/A  (fewer than 10 records)")
    if agree_20 is not None:
        print(f"Top-20 agreement : {agree_20:.0f}%  (overlap between NLP top-20 and Gemini top-20)")
    else:
        print("Top-20 agreement : N/A  (fewer than 20 records)")

    print()
    if not math.isnan(spearman_rho):
        if spearman_rho >= 0.7:
            verdict = "Strong rank correlation — NLP is a reliable gating signal for Gemini."
        elif spearman_rho >= 0.5:
            verdict = "Moderate correlation — NLP gating viable, expect some false negatives."
        elif spearman_rho >= 0.4:
            verdict = "Weak-moderate correlation — NLP gating would miss a notable fraction of good Gemini matches."
        else:
            verdict = "Weak/no correlation — NLP is NOT a reliable gating signal for Gemini."
        print(f"Interpretation   : {verdict}")
    print(sep)

    # ── CSV output ─────────────────────────────────────────────────────────────
    fieldnames = [
        "match_result_id", "job_title", "company",
        "nlp_score", "gemini_score", "delta",
    ]
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nResults saved to: {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
