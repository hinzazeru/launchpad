"""Detect silent drift in matching scores.

Matching runs on `gemini-3-flash-preview`. Preview models change or disappear
without notice, and the entire calibration is tuned to this one — validated
seniority bands (senior ~71, principal ~84, exec ~98) and the 0.85 high-match
threshold. A model swap would move every score at once, and nothing in the
system would say so: alerts would simply get quieter or noisier and look like
the job market moving.

This project has already been bitten by exactly that. Commit b4fe360 pinned a
preview model to GA and churned 86% of extracted domains; it was found weeks
later, by hand.

The canary re-scores a **fixed** set of jobs on a schedule and compares against
a stored baseline. Same jobs, same resume, same prompt — so any score movement
is the model, not the data.

Everything here is pure apart from `select_canary_jobs`, which only reads.
"""

import json
import logging
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

CANARY_SET_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "canary_jobs.json"

DEFAULT_SET_SIZE = 20

# Drift thresholds. Chosen against observed run-to-run noise: Gemini is not
# deterministic even at temperature 0, so a small mean delta is normal and
# alerting on it would train you to ignore the alert.
DEFAULT_MEAN_DELTA_ALERT = 5.0   # points, absolute
DEFAULT_MAX_DELTA_ALERT = 15.0   # any single job moving this far
DEFAULT_CROSSING_ALERT = 3       # jobs crossing the high-match threshold


def load_canary_set(path: Optional[Path] = None) -> List[Dict[str, str]]:
    """The pinned canary set as [{title, company}].

    Identified by (title, company) rather than job_id so the same set resolves
    in local SQLite and production Postgres, where ids differ. That pair is
    already the corpus dedup key.
    """
    path = path or CANARY_SET_PATH
    if not path.exists():
        logger.info("Canary set not found at %s", path)
        return []
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Could not read canary set (%s)", e)
        return []
    entries = data.get("jobs") if isinstance(data, dict) else data
    out = []
    for e in entries or []:
        if isinstance(e, dict) and e.get("title") and e.get("company"):
            out.append({"title": str(e["title"]), "company": str(e["company"])})
    return out


def resolve_canary_jobs(db, canary_set: List[Dict[str, str]]) -> Tuple[List[Any], List[Dict[str, str]]]:
    """Map the pinned set to live JobPosting rows.

    Returns (found, missing). A job deleted from the corpus is reported rather
    than silently shrinking the set — a canary quietly measuring 3 jobs instead
    of 20 is worse than one that says so.
    """
    from src.database.models import JobPosting

    found, missing = [], []
    for entry in canary_set:
        job = (
            db.query(JobPosting)
            .filter(JobPosting.title == entry["title"], JobPosting.company == entry["company"])
            .first()
        )
        if job is not None:
            found.append(job)
        else:
            missing.append(entry)
    return found, missing


