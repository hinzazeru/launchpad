"""Greenhouse job board provider.

Unlike Bright Data, Greenhouse has no aggregate search endpoint. Each company
publishes its own board at::

    https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true

so we fetch every posting from each curated board and filter client-side. That
sidesteps full-text-search noise entirely — there is no search engine to fool,
just a flat list of one company's real openings.

The API is public and unauthenticated: no key, no cost, no rate limit we've hit.
That is the whole reason this provider exists — Bright Data is currently both a
single point of failure and a per-call expense.

Board tokens rot. A survey of 900 tokens from a public ATS directory found only
~56% still live, so ``_fetch_board`` fails soft and the caller gets
``boards_failed`` rather than an exception. See ``data/greenhouse_boards.json``
for the curated list and how it was selected.
"""

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests

from src.importers.base_provider import JobProvider

logger = logging.getLogger(__name__)

GREENHOUSE_URL = "https://boards-api.greenhouse.io/v1/boards/{board}/jobs"

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BOARDS_FILE = PROJECT_ROOT / "data" / "greenhouse_boards.json"

# Mirrors brightdata_provider's mapping so experience_required means the same
# thing regardless of which provider produced the row.
_SENIORITY_YEARS = {
    "entry": 0,
    "associate": 0,
    "intern": 0,
    "junior": 1,
    "mid": 3,
    "senior": 5,
    "sr.": 5,
    "lead": 7,
    "staff": 7,
    "principal": 10,
    "director": 12,
    "vp": 15,
    "head of": 12,
    "chief": 15,
}

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_YEARS_RE = re.compile(r"(\d+)\+?\s*(?:years?|yrs?)", re.IGNORECASE)


def _word_in(word: str, text: str) -> bool:
    """Word-boundary containment, so "product" does not match "Production".

    Both arguments are expected lowercase. Falls back to a plain substring test
    for words containing regex-significant characters (e.g. "c++"), where a
    boundary assertion would never fire.
    """
    if not word:
        return False
    if not word[0].isalnum() or not word[-1].isalnum():
        return word in text
    return re.search(rf"\b{re.escape(word)}\b", text) is not None


def strip_html(html: str) -> str:
    """Greenhouse returns descriptions as escaped HTML in the `content` field."""
    if not html:
        return ""
    import html as html_module

    text = html_module.unescape(html)
    text = _HTML_TAG_RE.sub(" ", text)
    return _WS_RE.sub(" ", text).strip()


def load_boards(path: Optional[Path] = None) -> List[Dict]:
    """Load the curated board list. Returns [{token, display_name, notes}]."""
    path = path or BOARDS_FILE
    with open(path) as f:
        return json.load(f)["boards"]


