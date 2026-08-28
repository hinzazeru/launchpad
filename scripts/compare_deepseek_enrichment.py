"""Compare DeepSeek against Gemini on the three enrichment workloads.

Enrichment is the highest-volume LLM work in this codebase: three calls per
imported job (domain extraction, summarization, requirements extraction), all on
the cheap lite model. If DeepSeek matches Gemini's quality here it is the best
cost-saving swap available; if it doesn't, we've learned that for the price of a
few cents.

Both providers are given the SAME prompt constants from
``src.integrations.gemini_client``, so this measures the models, not prompt
engineering.

Read-only: pulls jobs from the database, writes nothing back. Results go to
``output/deepseek_comparison_<timestamp>.csv`` plus a stdout summary.

Usage::

    ./venv/bin/python scripts/compare_deepseek_enrichment.py --limit 10
    ./venv/bin/python scripts/compare_deepseek_enrichment.py --limit 10 --task domains

Requires ``DEEPSEEK_API_KEY`` in ``.env`` or the environment.

A note on token budgets — this is the trap in this comparison:
``deepseek-v4-flash`` is a REASONING model. It spends tokens thinking before
emitting content, drawn from the same ``max_tokens`` budget, and those tokens are
billed as output. Handing it Gemini's ``domain_max_tokens: 300`` produced an
EMPTY response with ``finish_reason: stop`` in testing — a silent failure that
looks like success. DeepSeek is therefore given a larger budget, reasoning tokens
are reported separately, and empty-content responses are counted as failures
rather than scored as valid.
"""

import argparse
import csv
import json
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.integrations.gemini_client import (  # noqa: E402
    DOMAIN_EXTRACTION_PROMPT,
    JOB_SUMMARY_PROMPT,
    REQUIREMENTS_EXTRACTION_PROMPT,
    clean_json_text,
)

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-v4-flash"

# Gemini's configured caps, from config.yaml. DeepSeek gets a much larger budget
# because reasoning tokens come out of the same allowance — see module docstring.
GEMINI_CAPS = {"domains": 300, "summary": 200, "requirements": 2048}
DEEPSEEK_CAPS = {"domains": 1500, "summary": 1200, "requirements": 4000}

# USD per 1M tokens, verified against provider pricing pages 2026-08-27.
# DeepSeek is quoted at cache-miss PEAK rates (the pessimistic case); off-peak
# is exactly half, and peak is only 01:00-04:00 and 06:00-10:00 UTC Mon-Fri.
#
# The gemini-3.1-flash-lite rates below were previously set to 0.10/0.40 — the
# rates for gemini-2.5-flash-lite, a different model. That understated Gemini's
# cost ~3x and produced a "DeepSeek is 4.36x more expensive" conclusion that was
# simply wrong (the real figure is 1.45x at peak, 0.73x off-peak). Re-verify
# these before quoting any cost ratio.
PRICING = {
    "deepseek-v4-flash": {"input": 0.44, "output": 1.32},
    "deepseek-v4-flash-offpeak": {"input": 0.22, "output": 0.66},
    "gemini-3.1-flash-lite": {"input": 0.25, "output": 1.50},
}


@dataclass
class CallResult:
    provider: str
    task: str
    job_id: int
    ok: bool = False
    latency_s: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    cost_usd: float = 0.0
    error: str = ""
    output: str = ""
    domains: List[str] = field(default_factory=list)
    invalid_domains: List[str] = field(default_factory=list)


def _load_env() -> None:
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        # Last assignment wins, matching shell `source` semantics. setdefault()
        # would take the FIRST occurrence instead, which silently picked up a
        # leftover placeholder line and produced 401s that looked like a bad key.
        os.environ[key.strip()] = value.strip().strip("\"'")


def _valid_domain_keys() -> set:
    data = json.loads((PROJECT_ROOT / "data" / "domain_expertise.json").read_text())
    return {k for cat in data["domains"].values() for k in cat}


def _cost(model: str, inp: int, out: int) -> float:
    rates = PRICING.get(model)
    if not rates:
        return 0.0
    return (inp / 1_000_000) * rates["input"] + (out / 1_000_000) * rates["output"]


def build_prompt(task: str, job) -> str:
    """Identical prompt text for both providers — that's the point."""
    description = job.description or ""
    if task == "domains":
        return DOMAIN_EXTRACTION_PROMPT.format(
            company=job.company or "Unknown",
            title=job.title or "Unknown",
            description=description[:8000],
        )
    if task == "summary":
        return JOB_SUMMARY_PROMPT.format(
            company=job.company or "Unknown",
            title=job.title or "Unknown",
            description=description[:8000],
        )
    if task == "requirements":
        return REQUIREMENTS_EXTRACTION_PROMPT.format(
            title=job.title or "Unknown",
            company=job.company or "Unknown",
            description=description[:10000],
        )
    raise ValueError(f"unknown task: {task}")


# ----------------------------------------------------------------- providers


