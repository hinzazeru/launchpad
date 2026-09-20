"""Tests for the Greenhouse yield-measurement script (spike Task 4).

The script produces the go/no-go number, so the things worth testing are the
ones that would silently move that number: overlap detection across differently
spelled company names, the zero-Bright-Data edge case, and the guarantee that
``--dry-run`` writes nothing.

Network is never touched — ``fetch_all_boards`` is the only part that talks to
Greenhouse, and everything downstream of it takes plain dicts.
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.db import Base
from src.database.models import JobPosting
from src.importers.greenhouse_provider import GreenhouseJobProvider
from scripts.spike_greenhouse_yield import (
    BoardFetch,
    aggregate_keys,
    build_report,
    compute_overlap,
    flatten_postings,
    gate_verdict,
    job_key,
    location_matches,
    overlap_ratio,
    select_brightdata,
    select_greenhouse,
    title_matches_profile,
    write_csv,
)

NOW = datetime(2026, 9, 19, 12, 0, 0)
FRESH = NOW - timedelta(days=2)
STALE = NOW - timedelta(days=40)

BOARDS = [
    {"token": "faire", "display_name": "Faire", "notes": ""},
    {"token": "d2l", "display_name": "D2L Corporation", "notes": ""},
    {"token": "dialpad", "display_name": "Dialpad", "notes": ""},
]

# 200+ chars, so these survive the description-length floor on the DB side.
LONG_DESC = "Own the roadmap for a payments platform. " * 8


@pytest.fixture
def provider():
    return GreenhouseJobProvider(boards=BOARDS)


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def gh_job(token, title, location="Toronto, ON", posted=FRESH):
    return {
        "_board_token": token,
        "title": title,
        "location": {"name": location},
        "content": LONG_DESC,
        "absolute_url": f"https://boards.greenhouse.io/{token}/jobs/1",
        "first_published": posted.isoformat(),
        "updated_at": posted.isoformat(),
    }


def add_bd_job(db, *, title, company, location="Toronto, ON",
               source="brightdata", posting_date=FRESH, description=LONG_DESC):
    job = JobPosting(
        title=title,
        company=company,
        location=location,
        description=description,
        posting_date=posting_date,
        import_date=posting_date,
        source=source,
    )
    db.add(job)
    db.commit()
    return job


# ---------------------------------------------------------------- pure bits

class TestJobKey:
    def test_punctuation_and_case_collapse(self):
        assert job_key("Sr. Product Manager", "Faire") == job_key(
            "sr product manager", "faire"
        )

    def test_board_token_and_display_name_converge(self):
        """The reason company_names.py exists — without it, everything is net-new."""
        assert job_key("Product Manager", "d2l") == job_key(
            "Product Manager", "D2L Corporation"
        )

    def test_different_teams_stay_distinct(self):
        assert job_key("Product Manager, Payments", "Faire") != job_key(
            "Product Manager, Growth", "Faire"
        )


class TestTitleMatchesProfile:
    def test_include_term_matches_substring(self):
        assert title_matches_profile(
            "Senior Growth Product Manager", ["product manager"], [], "x"
        )

    def test_exclude_wins_over_include(self):
        assert not title_matches_profile(
            "Software Engineer, Product Manager Tools",
            ["product manager"], ["engineer"], "x",
        )

    def test_empty_include_falls_back_to_literal_keyword(self):
        """Not "match everything" — that would inflate net-new by ~100x."""
        assert title_matches_profile("Senior Product Manager", [], [], "Product Manager")
        assert not title_matches_profile("Staff Designer", [], [], "Product Manager")


class TestLocationMatches:
    @pytest.mark.parametrize("name", ["Toronto, ON", "Vancouver", "Remote - Canada"])
    def test_canadian_cities_match_canada(self, name):
        assert location_matches(name, "Canada")

    def test_us_city_does_not_match_canada(self):
        assert not location_matches("Austin, TX", "Canada")

    def test_no_location_filter_matches_everything(self):
        assert location_matches("Anywhere", None)


class TestOverlapRatio:
    def test_zero_greenhouse_jobs_does_not_divide_by_zero(self):
        assert overlap_ratio(0, 0) == 0.0

    def test_normal_ratio(self):
        assert overlap_ratio(3, 4) == 0.75


class TestGateVerdict:
    def test_high_overlap_stops_regardless_of_net_new(self):
        assert gate_verdict(50, 0.9, baseline_size=100).startswith("STOP")

    def test_ten_net_new_is_go(self):
        assert gate_verdict(10, 0.1, baseline_size=100).startswith("GO")

    def test_three_net_new_is_marginal(self):
        assert gate_verdict(3, 0.1, baseline_size=100).startswith("MARGINAL")

    def test_two_net_new_is_no_go(self):
        assert gate_verdict(2, 0.1, baseline_size=100).startswith("NO-GO")

    def test_empty_baseline_refuses_to_rule(self):
        """An empty baseline makes every job net-new at 0% overlap, which would
        otherwise print a resounding GO off the back of measuring nothing."""
        assert gate_verdict(64, 0.0, baseline_size=0).startswith("INCONCLUSIVE")


class TestAggregateKeys:
    def test_same_job_across_two_keywords_counts_once(self, db, provider):
        """Every keyword resolves to the same profile today, so a naive sum
        reports 2x the real yield."""
        postings = [gh_job("faire", "Senior Product Manager")]
        reports = [
            build_report(provider, postings, db, kw, "Canada", 7)
            for kw in ("Senior Product Manager", "Principal Product Manager")
        ]
        assert sum(r.net_new for r in reports) == 2  # the wrong number
        located, overlapping = aggregate_keys(provider, reports)
        assert len(located) - len(overlapping) == 1  # the right one


# ------------------------------------------------------------------ fetching

class TestFlattenPostings:
    def test_failed_and_empty_boards_contribute_nothing(self):
        fetches = [
            BoardFetch("faire", [{"title": "PM"}], 0.5),
            BoardFetch("d2l", [], 0.2),
            BoardFetch("dialpad", None, 0.1),
        ]
        postings = flatten_postings(fetches)
        assert len(postings) == 1
        assert postings[0]["_board_token"] == "faire"

    def test_board_status_classification(self):
        assert BoardFetch("a", None, 0).status == "failed"
        assert BoardFetch("a", [], 0).status == "empty"
        assert BoardFetch("a", [{"title": "x"}], 0).status == "ok"


# ----------------------------------------------------------------- selection

class TestSelectGreenhouse:
    def test_title_vocabulary_then_location(self, provider):
        postings = [
            gh_job("faire", "Senior Product Manager", "Toronto, ON"),
            gh_job("faire", "Senior Product Manager", "San Francisco, CA"),
            gh_job("d2l", "Staff Software Engineer", "Toronto, ON"),
        ]
        titles, located, profile_id = select_greenhouse(
            postings, "Senior Product Manager", "Canada"
        )
        assert len(titles) == 2
        assert len(located) == 1
        assert profile_id


class TestSelectBrightData:
    def test_excludes_greenhouse_rows(self, db):
        add_bd_job(db, title="Senior Product Manager", company="Faire")
        add_bd_job(db, title="Principal Product Manager", company="Dialpad",
                   source="greenhouse")
        titles, _located, _strict = select_brightdata(
            db, "Senior Product Manager", "Canada", 7, now=NOW
        )
        assert [j.company for j in titles] == ["Faire"]

    def test_includes_legacy_api_source(self, db):
        """427 of the local DB's rows are source='api'. Dropping them would
        overstate net-new by more than half."""
        add_bd_job(db, title="Senior Product Manager", company="Shopify", source="api")
        titles, _located, _strict = select_brightdata(
            db, "Senior Product Manager", "Canada", 7, now=NOW
        )
        assert len(titles) == 1

    def test_stale_jobs_excluded(self, db):
        add_bd_job(db, title="Senior Product Manager", company="Faire",
                   posting_date=STALE)
        titles, _located, _strict = select_brightdata(
            db, "Senior Product Manager", "Canada", 7, now=NOW
        )
        assert titles == []

    def test_short_descriptions_excluded(self, db):
        add_bd_job(db, title="Senior Product Manager", company="Faire",
                   description="too short")
        titles, _located, _strict = select_brightdata(
            db, "Senior Product Manager", "Canada", 7, now=NOW
        )
        assert titles == []

    def test_alias_location_beats_strict_ilike(self, db):
        """"Toronto, ON" is Canadian; search.py's ILIKE '%Canada%' misses it."""
        add_bd_job(db, title="Senior Product Manager", company="Faire",
                   location="Toronto, ON")
        _titles, located, strict = select_brightdata(
            db, "Senior Product Manager", "Canada", 7, now=NOW
        )
        assert len(located) == 1
        assert strict == 0