class GreenhouseJobProvider(JobProvider):
    """Fetches jobs from a curated set of company Greenhouse boards."""

    def __init__(
        self,
        boards: Optional[List[Dict]] = None,
        timeout: int = 20,
        max_workers: int = 8,
    ):
        self.boards = boards if boards is not None else load_boards()
        self.timeout = timeout
        self.max_workers = max_workers
        # Populated by the most recent search; the spike script reports these.
        self.boards_checked: List[str] = []
        self.boards_failed: List[str] = []
        self.boards_empty: List[str] = []
        self._display_names = {b["token"]: b["display_name"] for b in self.boards}

    @property
    def provider_name(self) -> str:
        return "greenhouse"

    # ------------------------------------------------------------------ fetch

    def _fetch_board(self, token: str) -> Optional[List[Dict]]:
        """Fetch one board's postings.

        Returns None on failure and [] for a live-but-empty board — the caller
        needs to tell "broken token" apart from "company has no openings", which
        a bare [] would conflate.
        """
        try:
            resp = requests.get(
                GREENHOUSE_URL.format(board=token),
                params={"content": "true"},
                timeout=self.timeout,
                headers={"User-Agent": "launchpad/0.1"},
            )
            resp.raise_for_status()
            return resp.json().get("jobs", [])
        except Exception as e:
            logger.warning(f"Greenhouse board '{token}' failed: {e}")
            return None

    def search_jobs(
        self,
        keywords: Optional[str] = None,
        location: Optional[str] = None,
        max_results: int = 50,
        title_include: Optional[List[str]] = None,
        title_exclude: Optional[List[str]] = None,
    ) -> List[Dict]:
        """Synchronous search across all configured boards.

        `max_results` is a **per-board** cap, not a global one. A shared global
        cap starves companies late in iteration order purely by list position:
        the first big board would consume the entire budget.
        """
        self.boards_checked, self.boards_failed, self.boards_empty = [], [], []

        raw_by_board: Dict[str, Optional[List[Dict]]] = {}
        tokens = [b["token"] for b in self.boards]
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(tokens) or 1)) as ex:
            for token, jobs in zip(tokens, ex.map(self._fetch_board, tokens)):
                raw_by_board[token] = jobs

        query_words = [w.lower() for w in (keywords or "").split() if w]
        include = [t.lower() for t in (title_include or [])]
        exclude = [t.lower() for t in (title_exclude or [])]

        results: List[Dict] = []
        # Filtering stays sequential in board order so output is deterministic
        # even though fetching was concurrent.
        for token in tokens:
            raw = raw_by_board.get(token)
            if raw is None:
                self.boards_failed.append(token)
                continue
            if not raw:
                self.boards_empty.append(token)
                continue
            self.boards_checked.append(token)

            kept = 0
            for job in raw:
                title = job.get("title") or ""
                tl = title.lower()

                # ALL query words must appear, not any. "product manager" with
                # any-semantics matches "Engineering Manager" and "Product
                # Designer", which floods the result set with roles that were
                # never going to fit. Word order is not required, so "Manager,
                # Product Growth" still matches.
                #
                # Matched on word boundaries, not substrings: plain `in` lets
                # "product" match "Production Manager", which is a genuinely
                # different job.
                if query_words and not all(_word_in(w, tl) for w in query_words):
                    continue
                if include and not any(inc in tl for inc in include):
                    continue
                if exclude and any(exc in tl for exc in exclude):
                    continue
                if location and not self._location_matches(job, location):
                    continue

                job["_board_token"] = token
                results.append(job)
                kept += 1
                if kept >= max_results:
                    break

        logger.info(
            f"Greenhouse: {len(self.boards_checked)} boards checked, "
            f"{len(self.boards_empty)} empty, {len(self.boards_failed)} failed, "
            f"{len(results)} jobs matched"
        )
        return results

    async def search_jobs_async(
        self,
        keywords: Optional[str] = None,
        location: str = "United States",
        job_type: Optional[str] = None,
        max_results: int = 50,
        posted_when: str = "Past 24 hours",
        experience_level: Optional[str] = None,
        work_arrangement: Optional[str] = None,
        country_code: Optional[str] = None,
        company_name: Optional[str] = None,
        search_radius: Optional[str] = None,
        split_calls: bool = True,
        progress_callback: Optional[callable] = None,
    ) -> List[Dict]:
        """Async wrapper satisfying the JobProvider interface.

        Several parameters are LinkedIn-shaped and have no Greenhouse analogue
        (`job_type`, `posted_when`, `experience_level`, `search_radius`,
        `split_calls`); they are accepted and ignored rather than faked, since
        the board API exposes no such filters. `location` and `work_arrangement`
        are applied client-side.
        """
        import asyncio

        if progress_callback:
            await progress_callback(
                f"Fetching {len(self.boards)} Greenhouse boards...", 0.1
            )

        loc = location
        if work_arrangement and work_arrangement.lower() == "remote":
            loc = None  # remote roles are listed from anywhere

        jobs = await asyncio.to_thread(
            self.search_jobs,
            keywords=keywords,
            location=loc,
            max_results=max_results,
        )

        if progress_callback:
            await progress_callback(
                f"Greenhouse: {len(jobs)} jobs from "
                f"{len(self.boards_checked)} boards", 1.0
            )
        return jobs

    @staticmethod
    def _location_matches(job: Dict, location: str) -> bool:
        """Substring match against Greenhouse's free-text location name.

        Greenhouse has no structured country field, so 'Canada' has to match
        'Toronto, ON' too — hence the region alias list rather than a bare
        substring test.
        """
        name = ((job.get("location") or {}).get("name") or "").lower()
        if not name:
            return False
        loc = location.lower().strip()

        aliases = {
            "canada": ["canada", "toronto", "vancouver", "montreal", "ottawa",
                       "calgary", "waterloo", "kitchener", "edmonton", "ontario",
                       "british columbia", "quebec", ", on", ", bc", ", qc", ", ab"],
            "united states": ["united states", "usa", ", us", "remote - us"],
            "remote": ["remote", "anywhere", "distributed"],
        }
        for key, terms in aliases.items():
            if key in loc:
                return any(t in name for t in terms)
        return loc in name

    # -------------------------------------------------------------- normalize

    def normalize_job(self, job_data: Dict) -> Dict:
        """Normalize a Greenhouse posting to LaunchPad's standard shape."""
        token = job_data.get("_board_token", "")
        # Always the curated display name — never the board token. The dedup key
        # is (title, company), and a token like "leagueinc" would never match
        # Bright Data's "League Inc.", silently creating a duplicate row.
        company = self._display_names.get(token, token)

        title = job_data.get("title") or ""
        description = strip_html(job_data.get("content") or "")

        normalized: Dict = {
            "title": title,
            "company": company,
            "location": (job_data.get("location") or {}).get("name", ""),
            "description": description,
            "url": job_data.get("absolute_url", ""),
            "source": self.provider_name,
            # Populated later by Gemini enrichment, same as Bright Data.
            "required_skills": [],
        }

        normalized["posting_date"] = self._parse_date(
            job_data.get("first_published") or job_data.get("updated_at")
        )

        experience = self._infer_experience(title, description)
        if experience is not None:
            normalized["experience_required"] = experience

        salary = self._extract_salary(job_data, description)
        if salary:
            normalized["salary"] = salary

        if description:
            from src.matching.skill_extractor import extract_domain_requirements

            domains = extract_domain_requirements(description)
            if domains.get("required"):
                normalized["required_domains"] = domains["required"]

        return normalized

    @staticmethod
    def _parse_date(raw: Optional[str]) -> datetime:
        """Greenhouse returns ISO 8601. Falls back to now() rather than dropping
        the posting — matching brightdata_provider's behavior so freshness
        filtering treats both sources consistently."""
        if raw:
            try:
                dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
                return dt.replace(tzinfo=None) if dt.tzinfo else dt
            except (ValueError, TypeError):
                logger.warning(f"Unparseable Greenhouse date: {raw!r}")
        return datetime.now(timezone.utc).replace(tzinfo=None)

    @staticmethod
    def _infer_experience(title: str, description: str) -> Optional[float]:
        """Explicit '5+ years' in the description wins; otherwise infer from the
        title's seniority word. Returns None when neither is present rather than
        guessing a number the posting never stated."""
        match = _YEARS_RE.search(description or "")
        if match:
            return float(match.group(1))

        tl = (title or "").lower()
        # Longest keys first so "mid-senior" doesn't match on bare "senior",
        # and "sr." beats a stray "director" later in the title.
        for level in sorted(_SENIORITY_YEARS, key=len, reverse=True):
            if level in tl:
                return float(_SENIORITY_YEARS[level])
        return None

    @staticmethod
    def _extract_salary(job_data: Dict, description: str) -> str:
        """Prefer Greenhouse's structured pay range (published under pay-
        transparency laws); fall back to regex over the FULL description.

        The regex runs before any truncation because comp figures usually sit
        late in a long JD, after the company blurb and requirements.
        """
        ranges = job_data.get("pay_input_ranges") or []
        if ranges:
            r = ranges[0]
            lo, hi = r.get("min_cents"), r.get("max_cents")
            currency = r.get("currency_type", "USD")
            if lo and hi:
                return f"{currency} {lo // 100:,} - {hi // 100:,}"

        if description:
            from src.matching.skill_extractor import extract_salary_from_description

            return extract_salary_from_description(description) or ""
        return ""

    def stats(self) -> Tuple[List[str], List[str], List[str]]:
        """(checked, empty, failed) from the most recent search."""
        return self.boards_checked, self.boards_empty, self.boards_failed

    # ----------------------------------------------------------------- import

    def import_jobs(self, jobs: List[Dict], enrich: bool = True) -> int:
        """Persist normalized jobs, reusing the same dedup path as Bright Data.

        `import_jobs` is called by the search pipeline but is absent from the
        `JobProvider` ABC — it exists only on BrightDataJobProvider. Implemented
        here with matching semantics so the two providers stay interchangeable
        rather than silently depending on that gap.

        Dedup is the shared `(lower(title), lower(company))` key, so a job
        already imported from Bright Data is detected here too — provided
        `normalize_job` set `company` from the curated display name rather than
        the board token (see `src.importers.company_names`).
        """
        from src.database.crud import get_existing_jobs_for_repost_check
        from src.database.db import SessionLocal
        from src.database.models import JobPosting
        from src.importers.validators import normalize_job_data, validate_job_posting

        session = SessionLocal()
        imported = 0
        new_postings: List = []
        seen_in_batch = set()

        try:
            normalized_jobs = []
            for job in jobs:
                nj = normalize_job_data(self.normalize_job(job))
                key = (nj["title"].strip().lower(), nj["company"].strip().lower())
                if key in seen_in_batch:
                    continue
                ok, error = validate_job_posting(nj, check_freshness=False)
                if not ok:
                    logger.debug(f"Skipping invalid Greenhouse job: {error}")
                    continue
                seen_in_batch.add(key)
                normalized_jobs.append((nj, key))

            existing = (
                get_existing_jobs_for_repost_check(session, [k for _, k in normalized_jobs])
                if normalized_jobs
                else {}
            )

            for nj, key in normalized_jobs:
                if key in existing:
                    # Already known — most likely the same posting Bright Data
                    # already found. Left untouched; the spike counts it as
                    # overlap rather than re-importing or bumping repost state.
                    continue
                new_postings.append(
                    JobPosting(
                        title=nj["title"],
                        company=nj["company"],
                        location=nj.get("location", ""),
                        description=nj.get("description", ""),
                        required_skills=nj.get("required_skills", []),
                        experience_required=nj.get("experience_required", 0),
                        posting_date=nj.get("posting_date"),
                        source=nj.get("source", self.provider_name),
                        url=nj.get("url", ""),
                        salary=nj.get("salary"),
                        required_domains=nj.get("required_domains"),
                        domain_extraction_method=(
                            "keyword" if nj.get("required_domains") else None
                        ),
                    )
                )
                imported += 1

            if new_postings:
                try:
                    session.add_all(new_postings)
                    session.commit()
                except Exception as e:
                    session.rollback()
                    if "UNIQUE constraint" in str(e) or "IntegrityError" in type(e).__name__:
                        logger.warning("Bulk insert hit unique constraint, retrying one-by-one")
                        survived = []
                        for jp in new_postings:
                            try:
                                session.add(jp)
                                session.commit()
                                survived.append(jp)
                            except Exception:
                                session.rollback()
                                imported -= 1
                        new_postings = survived
                    else:
                        raise

            if enrich and new_postings:
                gemini_extractor = requirements_extractor = None
                try:
                    from src.integrations.gemini_client import (
                        GeminiDomainExtractor,
                        GeminiRequirementsExtractor,
                    )

                    de = GeminiDomainExtractor()
                    if de.is_available():
                        gemini_extractor = de
                    re_ = GeminiRequirementsExtractor()
                    if re_.is_available():
                        requirements_extractor = re_
                except Exception:
                    pass

                if gemini_extractor or requirements_extractor:
                    from src.importers.enrichment import enrich_jobs_parallel

                    n = enrich_jobs_parallel(
                        new_postings, gemini_extractor, requirements_extractor, session
                    )
                    logger.info(f"Enriched {n}/{len(new_postings)} Greenhouse jobs")

            logger.info(f"Imported {imported} new jobs from Greenhouse")
            return imported

        except Exception as e:
            logger.error(f"Error importing Greenhouse jobs: {e}", exc_info=True)
            session.rollback()
            raise
        finally:
            session.close()