def call_deepseek(task: str, prompt: str, job_id: int, valid_keys: set,
                  thinking: str = "disabled") -> CallResult:
    import requests

    r = CallResult(provider="deepseek", task=task, job_id=job_id)
    body = {
        "model": DEEPSEEK_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": DEEPSEEK_CAPS[task],
        "temperature": 0.1,
        "stream": False,
        # Thinking defaults to ENABLED, and reasoning tokens are drawn from
        # max_tokens AND billed as output. On a first run with the default,
        # 11/30 calls returned empty content with reasoning_tokens pinned
        # exactly at the cap, and reasoning was 96% of all output tokens.
        # These three tasks are structured extraction — they do not benefit
        # from reasoning, so it is off unless explicitly requested.
        "thinking": {"type": thinking},
    }
    if task != "summary":
        body["response_format"] = {"type": "json_object"}

    start = time.perf_counter()
    try:
        resp = requests.post(
            f"{DEEPSEEK_BASE_URL}/chat/completions",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {os.environ['DEEPSEEK_API_KEY']}",
            },
            json=body,
            timeout=180,
        )
        r.latency_s = round(time.perf_counter() - start, 2)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        r.latency_s = round(time.perf_counter() - start, 2)
        r.error = f"{type(e).__name__}: {e}"[:200]
        return r

    usage = data.get("usage", {})
    r.input_tokens = usage.get("prompt_tokens", 0)
    r.output_tokens = usage.get("completion_tokens", 0)
    r.reasoning_tokens = (usage.get("completion_tokens_details") or {}).get(
        "reasoning_tokens", 0
    )
    r.cost_usd = _cost(DEEPSEEK_MODEL, r.input_tokens, r.output_tokens)

    content = (data["choices"][0]["message"].get("content") or "").strip()
    if not content:
        # The silent failure this harness exists to catch: reasoning consumed
        # the whole budget, so finish_reason says "stop" but nothing was said.
        r.error = f"empty content (reasoning_tokens={r.reasoning_tokens})"
        return r

    r.output = content
    _finish(r, task, content, valid_keys)
    return r


def call_gemini(task: str, prompt: str, job_id: int, valid_keys: set) -> CallResult:
    from google.genai import types

    from src.config import get_config
    from src.integrations.gemini_client import GeminiDomainExtractor

    extractor = GeminiDomainExtractor()
    model = get_config().get("gemini.extractor.model", "gemini-3.1-flash-lite")

    r = CallResult(provider="gemini", task=task, job_id=job_id)
    cfg = types.GenerateContentConfig(
        temperature=0.1,
        max_output_tokens=GEMINI_CAPS[task],
        **({"response_mime_type": "application/json"} if task != "summary" else {}),
    )

    start = time.perf_counter()
    try:
        resp = extractor._rate_limiter.call_with_retry(
            extractor.client.models.generate_content,
            model=model,
            contents=prompt,
            config=cfg,
        )
        r.latency_s = round(time.perf_counter() - start, 2)
    except Exception as e:
        r.latency_s = round(time.perf_counter() - start, 2)
        r.error = f"{type(e).__name__}: {e}"[:200]
        return r

    meta = getattr(resp, "usage_metadata", None)
    if meta:
        r.input_tokens = getattr(meta, "prompt_token_count", 0) or 0
        r.output_tokens = getattr(meta, "candidates_token_count", 0) or 0
    r.cost_usd = _cost(model, r.input_tokens, r.output_tokens)

    try:
        content = (resp.text or "").strip()
    except Exception:
        parts = []
        for cand in resp.candidates or []:
            for part in getattr(cand.content, "parts", []) or []:
                if getattr(part, "text", None):
                    parts.append(part.text)
        content = "".join(parts).strip()

    if not content:
        r.error = "empty content"
        return r

    r.output = content
    _finish(r, task, content, valid_keys)
    return r


def _finish(r: CallResult, task: str, content: str, valid_keys: set) -> None:
    """Parse and validate, shared so both providers are judged identically."""
    if task == "summary":
        r.ok = True
        return

    try:
        parsed = json.loads(clean_json_text(content))
    except Exception as e:
        r.error = f"parse failure: {type(e).__name__}"[:200]
        return

    r.ok = True
    if task == "domains":
        found = parsed.get("domains") or []
        r.domains = [d for d in found if isinstance(d, str)]
        # Objective correctness signal: a key either exists in the taxonomy or
        # it is a hallucination the matching engine will silently never match.
        r.invalid_domains = [d for d in r.domains if d not in valid_keys]


