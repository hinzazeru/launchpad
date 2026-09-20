#!/usr/bin/env python3
"""Greenhouse spike: measure real yield against the incumbent Bright Data pipeline.

Task 4 of ``tasks/tasks-greenhouse-source-spike.md``. Produces the go/no-go
number the decision gate turns on: **net-new Canadian PM roles per week** that
Greenhouse finds and Bright Data does not.

    python scripts/spike_greenhouse_yield.py --dry-run
    python scripts/spike_greenhouse_yield.py --import

``--dry-run`` (the default) performs zero DB writes. ``--import`` persists the
location-matching jobs, enriches them, matches them against the resume and
saves ``MatchResult`` rows so the roles show up in ``/matches`` alongside
everything else.

Two fairness decisions worth knowing about, because they move the headline
number in opposite directions:

**Both sides get the same title vocabulary.** The DB side runs through
``apply_title_filter`` (role-profile vocabulary — "Sr. Product Mgr" counts).
Filtering Greenhouse titles with a literal keyword substring instead would
hand Bright Data a wider net and inflate Greenhouse's apparent net-new, so the
same include/exclude terms are applied to both.

**Both sides get the same location test.** ``search.py`` filters the DB with
``location ILIKE '%Canada%'``, which misses the "Toronto, ON" rows that make up
most of the Canadian inventory, while the Greenhouse provider uses an alias
list that catches them. Comparing those two directly would understate Bright
Data badly. So the alias test is applied to both, and the strict ILIKE count is
reported alongside it as ``ILIKE-only`` — the gap between the two numbers is a
real (separate) bug in the incumbent filter, not part of this measurement.

**The Bright Data baseline is every non-Greenhouse row**, not
``source = 'brightdata'``. 427 of the local DB's 704 postings carry the legacy
``source = 'api'`` from before the Apify removal; scoping to ``'brightdata'``
alone would discard them and overstate net-new by more than half.
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import or_  # noqa: E402

from src.database.models import JobPosting  # noqa: E402
from src.importers.company_names import canonical_company  # noqa: E402
from src.importers.greenhouse_provider import GreenhouseJobProvider  # noqa: E402
from src.matching.role_profiles import (  # noqa: E402
    normalize_title,
    resolve_profile,
    title_filter_terms,
)
from src.matching.title_filter import apply_title_filter  # noqa: E402

logger = logging.getLogger("greenhouse_spike")

# Mirrors backend/routers/search.py:1466 and :1486 so the baseline is the
# candidate set the app would actually have matched, not a looser one.
BROAD_LOCATIONS = {
    "north america", "south america", "europe", "asia",
    "worldwide", "global", "anywhere",
}
MIN_DESCRIPTION_LENGTH = 200
CANDIDATE_QUERY_LIMIT = 500

# Used only when no enabled ScheduledSearch rows exist (e.g. a fresh DB, or the
# local SQLite copy where both schedules are disabled).
FALLBACK_KEYWORDS = ["Senior Product Manager", "Principal Product Manager"]


# --------------------------------------------------------------------- pure

def job_key(title: Optional[str], company: Optional[str]) -> Tuple[str, str]:
    """Cross-source identity key: (normalized title, canonical company).

    ``normalize_title`` is the role-profile one — lowercase, punctuation
    dropped, whitespace collapsed — so "Sr. Product Manager, Payments" and
    "Sr Product Manager - Payments" converge. It deliberately does NOT strip
    seniority or the trailing team name: "Product Manager, Payments" and
    "Product Manager, Growth" are different jobs, and collapsing them would
    manufacture overlap that isn't there.
    """
    return normalize_title(title), canonical_company(company)


def title_matches_profile(
    title: str,
    include: Sequence[str],
    exclude: Sequence[str],
    fallback_keyword: str,
) -> bool:
    """Python mirror of ``apply_title_filter``'s SQL.

    ``ilike('%term%')`` is a case-insensitive substring test, so this is too.

    Not ``role_profiles.title_matches``: that helper returns True for every
    title when a profile has no vocabulary, while ``apply_title_filter`` falls
    back to a literal keyword ILIKE. Under the ``generic`` profile the first
    behavior would count all ~2000 fetched postings as title matches and report
    a wildly inflated net-new number.
    """
    tl = (title or "").lower()
    if not include:
        return fallback_keyword.lower() in tl
    if not any(term.lower() in tl for term in include):
        return False
    return not any(term.lower() in tl for term in exclude)


def location_matches(location_name: Optional[str], location: Optional[str]) -> bool:
    """Alias-aware location test, shared by both sources.

    Delegates to the provider's own matcher so the Greenhouse side is not being
    judged by a different rule than the one it ships with.
    """
    if not location:
        return True
    return GreenhouseJobProvider._location_matches(
        {"location": {"name": location_name or ""}}, location
    )


def overlap_ratio(overlap: int, total: int) -> float:
    """Overlap as a fraction of Greenhouse's location matches.

    Returns 0.0 for an empty Greenhouse result rather than dividing by zero —
    "nothing found" is not "nothing overlapped", but the report prints the raw
    counts beside it so the distinction stays visible.
    """
    return (overlap / total) if total else 0.0


# ------------------------------------------------------------------ fetching

@dataclass
class BoardFetch:
    """One board's fetch result, with the latency the decision gate asks for."""

    token: str
    jobs: Optional[List[Dict]]
    latency_s: float

    @property
    def status(self) -> str:
        if self.jobs is None:
            return "failed"
        return "empty" if not self.jobs else "ok"


