"""Aggregate what a seniority tier actually asks for.

Built because a raw count answers nothing. "product management appears 276
times" is uninterpretable until you know Senior roles say it 1,370 times. Every
figure here is therefore meant to be read against a baseline tier, which
`compare()` produces.

Pure functions over already-fetched rows: no database, no HTTP, no LLM. The
Gemini work happens offline in scripts/build_skill_canonical_map.py, whose
output this reads as a plain JSON file.

Three data hazards, each handled once here so no caller has to remember them:

1. `structured_requirements IS NOT NULL` overcounts — 22 of 601 rows hold JSON
   `null`, which passes the SQL check and then fails `.get()`.
2. `min_years` is mixed-type across rows (int and str).
3. Raw skill strings fragment badly — 579 roles produced 1,313 distinct
   must-have strings, with `communication` (64) and `communication skills` (29)
   counted separately.
"""

import json
import logging
import threading
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
CANONICAL_MAP_PATH = _DATA_DIR / "skill_canonical_map.json"
RESPONSIBILITY_THEMES_PATH = _DATA_DIR / "responsibility_themes.json"

_cache_lock = threading.Lock()
_canonical_map: Optional[Dict[str, str]] = None
_theme_map: Optional[Dict[str, str]] = None


# --- mapping files -------------------------------------------------------------

def _load_json_map(path: Path, label: str) -> Dict[str, str]:
    """Load a {raw: canonical} map. A missing file is not an error.

    Absent or broken, aggregation still runs on raw strings — degraded, never
    broken. The map is an improvement to the output, not a dependency of it.
    """
    if not path.exists():
        logger.info("%s not found at %s; using raw strings", label, path)
        return {}
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Could not read %s (%s); using raw strings", label, e)
        return {}
    if not isinstance(data, dict):
        logger.warning("%s is not a JSON object; using raw strings", label)
        return {}
    return {
        str(k).strip().lower(): str(v).strip()
        for k, v in data.items()
        if k and v
    }


def load_canonical_map(force_reload: bool = False) -> Dict[str, str]:
    global _canonical_map
    with _cache_lock:
        if _canonical_map is None or force_reload:
            _canonical_map = _load_json_map(CANONICAL_MAP_PATH, "skill canonical map")
        return _canonical_map


def load_themes(force_reload: bool = False) -> List[Dict[str, Any]]:
    """Responsibility themes as [{name, keywords}].

    Keyword matching rather than a {raw: theme} lookup, because 33,071 of the
    35,707 responsibility strings in the corpus are unique sentences — only
    1,688 ever repeat. A per-string map would miss essentially everything and
    would need regenerating for every new posting; keywords generalise.
    """
    global _theme_map
    with _cache_lock:
        if _theme_map is not None and not force_reload:
            return _theme_map
        themes: List[Dict[str, Any]] = []
        if RESPONSIBILITY_THEMES_PATH.exists():
            try:
                data = json.loads(RESPONSIBILITY_THEMES_PATH.read_text())
                for t in (data.get("themes") if isinstance(data, dict) else data) or []:
                    name = str(t.get("name", "")).strip()
                    kws = [str(k).strip().lower() for k in (t.get("keywords") or []) if k]
                    if name and kws:
                        themes.append({"name": name, "keywords": kws})
            except (json.JSONDecodeError, OSError, AttributeError) as e:
                logger.warning("Could not read responsibility themes (%s)", e)
        else:
            logger.info("Responsibility themes not found at %s", RESPONSIBILITY_THEMES_PATH)
        _theme_map = themes
        return _theme_map


def classify_responsibility(text: str, themes: Optional[List[Dict[str, Any]]] = None) -> List[str]:
    """Themes a responsibility matches. May be several, or none.

    Deliberately multi-label: "define product vision and align stakeholders"
    genuinely belongs to both strategy and stakeholder themes, and forcing a
    single winner would understate both.
    """
    if not text:
        return []
    lowered = str(text).lower()
    themes = load_themes() if themes is None else themes
    return [t["name"] for t in themes if any(kw in lowered for kw in t["keywords"])]


def canonicalise(skill: str, mapping: Optional[Dict[str, str]] = None) -> str:
    """Fold a raw skill string to its canonical form.

    An unmapped string passes through lowercased rather than being dropped, so
    a partial map degrades the output gradually instead of silently losing the
    long tail.
    """
    if not skill:
        return ""
    key = str(skill).strip().lower()
    if not key:
        return ""
    mapping = load_canonical_map() if mapping is None else mapping
    return mapping.get(key, key)


# --- parsing -------------------------------------------------------------------

def parse_requirements(raw: Any) -> Optional[dict]:
    """Return the requirements dict, or None if this row has nothing usable.

    Guards hazard 1: a JSON `null` column reads as Python None but satisfies
    `IS NOT NULL` in SQL, so type must be checked rather than presence.
    """
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, (str, bytes)):
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


def coerce_years(value: Any) -> Optional[float]:
    """Guards hazard 2. Returns None for anything non-numeric or implausible."""
    if value is None or value == "":
        return None
    try:
        years = float(value)
    except (TypeError, ValueError):
        return None
    # A job asking 0 or 60 years is an extraction error, not a data point.
    if not 0 < years <= 40:
        return None
    return years