def select_canary_jobs(db, size: int = DEFAULT_SET_SIZE) -> List[Dict[str, str]]:
    """Pick a stratified sample to pin as the canary set.

    Spread across the score range rather than taking the top N: drift at the
    bottom matters as much as at the top, and a top-only set would miss a model
    that starts scoring everything high. Requires a description long enough to
    be scored the way the real pipeline scores it.
    """
    from src.database.models import JobPosting, MatchResult
    from sqlalchemy import func

    best = (
        db.query(MatchResult.job_id, func.max(MatchResult.match_score).label("score"))
        .group_by(MatchResult.job_id)
        .subquery()
    )
    rows = (
        db.query(JobPosting, best.c.score)
        .join(best, JobPosting.id == best.c.job_id)
        .filter(JobPosting.description.isnot(None))
        .all()
    )
    rows = [(j, s) for j, s in rows if j.description and len(j.description) >= 200]
    if not rows:
        return []

    # Even coverage across score bands.
    bands = [(0, 50), (50, 65), (65, 78), (78, 85), (85, 101)]
    per_band = max(1, size // len(bands))
    picked, seen = [], set()

    for low, high in bands:
        in_band = sorted(
            [(j, s) for j, s in rows if low <= s < high],
            key=lambda t: (-t[1], t[0].id),
        )
        for job, _ in in_band[:per_band]:
            if job.id not in seen:
                seen.add(job.id)
                picked.append(job)

    # Top up from the highest scorers if bands were thin.
    if len(picked) < size:
        for job, _ in sorted(rows, key=lambda t: (-t[1], t[0].id)):
            if job.id not in seen:
                seen.add(job.id)
                picked.append(job)
            if len(picked) >= size:
                break

    return [{"title": j.title, "company": j.company} for j in picked[:size]]


def compare_scores(
    observations: List[Dict[str, Any]],
    high_match_threshold: float = 85.0,
) -> Dict[str, Any]:
    """Summarise one canary run against its baseline.

    `observations` is [{job_id, title, company, score, baseline_score}], where
    either score may be None if that job failed to score.
    """
    paired = [
        o for o in observations
        if o.get("score") is not None and o.get("baseline_score") is not None
    ]
    failed = [o for o in observations if o.get("score") is None]

    deltas = [o["score"] - o["baseline_score"] for o in paired]
    abs_deltas = [abs(d) for d in deltas]

    crossings = []
    for o in paired:
        was_high = o["baseline_score"] >= high_match_threshold
        now_high = o["score"] >= high_match_threshold
        if was_high != now_high:
            crossings.append({
                "title": o.get("title"),
                "company": o.get("company"),
                "baseline_score": o["baseline_score"],
                "score": o["score"],
                "direction": "gained" if now_high else "lost",
            })

    worst = max(paired, key=lambda o: abs(o["score"] - o["baseline_score"]), default=None)

    return {
        "n_compared": len(paired),
        "n_failed": len(failed),
        "mean_delta": round(mean(deltas), 2) if deltas else 0.0,
        "mean_abs_delta": round(mean(abs_deltas), 2) if abs_deltas else 0.0,
        "max_abs_delta": round(max(abs_deltas), 2) if abs_deltas else 0.0,
        "threshold_crossings": crossings,
        "n_crossings": len(crossings),
        "worst_job": {
            "title": worst.get("title"),
            "company": worst.get("company"),
            "baseline_score": worst["baseline_score"],
            "score": worst["score"],
            "delta": round(worst["score"] - worst["baseline_score"], 2),
        } if worst else None,
    }


def assess_drift(
    summary: Dict[str, Any],
    model_changed: bool = False,
    mean_delta_alert: float = DEFAULT_MEAN_DELTA_ALERT,
    max_delta_alert: float = DEFAULT_MAX_DELTA_ALERT,
    crossing_alert: int = DEFAULT_CROSSING_ALERT,
) -> Dict[str, Any]:
    """Decide whether this run warrants an alert, and say why.

    A changed model name always alerts regardless of the numbers — that is the
    event this exists to catch, and catching it before the scores move is
    strictly better than after.
    """
    reasons = []
    if model_changed:
        reasons.append("matching model changed")
    if summary["mean_abs_delta"] >= mean_delta_alert:
        reasons.append(f"mean absolute drift {summary['mean_abs_delta']} >= {mean_delta_alert}")
    if summary["max_abs_delta"] >= max_delta_alert:
        reasons.append(f"a job moved {summary['max_abs_delta']} points")
    if summary["n_crossings"] >= crossing_alert:
        reasons.append(f"{summary['n_crossings']} jobs crossed the high-match threshold")
    if summary["n_compared"] == 0:
        reasons.append("nothing could be compared")

    return {"alert": bool(reasons), "reasons": reasons}


def format_report(
    summary: Dict[str, Any],
    verdict: Dict[str, Any],
    model_name: str,
    baseline_model: Optional[str],
    missing: Optional[List[Dict[str, str]]] = None,
) -> str:
    """Telegram HTML. Sent only when alerting; quiet runs stay quiet."""
    head = "⚠️ Score drift detected" if verdict["alert"] else "✅ Score canary stable"
    lines = [head, ""]

    if verdict["reasons"]:
        for r in verdict["reasons"]:
            lines.append(f"• {r}")
        lines.append("")

    if baseline_model and baseline_model != model_name:
        lines.append(f"Model: {baseline_model} → <b>{model_name}</b>")
    else:
        lines.append(f"Model: {model_name}")

    lines.append(
        f"Compared {summary['n_compared']} jobs · "
        f"mean |Δ| {summary['mean_abs_delta']} · max |Δ| {summary['max_abs_delta']}"
    )

    if summary.get("worst_job"):
        w = summary["worst_job"]
        lines.append(
            f"Largest move: {w['title'][:40]} @ {w['company'][:20]} "
            f"{w['baseline_score']:.0f} → {w['score']:.0f} ({w['delta']:+.0f})"
        )

    for c in summary["threshold_crossings"][:5]:
        arrow = "↑" if c["direction"] == "gained" else "↓"
        lines.append(f"{arrow} {c['title'][:38]} {c['baseline_score']:.0f} → {c['score']:.0f}")

    if summary["n_failed"]:
        lines.append(f"{summary['n_failed']} job(s) failed to score this run")
    if missing:
        lines.append(f"{len(missing)} canary job(s) no longer in the database")

    return "\n".join(lines)


# --- execution -----------------------------------------------------------------

def resolve_model_name(matcher: Any) -> str:
    """The model actually doing the matching.

    JobMatcher delegates to a GeminiMatcher held on `.gemini_matcher`, and only
    that inner object carries `model_name` — reading it off JobMatcher returns
    nothing. Getting this wrong is quietly fatal: an "unknown" recorded every
    week compares equal to itself forever, so a model swap never alerts and the
    canary's primary check is dead while every run still looks healthy.
    """
    for candidate in (getattr(matcher, "gemini_matcher", None), matcher):
        name = getattr(candidate, "model_name", None)
        if name:
            return str(name)
    return "unknown"


def run_canary(db, resume, matcher, high_match_threshold: float = 85.0) -> Dict[str, Any]:
    """Re-score the pinned canary set and compare against the last baseline.

    Baseline is the most recent prior run, not the first: drift accumulating a
    few points a week would never trip a fixed-origin comparison, and comparing
    to "last week" is what catches a step change on the run it happens.

    Scores each job individually and tolerates failures — one bad Gemini call
    must not void the whole check, unlike the search pipeline where a partial
    result would be persisted.

    Returns a dict with `observations`, `summary`, `verdict`, and metadata.
    """
    from src.database.models import ScoreCanaryRun

    canary_set = load_canary_set()
    if not canary_set:
        return {"error": "canary set is empty — run scripts/build_canary_set.py", "observations": []}

    jobs, missing = resolve_canary_jobs(db, canary_set)
    model_name = resolve_model_name(matcher)

    # Baseline = each job's score from the most recent previous run.
    last_run_at = (
        db.query(ScoreCanaryRun.run_at)
        .order_by(ScoreCanaryRun.run_at.desc())
        .limit(1)
        .scalar()
    )
    baseline: Dict[int, float] = {}
    baseline_model = None
    if last_run_at is not None:
        for row in db.query(ScoreCanaryRun).filter(ScoreCanaryRun.run_at == last_run_at).all():
            if row.score is not None:
                baseline[row.job_id] = row.score
            baseline_model = baseline_model or row.model_name

    observations = []
    for job in jobs:
        score, error = None, None
        try:
            result = matcher.match_job(resume, job)
            raw = result.get("overall_score", 0) if isinstance(result, dict) else 0
            # match_job returns 0-1; stored scores are 0-100.
            score = round(float(raw) * 100, 1) if raw <= 1 else round(float(raw), 1)
        except Exception as e:
            error = str(e)[:300]
            logger.warning("Canary job %s failed to score: %s", job.id, error)

        observations.append({
            "job_id": job.id,
            "title": job.title,
            "company": job.company,
            "score": score,
            "baseline_score": baseline.get(job.id),
            "error": error,
        })

    summary = compare_scores(observations, high_match_threshold)
    model_changed = bool(baseline_model and baseline_model != model_name)
    verdict = assess_drift(summary, model_changed=model_changed)

    return {
        "observations": observations,
        "summary": summary,
        "verdict": verdict,
        "model_name": model_name,
        "baseline_model": baseline_model,
        "is_first_run": last_run_at is None,
        "missing": missing,
        "n_requested": len(canary_set),
    }


def persist_canary_run(db, result: Dict[str, Any], engine_version=None, resume_filename=None) -> int:
    """Write one row per observation. Returns rows written."""
    from datetime import datetime, timezone

    from src.database.models import ScoreCanaryRun

    run_at = datetime.now(timezone.utc)
    rows = 0
    for o in result.get("observations", []):
        db.add(ScoreCanaryRun(
            run_at=run_at,
            job_id=o["job_id"],
            score=o["score"],
            baseline_score=o.get("baseline_score"),
            delta=(round(o["score"] - o["baseline_score"], 2)
                   if o["score"] is not None and o.get("baseline_score") is not None else None),
            model_name=result.get("model_name"),
            engine_version=engine_version,
            resume_filename=resume_filename,
            error_message=o.get("error"),
        ))
        rows += 1
    db.commit()
    return rows