def fetch_all_boards(provider: GreenhouseJobProvider) -> List[BoardFetch]:
    """Fetch every board once, timed individually.

    One pass for all keywords: the boards return a company's entire posting
    list, so keyword filtering is a local operation. Re-fetching per keyword
    would double the wall clock and measure nothing new.
    """
    tokens = [b["token"] for b in provider.boards]

    def timed(token: str) -> BoardFetch:
        start = time.perf_counter()
        jobs = provider._fetch_board(token)
        return BoardFetch(token, jobs, time.perf_counter() - start)

    with ThreadPoolExecutor(max_workers=min(provider.max_workers, len(tokens) or 1)) as ex:
        return list(ex.map(timed, tokens))


def flatten_postings(fetches: Sequence[BoardFetch]) -> List[Dict]:
    """All postings from successful boards, tagged with their board token.

    Tagging matches what ``search_jobs`` does so ``normalize_job`` can resolve
    the curated display name later.
    """
    postings: List[Dict] = []
    for f in fetches:
        for job in f.jobs or []:
            job["_board_token"] = f.token
            postings.append(job)
    return postings


# ----------------------------------------------------------------- selection

@dataclass
class KeywordReport:
    keyword: str
    profile_id: str
    gh_total: int = 0
    gh_title: int = 0
    gh_located: int = 0
    gh_fresh: int = 0
    bd_title: int = 0
    bd_located: int = 0
    bd_strict_located: int = 0
    bd_all_located: int = 0
    overlap: int = 0
    net_new: int = 0
    net_new_fresh: int = 0
    gh_jobs: List[Dict] = field(default_factory=list)
    overlap_by_key: Dict[Tuple[str, str], JobPosting] = field(default_factory=dict)
    fresh_keys: set = field(default_factory=set)


def select_greenhouse(
    postings: Sequence[Dict], keyword: str, location: Optional[str]
) -> Tuple[List[Dict], List[Dict], str]:
    """Apply the role-profile title vocabulary, then the location test."""
    profile = resolve_profile(keyword)
    include, exclude = title_filter_terms(profile)

    title_matches = [
        j for j in postings
        if title_matches_profile(j.get("title") or "", include, exclude, keyword)
    ]
    located = [
        j for j in title_matches
        if location_matches((j.get("location") or {}).get("name"), location)
    ]
    return title_matches, located, profile.id