# ------------------------------------------------------------------- overlap

class TestComputeOverlap:
    def test_seeded_duplicate_is_detected(self, db, provider):
        """The deliberately-seeded duplicate from the task's test list."""
        bd = [add_bd_job(db, title="Senior Product Manager", company="Faire")]
        gh = [gh_job("faire", "Senior Product Manager")]
        overlap, net_new = compute_overlap(gh, bd, provider)
        assert len(overlap) == 1
        assert net_new == []

    def test_duplicate_detected_across_name_spellings(self, db, provider):
        bd = [add_bd_job(db, title="Product Manager", company="D2L Corporation")]
        gh = [gh_job("d2l", "Product Manager")]
        overlap, net_new = compute_overlap(gh, bd, provider)
        assert len(overlap) == 1
        assert net_new == []

    def test_genuinely_new_job_is_net_new(self, db, provider):
        bd = [add_bd_job(db, title="Senior Product Manager", company="Faire")]
        gh = [gh_job("dialpad", "Principal Product Manager")]
        overlap, net_new = compute_overlap(gh, bd, provider)
        assert overlap == {}
        assert len(net_new) == 1

    def test_empty_brightdata_makes_everything_net_new(self, provider):
        gh = [gh_job("faire", "Senior Product Manager")]
        overlap, net_new = compute_overlap(gh, [], provider)
        assert overlap == {}
        assert len(net_new) == 1