# --------------------------------------------------------------------- main


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=10, help="jobs to sample (default 10)")
    ap.add_argument(
        "--task",
        choices=["domains", "summary", "requirements", "all"],
        default="all",
    )
    ap.add_argument(
        "--thinking",
        choices=["disabled", "enabled"],
        default="disabled",
        help="DeepSeek reasoning mode (default disabled; see call_deepseek)",
    )
    args = ap.parse_args()

    _load_env()
    if not os.environ.get("DEEPSEEK_API_KEY"):
        print("DEEPSEEK_API_KEY not found in .env or environment", file=sys.stderr)
        return 1

    from src.database.db import SessionLocal
    from src.database.models import JobPosting

    valid_keys = _valid_domain_keys()
    tasks = ["domains", "summary", "requirements"] if args.task == "all" else [args.task]

    session = SessionLocal()
    try:
        jobs = (
            session.query(JobPosting)
            .filter(JobPosting.description.isnot(None))
            .order_by(JobPosting.posting_date.desc())
            .limit(args.limit)
            .all()
        )
        jobs = [j for j in jobs if len(j.description or "") > 400]
    finally:
        session.close()

    if not jobs:
        print("No jobs with usable descriptions found.", file=sys.stderr)
        return 1

    print(f"Comparing {len(tasks)} task(s) across {len(jobs)} jobs "
          f"= {len(tasks) * len(jobs) * 2} API calls\n")

    results: List[CallResult] = []
    for task in tasks:
        for i, job in enumerate(jobs, 1):
            prompt = build_prompt(task, job)
            print(f"  [{task}] {i}/{len(jobs)} {job.title[:44]:44}", end=" ", flush=True)
            g = call_gemini(task, prompt, job.id, valid_keys)
            d = call_deepseek(task, prompt, job.id, valid_keys, args.thinking)
            results.extend([g, d])
            print(f"gemini={'ok' if g.ok else 'FAIL'} "
                  f"deepseek={'ok' if d.ok else 'FAIL'}")

    _report(results, tasks, valid_keys)
    _write_csv(results)
    return 0


def _report(results: List[CallResult], tasks: List[str], valid_keys: set) -> None:
    print("\n" + "=" * 78)
    for task in tasks:
        print(f"\n### {task}")
        print(f"{'provider':10} {'ok':>6} {'fail':>5} {'p50 s':>7} {'tok in':>8} "
              f"{'tok out':>8} {'reason':>7} {'cost $':>9}")
        for provider in ("gemini", "deepseek"):
            rs = [r for r in results if r.task == task and r.provider == provider]
            if not rs:
                continue
            ok = [r for r in rs if r.ok]
            lat = sorted(r.latency_s for r in rs)
            p50 = lat[len(lat) // 2] if lat else 0
            print(f"{provider:10} {len(ok):>6} {len(rs) - len(ok):>5} {p50:>7.2f} "
                  f"{sum(r.input_tokens for r in rs):>8} "
                  f"{sum(r.output_tokens for r in rs):>8} "
                  f"{sum(r.reasoning_tokens for r in rs):>7} "
                  f"{sum(r.cost_usd for r in rs):>9.5f}")

        errs = [r for r in results if r.task == task and not r.ok]
        for r in errs[:6]:
            print(f"   ! {r.provider} job {r.job_id}: {r.error}")

        if task == "domains":
            print("\n   domain agreement (job: gemini | deepseek)")
            for job_id in dict.fromkeys(r.job_id for r in results if r.task == task):
                g = next((r for r in results if r.task == task
                          and r.provider == "gemini" and r.job_id == job_id), None)
                d = next((r for r in results if r.task == task
                          and r.provider == "deepseek" and r.job_id == job_id), None)
                if not g or not d:
                    continue
                gs, ds = set(g.domains), set(d.domains)
                mark = "=" if gs == ds else "~" if gs & ds else "X"
                bad = ""
                if g.invalid_domains or d.invalid_domains:
                    bad = f"  INVALID g={g.invalid_domains} d={d.invalid_domains}"
                print(f"   {mark} {job_id:5}: {sorted(gs)} | {sorted(ds)}{bad}")

    total_g = sum(r.cost_usd for r in results if r.provider == "gemini")
    total_d = sum(r.cost_usd for r in results if r.provider == "deepseek")
    print("\n" + "=" * 78)
    print(f"TOTAL COST  gemini ${total_g:.5f}   deepseek ${total_d:.5f}")
    if total_g:
        print(f"DeepSeek is {total_d / total_g:.2f}x Gemini's cost on this sample "
              f"(DeepSeek priced at PEAK; off-peak halves it)")
    print("Reasoning tokens are billed as output — they are in the totals above.")


def _write_csv(results: List[CallResult]) -> None:
    out_dir = PROJECT_ROOT / "output"
    out_dir.mkdir(exist_ok=True)
    path = out_dir / f"deepseek_comparison_{datetime.now():%Y%m%d_%H%M%S}.csv"
    rows = [asdict(r) for r in results]
    for row in rows:
        row["domains"] = ", ".join(row["domains"])
        row["invalid_domains"] = ", ".join(row["invalid_domains"])
        row["output"] = (row["output"] or "")[:2000]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\nFull results: {path}")


if __name__ == "__main__":
    raise SystemExit(main())