def select_brightdata(
    session,
    keyword: str,
    location: Optional[str],
    max_age_days: int,
    now: Optional[datetime] = None,
    limit: Optional[int] = CANDIDATE_QUERY_LIMIT,
) -> Tuple[List[JobPosting], List[JobPosting], int]:
    """The incumbent's candidate set, mirroring ``search.py``'s match stage.

    Returns (title matches, alias-location matches, strict-ILIKE count). The
    freshness window, 500-row cap, 200-char description floor and
    newest-posting_date dedup are all copied from there deliberately: a
    baseline built from a *different* candidate set would not be the thing
    Greenhouse has to beat.

    ``max_age_days=0`` disables the window and ``limit=None`` the cap, which is
    how the overlap query runs: "have I already seen this job?" is a question
    about all of Bright Data's history, not about the last four days.
    """
    now = now or datetime.now()

    query = session.query(JobPosting)
    query, _profile = apply_title_filter(query, keyword)
    # Everything that isn't Greenhouse, including the legacy 'api' rows and
    # NULLs — see the module docstring.
    query = query.filter(
        or_(JobPosting.source.is_(None), JobPosting.source != "greenhouse")
    )

    if max_age_days and max_age_days > 0:
        cutoff = now - timedelta(days=max_age_days)
        query = query.filter(
            or_(
                JobPosting.posting_date >= cutoff,
                (JobPosting.posting_date.is_(None)) & (JobPosting.import_date >= cutoff),
            )
        )

    rows = (query.limit(limit) if limit else query).all()
    rows = [
        r for r in rows
        if r.description and len(r.description) >= MIN_DESCRIPTION_LENGTH
    ]

    seen: Dict[Tuple[str, str], JobPosting] = {}
    for row in rows:
        key = (row.title.strip().lower(), row.company.strip().lower())
        incumbent = seen.get(key)
        if incumbent is None or (
            row.posting_date
            and (not incumbent.posting_date or row.posting_date > incumbent.posting_date)
        ):
            seen[key] = row
    rows = list(seen.values())

    located = [r for r in rows if location_matches(r.location, location)]

    strict = 0
    if location and location.strip().lower() not in BROAD_LOCATIONS:
        needle = location.split(",")[-1].strip().lower()
        strict = sum(1 for r in rows if needle in (r.location or "").lower())
    else:
        strict = len(rows)

    return rows, located, strict


def compute_overlap(
    gh_jobs: Sequence[Dict],
    bd_jobs: Sequence[JobPosting],
    provider: GreenhouseJobProvider,
) -> Tuple[Dict[Tuple[str, str], JobPosting], List[Dict]]:
    """Split Greenhouse jobs into (already known to Bright Data, net-new).

    Company names are compared canonically, so "d2l" and "D2L Corporation" are
    one employer. That's the whole reason ``company_names.py`` exists — without
    it every Greenhouse job looks net-new.
    """
    bd_by_key = {job_key(r.title, r.company): r for r in bd_jobs}

    overlap: Dict[Tuple[str, str], JobPosting] = {}
    net_new: List[Dict] = []
    for raw in gh_jobs:
        token = raw.get("_board_token", "")
        company = provider._display_names.get(token, token)
        key = job_key(raw.get("title"), company)
        match = bd_by_key.get(key)
        if match is not None:
            overlap[key] = match
        else:
            net_new.append(raw)
    return overlap, net_new


def fresh_greenhouse_keys(
    provider: GreenhouseJobProvider,
    gh_jobs: Sequence[Dict],
    max_age_days: int,
    now: Optional[datetime] = None,
) -> set:
    """Keys of Greenhouse jobs posted inside the freshness window.

    The gate is denominated per week, so the weekly rate has to compare like
    with like. Greenhouse boards serve a company's entire open req list with no
    age filter, so without this a role posted two months ago counts toward "net
    new this week" purely because Bright Data's windowed candidate set no
    longer contains it.
    """
    if not max_age_days or max_age_days <= 0:
        return {
            job_key(j.get("title"),
                    provider._display_names.get(j.get("_board_token", ""), ""))
            for j in gh_jobs
        }

    cutoff = (now or datetime.now()) - timedelta(days=max_age_days)
    keys = set()
    for raw in gh_jobs:
        posted = provider._parse_date(
            raw.get("first_published") or raw.get("updated_at")
        )
        if posted >= cutoff:
            token = raw.get("_board_token", "")
            keys.add(job_key(raw.get("title"),
                             provider._display_names.get(token, token)))
    return keys