def percentiles(values: List[float]) -> Dict[str, Optional[float]]:
    """p25 / median / p75 plus range. Empty input yields Nones, never a crash."""
    if not values:
        return {"p25": None, "median": None, "p75": None, "min": None, "max": None, "n": 0}
    ordered = sorted(values)
    n = len(ordered)

    def at(fraction: float) -> float:
        return ordered[min(int(fraction * n), n - 1)]

    return {
        "p25": at(0.25),
        "median": at(0.50),
        "p75": at(0.75),
        "min": ordered[0],
        "max": ordered[-1],
        "n": n,
    }


# --- profile -------------------------------------------------------------------

def build_profile(rows: List[Any], top_n: int = 15) -> Dict[str, Any]:
    """Aggregate a cohort.

    Args:
        rows: objects exposing `.title` and `.structured_requirements`.
        top_n: how many entries to keep per ranked list.

    Skills are counted once per posting: a description repeating "product
    strategy" three times is one role wanting it, not three.
    """
    mapping = load_canonical_map()
    themes = load_themes()

    years: List[float] = []
    must, nice, domains, focus, theme_counts = Counter(), Counter(), Counter(), Counter(), Counter()
    gemini_seniority = Counter()
    usable = 0
    resp_total = 0
    resp_classified = 0

    for row in rows:
        data = parse_requirements(getattr(row, "structured_requirements", None))
        if data is None:
            continue
        usable += 1

        y = coerce_years(data.get("min_years"))
        if y is not None:
            years.append(y)

        if data.get("role_focus"):
            focus[str(data["role_focus"]).strip().lower()] += 1
        if data.get("seniority_level"):
            gemini_seniority[str(data["seniority_level"]).strip().lower()] += 1

        for field, counter in (("must_have_skills", must), ("nice_to_have_skills", nice)):
            seen = set()
            for item in data.get(field) or []:
                name = item.get("name") if isinstance(item, dict) else item
                canonical = canonicalise(name, mapping)
                if canonical:
                    seen.add(canonical)
            counter.update(seen)

        domains.update({
            str(d).strip().lower() for d in (data.get("required_domains") or []) if d
        })

        seen_themes = set()
        for resp in data.get("key_responsibilities") or []:
            resp_total += 1
            hits = classify_responsibility(resp, themes)
            if hits:
                resp_classified += 1
            seen_themes.update(hits)
        theme_counts.update(seen_themes)

    def ranked(counter: Counter) -> List[Dict[str, Any]]:
        return [
            {"name": name, "count": count, "pct": round(100.0 * count / usable, 1) if usable else 0.0}
            for name, count in counter.most_common(top_n)
        ]

    return {
        "n_postings": len(rows),
        "n_usable": usable,
        "experience": percentiles(years),
        "must_have": ranked(must),
        "nice_to_have": ranked(nice),
        "domains": ranked(domains),
        "responsibility_themes": ranked(theme_counts),
        # Themes are keyword-matched and cover ~45% of statements corpus-wide.
        # Surfaced so the UI can say so rather than implying the section
        # describes every responsibility in the cohort.
        "responsibility_coverage": {
            "classified": resp_classified,
            "total": resp_total,
            "pct": round(100.0 * resp_classified / resp_total, 1) if resp_total else 0.0,
        },
        "focus": {k: v for k, v in focus.most_common()},
        "focus_pct": {
            k: round(100.0 * v / sum(focus.values()), 1) for k, v in focus.most_common()
        } if focus else {},
        "gemini_seniority": {k: v for k, v in gemini_seniority.most_common()},
    }


def compare(tier: Dict[str, Any], baseline: Dict[str, Any], field: str = "must_have") -> Dict[str, Any]:
    """What separates the tier from its baseline.

    Compares by percentage of postings, not raw count — the cohorts differ in
    size by roughly 5x, so raw counts would make every baseline item look
    dominant.
    """
    tier_pct = {i["name"]: i["pct"] for i in tier.get(field, [])}
    base_pct = {i["name"]: i["pct"] for i in baseline.get(field, [])}

    rows = []
    for name, pct in tier_pct.items():
        b = base_pct.get(name, 0.0)
        rows.append({
            "name": name,
            "tier_pct": pct,
            "baseline_pct": b,
            "delta": round(pct - b, 1),
        })
    rows.sort(key=lambda r: r["delta"], reverse=True)

    return {
        "distinctive_to_tier": [r for r in rows if r["delta"] > 0][:10],
        "shared": [r for r in rows if abs(r["delta"]) <= 2.0][:10],
        "stronger_in_baseline": sorted(
            [
                {
                    "name": n,
                    "tier_pct": tier_pct.get(n, 0.0),
                    "baseline_pct": p,
                    "delta": round(tier_pct.get(n, 0.0) - p, 1),
                }
                for n, p in base_pct.items()
            ],
            key=lambda r: r["delta"],
        )[:10],
    }
