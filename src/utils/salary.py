"""Salary string parsing utilities.

Converts stored salary strings (e.g. "$120,000-$150,000", "$80K-$100K",
"$60-$70/hr") into numeric (min_annual, max_annual) tuples for analysis.
"""

import re
from typing import Optional, Tuple

HOURS_PER_YEAR = 2080


def parse_salary_string(s: str) -> Optional[Tuple[float, float]]:
    """Parse a stored salary string into (min_annual, max_annual).

    Returns None for unparseable strings.
    """
    if not s:
        return None

    s = s.strip()

    # Hourly: "$60-$70/hr", "CA$75-$85/hr", "$75/hr"
    hr_match = re.match(
        r'(?:(?:CA|US)\$?)?\$?(\d+(?:\.\d+)?)\s*[-–]?\s*(?:\$|(?:CA|US)\$)?(\d+(?:\.\d+)?)?\s*/\s*hr',
        s, re.IGNORECASE
    )
    if hr_match:
        low = float(hr_match.group(1))
        high = float(hr_match.group(2)) if hr_match.group(2) else low
        return (low * HOURS_PER_YEAR, high * HOURS_PER_YEAR)

    # K format: "$80K-$100K", "$120K"
    k_match = re.match(
        r'(?:(?:CA|US)\$?)?\$?(\d+)\s*[kK]\s*(?:[-–]|to)\s*(?:\$|(?:CA|US)\$)?(\d+)\s*[kK]',
        s, re.IGNORECASE
    )
    if not k_match:
        # Single K: "$120K"
        k_match = re.match(
            r'(?:(?:CA|US)\$?)?\$?(\d+)\s*[kK]',
            s, re.IGNORECASE
        )
    if k_match:
        low = float(k_match.group(1)) * 1000
        high = float(k_match.group(2)) * 1000 if k_match.lastindex and k_match.lastindex >= 2 and k_match.group(2) else low
        if 40_000 <= low <= 500_000:
            return (low, high)

    # Full numbers: "$120,000-$150,000", "$120,000", "$152,000 to $190,000 CAD"
    full_match = re.match(
        r'(?:(?:CA|US)\$?)?\$?([\d,]+)(?:\.\d+)?\s*(?:[-–]|to)\s*(?:\$|(?:CA|US)\$)?([\d,]+)(?:\.\d+)?',
        s, re.IGNORECASE
    )
    if not full_match:
        # Single value: "$120,000"
        full_match = re.match(
            r'(?:(?:CA|US)\$?)?\$?([\d,]+)(?:\.\d+)?',
            s, re.IGNORECASE
        )
    if full_match:
        low = float(full_match.group(1).replace(',', ''))
        has_high = full_match.lastindex and full_match.lastindex >= 2 and full_match.group(2)
        high = float(full_match.group(2).replace(',', '')) if has_high else low
        if 40_000 <= low <= 500_000:
            return (low, high)

    return None


def classify_country(location: str) -> str:
    """Classify a job location string into Canada, US, or Other."""
    if not location:
        return "Other"
    loc = location.lower()

    canada_keywords = [
        "canada", "british columbia", "ontario", "alberta", "quebec",
        "manitoba", "saskatchewan", "nova scotia", "new brunswick",
        "newfoundland", "prince edward", ", bc,", ", ab,", ", on,",
        ", qc,", ", bc", ", ab", ", on", ", qc", ", mb", ", sk",
        "toronto", "vancouver", "montreal", "calgary", "ottawa",
        "edmonton", "winnipeg",
    ]
    if any(kw in loc for kw in canada_keywords):
        return "Canada"

    us_keywords = [
        "united states", ", us", "u.s.", "usa",
        "california", "new york", "texas", "washington",
        ", ny", ", ca", ", tx", ", wa", ", il", ", ma", ", fl",
        ", ga", ", pa", ", co", ", nc", ", va", ", oh", ", nj",
        ", az", ", or", ", mn", ", wi", ", mi", ", md", ", ct",
        "san francisco", "seattle", "boston", "chicago", "austin",
        "denver", "atlanta", "los angeles",
    ]
    if any(kw in loc for kw in us_keywords):
        return "US"

    return "Other"