def build_report(
    provider: GreenhouseJobProvider,
    postings: Sequence[Dict],
    session,
    keyword: str,
    location: Optional[str],
    max_age_days: int,
) -> KeywordReport:
    gh_title, gh_located, profile_id = select_greenhouse(postings, keyword, location)

    # Two Bright Data queries, answering two different questions. The windowed
    # one is what the app would match today; the unwindowed one is what the app
    # has *ever* seen, which is what "net-new" actually means.
    bd_title, bd_located, bd_strict = select_brightdata(
        session, keyword, location, max_age_days
    )
    _all_title, bd_all_located, _ = select_brightdata(
        session, keyword, location, 0, limit=None
    )

    overlap, net_new = compute_overlap(gh_located, bd_all_located, provider)
    fresh_keys = fresh_greenhouse_keys(provider, gh_located, max_age_days)
    net_new_keys = {
        job_key(j.get("title"),
                provider._display_names.get(j.get("_board_token", ""),
                                            j.get("_board_token", "")))
        for j in net_new
    }

    return KeywordReport(
        keyword=keyword,
        profile_id=profile_id,
        gh_total=len(postings),
        gh_title=len(gh_title),
        gh_located=len(gh_located),
        gh_fresh=len(fresh_keys),
        bd_title=len(bd_title),
        bd_located=len(bd_located),
        bd_strict_located=bd_strict,
        bd_all_located=len(bd_all_located),
        overlap=len(overlap),
        net_new=len(net_new),
        net_new_fresh=len(net_new_keys & fresh_keys),
        gh_jobs=list(gh_located),
        overlap_by_key=overlap,
        fresh_keys=fresh_keys,
    )


# ----------------------------------------------------------------- reporting