# -------------------------------------------------------------------- report

class TestBuildReport:
    def test_fresh_db_with_zero_brightdata_rows(self, db, provider):
        """Task acceptance: handle an empty baseline rather than dividing by zero."""
        postings = [gh_job("faire", "Senior Product Manager")]
        report = build_report(provider, postings, db, "Senior Product Manager",
                              "Canada", 7)
        assert report.bd_located == 0
        assert report.net_new == 1
        assert overlap_ratio(report.overlap, report.gh_located) == 0.0

    def test_counts_split_overlap_and_net_new(self, db, provider):
        add_bd_job(db, title="Senior Product Manager", company="Faire")
        postings = [
            gh_job("faire", "Senior Product Manager"),
            gh_job("dialpad", "Senior Product Manager, Platform"),
            gh_job("faire", "Senior Product Manager", "Austin, TX"),
        ]
        report = build_report(provider, postings, db, "Senior Product Manager",
                              "Canada", 7)
        assert report.gh_title == 3
        assert report.gh_located == 2
        assert report.overlap == 1
        assert report.net_new == 1


class TestFreshnessSymmetry:
    """Greenhouse boards serve every open req regardless of age. Without a
    matching window, a two-month-old posting counts as "net-new this week"
    purely because Bright Data's windowed candidate set no longer holds it."""

    def test_stale_greenhouse_job_excluded_from_weekly_rate(self, db, provider):
        postings = [
            gh_job("faire", "Senior Product Manager", posted=FRESH),
            gh_job("dialpad", "Principal Product Manager", posted=STALE),
        ]
        report = build_report(provider, postings, db, "Senior Product Manager",
                              "Canada", 7)
        assert report.net_new == 2       # both are unknown to Bright Data
        assert report.net_new_fresh == 1  # only one was posted this week

    def test_overlap_uses_full_history_not_the_window(self, db, provider):
        """A job Bright Data found 40 days ago is not net-new, even though it
        has long since fallen out of the 7-day candidate set."""
        add_bd_job(db, title="Senior Product Manager", company="Faire",
                   posting_date=STALE)
        postings = [gh_job("faire", "Senior Product Manager", posted=FRESH)]
        report = build_report(provider, postings, db, "Senior Product Manager",
                              "Canada", 7)
        assert report.bd_located == 0      # outside the window
        assert report.bd_all_located == 1  # but present in history
        assert report.overlap == 1
        assert report.net_new_fresh == 0


class TestDryRunWritesNothing:
    def test_report_and_csv_leave_row_counts_unchanged(self, db, provider, tmp_path):
        """Task acceptance: --dry-run performs zero DB writes."""
        add_bd_job(db, title="Senior Product Manager", company="Faire")
        before = db.query(JobPosting).count()

        postings = [
            gh_job("faire", "Senior Product Manager"),
            gh_job("dialpad", "Principal Product Manager"),
        ]
        reports = [
            build_report(provider, postings, db, kw, "Canada", 7)
            for kw in ("Senior Product Manager", "Principal Product Manager")
        ]
        write_csv(reports, provider, tmp_path / "spike.csv")

        assert db.query(JobPosting).count() == before

    def test_csv_labels_every_row(self, db, provider, tmp_path):
        import csv as csv_module

        add_bd_job(db, title="Senior Product Manager", company="Faire")
        postings = [
            gh_job("faire", "Senior Product Manager"),
            gh_job("dialpad", "Senior Product Manager, Platform"),
        ]
        report = build_report(provider, postings, db, "Senior Product Manager",
                              "Canada", 7)
        path = write_csv([report], provider, tmp_path / "spike.csv")

        rows = list(csv_module.DictReader(path.open()))
        assert {r["status"] for r in rows} == {"overlap", "net_new"}
        # Display name, never the board token — that's what dedup compares.
        assert "Faire" in {r["company"] for r in rows}