def render_report(
    provider: GreenhouseJobProvider,
    fetches: Sequence[BoardFetch],
    reports: Sequence[KeywordReport],
    location: Optional[str],
    max_age_days: int,
    wall_clock_s: float,
) -> str:
    ok = [f for f in fetches if f.status == "ok"]
    empty = [f for f in fetches if f.status == "empty"]
    failed = [f for f in fetches if f.status == "failed"]

    lines: List[str] = []
    add = lines.append

    add("=" * 72)
    add("GREENHOUSE SPIKE — YIELD vs BRIGHT DATA")
    add("=" * 72)
    add(f"Location filter : {location or '(none)'}")
    add(f"Freshness window: {max_age_days} days (Bright Data side only)")
    add(f"Wall clock      : {wall_clock_s:.1f}s")
    add("")

    add("-" * 72)
    add("BOARDS")
    add("-" * 72)
    add(
        f"{len(fetches)} configured — {len(ok)} returned postings, "
        f"{len(empty)} live but empty, {len(failed)} failed"
    )
    if ok:
        slowest = sorted(ok, key=lambda f: f.latency_s, reverse=True)
        median = sorted(f.latency_s for f in ok)[len(ok) // 2]
        add(f"Latency: median {median:.2f}s, slowest {slowest[0].token} {slowest[0].latency_s:.2f}s")
    if empty:
        add(f"Empty : {', '.join(sorted(f.token for f in empty))}")
    if failed:
        add(f"Failed: {', '.join(sorted(f.token for f in failed))}")
    add("")
    add(f"{'board':<22}{'postings':>10}{'latency':>10}  status")
    for f in sorted(fetches, key=lambda f: len(f.jobs or []), reverse=True):
        count = "-" if f.jobs is None else str(len(f.jobs))
        add(f"{f.token:<22}{count:>10}{f.latency_s:>9.2f}s  {f.status}")
    add("")

    for r in reports:
        add("-" * 72)
        add(f"KEYWORD: {r.keyword}   (role profile: {r.profile_id})")
        add("-" * 72)
        add(f"  Greenhouse  postings fetched    {r.gh_total:>6}")
        add(f"              title matches       {r.gh_title:>6}")
        add(f"              location matches    {r.gh_located:>6}")
        add(f"              posted last {max_age_days}d      {r.gh_fresh:>6}")
        add(f"  Bright Data candidates now      {r.bd_located:>6}   (last {max_age_days}d)")
        add(
            f"              ILIKE-only          {r.bd_strict_located:>6}"
            f"   <- what search.py actually filters on"
        )
        add(f"              all history         {r.bd_all_located:>6}   <- overlap is checked against this")
        add("")
        add(f"  Overlap                         {r.overlap:>6}"
            f"   ({overlap_ratio(r.overlap, r.gh_located):.0%} of Greenhouse)")
        add(f"  Net-new, all ages               {r.net_new:>6}")
        add(f"  NET-NEW, posted last {max_age_days}d     {r.net_new_fresh:>6}   <-- the gate number")
        if r.net_new:
            add("")
            for raw in sorted(r.gh_jobs, key=lambda j: j.get("title") or ""):
                token = raw.get("_board_token", "")
                company = provider._display_names.get(token, token)
                key = job_key(raw.get("title"), company)
                flag = " " if key in r.overlap_by_key else "*"
                loc = (raw.get("location") or {}).get("name", "")
                add(f"   {flag} {(raw.get('title') or '')[:38]:<38} "
                    f"{company[:16]:<16} {loc[:22]}")
            add("     (* = net-new)")
        add("")

    located_keys, overlap_keys = aggregate_keys(provider, reports)
    fresh_keys: set = set()
    for r in reports:
        fresh_keys |= r.fresh_keys
    total_gh = len(located_keys)
    total_overlap = len(overlap_keys)
    total_net_new = total_gh - total_overlap
    weekly_net_new = len((located_keys - overlap_keys) & fresh_keys)
    baseline = max(r.bd_all_located for r in reports) if reports else 0

    profiles = {r.profile_id for r in reports}
    add("=" * 72)
    add("DECISION GATE")
    add("=" * 72)
    if len(reports) > 1 and len(profiles) == 1:
        add(f"NOTE: all {len(reports)} keywords resolve to the same role profile "
            f"('{profiles.pop()}'), so their per-keyword sections above are")
        add("      identical by construction. Totals below are deduplicated.")
        add("")
    add(f"Distinct Greenhouse location matches : {total_gh}")
    add(f"Bright Data baseline (all history)   : {baseline}")
    add(f"Overlap with Bright Data             : {total_overlap} "
        f"({overlap_ratio(total_overlap, total_gh):.0%})")
    add(f"Distinct net-new, all ages           : {total_net_new}")
    add(f"NET-NEW posted in last {max_age_days}d          : {weekly_net_new}"
        f"   <-- the per-week rate the gate is written against")
    add("")
    add("Verdict: " + gate_verdict(
        weekly_net_new, overlap_ratio(total_overlap, total_gh), baseline
    ))
    add("=" * 72)
    return "\n".join(lines)


def gate_verdict(net_new: int, overlap_pct: float, baseline_size: int = 1) -> str:
    """The thresholds from Task 6, written down before the numbers were seen.

    ``baseline_size`` guards the whole gate. With zero Bright Data candidates
    every Greenhouse job is net-new by construction and overlap is 0% — which
    reads as a resounding GO while measuring nothing at all. That is exactly
    what a local SQLite copy produces, so refuse to rule rather than emit a
    number the gate would act on.
    """
    if baseline_size == 0:
        return (
            "INCONCLUSIVE — the Bright Data baseline is empty, so 100% net-new "
            "and 0% overlap are arithmetic, not evidence. Point DATABASE_URL at "
            "production Postgres and re-run."
        )
    if overlap_pct > 0.70:
        return (
            f"STOP — {overlap_pct:.0%} overlap. Same jobs, different pipe; the value "
            "is second-source resilience, not new listings."
        )
    if net_new >= 10:
        return "GO — clearly additive. Build the multi-source roadmap."
    if net_new >= 3:
        return (
            "MARGINAL — keep Greenhouse as a secondary source only. "
            "Skip the registry, hand-maintain the board list."
        )
    return "NO-GO — not worth further source work. Bright Data stays primary."


def aggregate_keys(
    provider: GreenhouseJobProvider, reports: Sequence[KeywordReport]
) -> Tuple[set, set]:
    """Union of (located keys, overlapping keys) across all keywords.

    Summing per-keyword counts would double-count: every registered keyword
    currently resolves to the same ``product_manager`` profile, so the keywords
    return identical job sets and a naive sum reports 2x the real yield. The
    gate turns on *distinct roles found*, so the totals are set unions.
    """
    located: set = set()
    overlapping: set = set()
    for r in reports:
        for raw in r.gh_jobs:
            token = raw.get("_board_token", "")
            company = provider._display_names.get(token, token)
            located.add(job_key(raw.get("title"), company))
        overlapping |= set(r.overlap_by_key)
    return located, overlapping


def write_csv(reports: Sequence[KeywordReport], provider: GreenhouseJobProvider,
              path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "keyword", "status", "board", "company", "title", "location",
            "posting_date", "salary", "url", "overlapping_brightdata_job",
        ])
        for r in reports:
            for raw in r.gh_jobs:
                token = raw.get("_board_token", "")
                company = provider._display_names.get(token, token)
                key = job_key(raw.get("title"), company)
                bd = r.overlap_by_key.get(key)
                normalized = provider.normalize_job(raw)
                writer.writerow([
                    r.keyword,
                    "overlap" if bd else "net_new",
                    token,
                    company,
                    raw.get("title") or "",
                    (raw.get("location") or {}).get("name", ""),
                    normalized.get("posting_date", ""),
                    normalized.get("salary", ""),
                    raw.get("absolute_url", ""),
                    f"{bd.title} @ {bd.company}" if bd else "",
                ])
    return path


# ------------------------------------------------------------------ importing

def load_resume(resume_filename: str):
    """Parse a resume from data/resumes/ into the shape ``match_jobs`` expects.

    Mirrors webapp_scheduler.py's STAGE 1 rather than importing it, because
    that logic lives inside a 250-line function with its own perf logging and
    schedule bookkeeping.
    """
    from src.resume.experience import compute_experience_years
    from src.resume.parser import ResumeParser

    path = PROJECT_ROOT / "data" / "resumes" / resume_filename
    if not path.exists():
        raise FileNotFoundError(f"Resume not found: {path}")

    parsed = ResumeParser().parse_auto(path.read_text(encoding="utf-8"))

    skills: List[str] = []
    for category_skills in parsed.skills.values():
        skills.extend(category_skills)

    class ParsedResume:
        def __init__(self):
            self.id = 0
            self.skills = skills
            self.experience_years = compute_experience_years(parsed.roles)
            self.domains = []
            self.job_titles = [r.title for r in parsed.roles if r.title]

    return ParsedResume()


def import_and_match(
    provider: GreenhouseJobProvider,
    reports: Sequence[KeywordReport],
    resume_filename: str,
) -> None:
    """Persist, enrich and match the Greenhouse jobs so they reach /matches.

    Import goes through ``provider.import_jobs``, which reuses the shared
    ``(title, company)`` dedup path — a job Bright Data already found is
    skipped, not duplicated.
    """
    from backend.services.matcher_service import get_job_matcher
    from src.database.db import SessionLocal
    from src.database.models import Resume

    seen: Dict[Tuple[str, str], Dict] = {}
    for r in reports:
        for raw in r.gh_jobs:
            token = raw.get("_board_token", "")
            company = provider._display_names.get(token, token)
            seen.setdefault(job_key(raw.get("title"), company), raw)

    jobs = list(seen.values())
    print(f"\nImporting {len(jobs)} Greenhouse jobs (dedup applied)...")
    imported = provider.import_jobs(jobs, enrich=True)
    print(f"  {imported} new JobPosting rows (the rest were already known)")

    if not imported:
        print("  Nothing new to match.")
        return

    wanted = {
        (n["title"].strip().lower(), n["company"].strip().lower())
        for n in (provider.normalize_job(j) for j in jobs)
    }

    session = SessionLocal()
    try:
        rows = [
            row
            for row in session.query(JobPosting)
            .filter(JobPosting.source == "greenhouse")
            .all()
            if (row.title.strip().lower(), row.company.strip().lower()) in wanted
        ]
        if not rows:
            print("  No Greenhouse rows found to match.")
            return

        resume = load_resume(resume_filename)
        print(f"  Matching {len(rows)} jobs against {resume_filename} "
              f"({len(resume.skills)} skills, {resume.experience_years}y)...")

        effective_resume_id = resume.id
        if effective_resume_id == 0:
            db_resume = session.query(Resume).first()
            if db_resume:
                effective_resume_id = db_resume.id

        matcher = get_job_matcher()
        matches, _stats = matcher.match_jobs(
            resume,
            rows,
            min_score=0.0,
            db_session=session,
            effective_resume_id=effective_resume_id,
        )

        if matches and effective_resume_id > 0:
            matcher.save_match_results(
                db_session=session,
                resume_id=effective_resume_id,
                match_results=matches,
            )
            session.commit()

        print(f"\n  {len(matches)} matches saved. Top scores:")
        for m in matches[:10]:
            print(f"    {m.get('overall_score', 0):>5.1f}  "
                  f"{(m.get('job_title') or '')[:48]:<48} {m.get('company', '')}")
        print("\n  Review them at /matches (filter source=greenhouse).")
    finally:
        session.close()


# ----------------------------------------------------------------------- main

def resolve_keywords(session, explicit: Optional[List[str]]) -> List[str]:
    """Explicit --keyword args, else enabled schedules, else the spike defaults."""
    if explicit:
        return explicit

    from src.database.models import ScheduledSearch

    keywords = [
        s.keyword.strip()
        for s in session.query(ScheduledSearch).filter(ScheduledSearch.enabled.is_(True)).all()
        if s.keyword and s.keyword.strip()
    ]
    if keywords:
        return sorted(set(keywords))

    logger.info("No enabled schedules found; using spike default keywords")
    return list(FALLBACK_KEYWORDS)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Measure Greenhouse yield against the Bright Data baseline.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true",
                      help="report only, zero DB writes (default)")
    mode.add_argument("--import", dest="do_import", action="store_true",
                      help="persist, enrich and match the location-matching jobs")
    parser.add_argument("--keyword", action="append", dest="keywords",
                        help="repeatable; defaults to enabled schedules")
    parser.add_argument("--location", default="Canada")
    parser.add_argument("--max-age-days", type=int, default=None,
                        help="Bright Data freshness window (default: config)")
    parser.add_argument("--max-per-board", type=int, default=1000,
                        help="per-board posting cap (default: effectively uncapped)")
    parser.add_argument("--resume", default=None,
                        help="resume filename in data/resumes/ (--import only)")
    parser.add_argument("--csv", default=None, help="output CSV path")
    parser.add_argument("--verbose", "-v", action="store_true")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    # Quiet the per-job enrichment chatter that would bury the report.
    if not args.verbose:
        logging.getLogger("src").setLevel(logging.WARNING)

    from src.config import get_config
    from src.database.db import SessionLocal, init_db

    # init_db() issues create_all, which is DDL — a write. A dry run must not
    # touch the schema of the production database it is only reading from.
    if args.do_import:
        init_db()
    config = get_config()
    max_age_days = (
        args.max_age_days
        if args.max_age_days is not None
        else config.get("matching.max_job_age_days", 7)
    )

    provider = GreenhouseJobProvider()
    session = SessionLocal()
    try:
        keywords = resolve_keywords(session, args.keywords)
        resume_filename = args.resume
        if resume_filename is None:
            from src.database.models import ScheduledSearch

            schedule = session.query(ScheduledSearch).filter(
                ScheduledSearch.enabled.is_(True)
            ).first() or session.query(ScheduledSearch).first()
            resume_filename = schedule.resume_filename if schedule else "resume_2026.json"

        print(f"Fetching {len(provider.boards)} Greenhouse boards "
              f"for {len(keywords)} keyword(s)...")
        started = time.perf_counter()
        fetches = fetch_all_boards(provider)
        postings = flatten_postings(fetches)

        reports = [
            build_report(provider, postings, session, kw, args.location, max_age_days)
            for kw in keywords
        ]
        wall_clock = time.perf_counter() - started

        print()
        print(render_report(
            provider, fetches, reports, args.location, max_age_days, wall_clock
        ))

        csv_path = Path(args.csv) if args.csv else (
            PROJECT_ROOT / "output"
            / f"greenhouse_spike_{datetime.now():%Y%m%d_%H%M%S}.csv"
        )
        write_csv(reports, provider, csv_path)
        print(f"\nCSV: {csv_path}")
    finally:
        session.close()

    if args.do_import:
        import_and_match(provider, reports, resume_filename)
    else:
        print("\n(dry run — no database writes. Re-run with --import to persist.)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
