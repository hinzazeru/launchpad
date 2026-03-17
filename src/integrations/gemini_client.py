"""Gemini API client for LLM-based domain extraction.

This module provides integration with Google's Gemini API for extracting
domain/industry information from job descriptions with higher accuracy
than keyword-based matching.

Usage:
    >>> from src.integrations.gemini_client import GeminiDomainExtractor
    >>> extractor = GeminiDomainExtractor()
    >>> domains = extractor.extract_domains(job_description, company_name)
    >>> print(domains)  # ['fintech', 'b2b_saas', 'banking']
"""

import json
import logging
import re
import time
import threading
from typing import List, Dict, Optional

def clean_json_text(text: str) -> str:
    """Clean JSON text by removing markdown code blocks and fixing common JSON issues.
    
    Handles:
    - Markdown code blocks (```json ... ```)
    - JavaScript-style unquoted property names
    - Trailing commas in arrays/objects
    - Unterminated strings (truncated responses)
    - Missing commas between array/object elements
    - Control characters within strings
    
    Falls back to json_repair library for complex cases.
    """
    if not text:
        return ""
        
    text = text.strip()
    
    # Remove markdown code blocks
    if "```" in text:
        match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
        if match:
            text = match.group(1).strip()
            
    # Find the first { or [ and last } or ]
    # This handles cases where there's text before or after the JSON
    json_start_indices = [text.find(c) for c in ['{', '['] if text.find(c) != -1]
    json_end_indices = [text.rfind(c) for c in ['}', ']'] if text.rfind(c) != -1]
    
    if json_start_indices and json_end_indices:
        start = min(json_start_indices)
        end = max(json_end_indices)
        if start <= end:
            text = text[start : end + 1]
    
    # Try parsing as-is first (fastest path)
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass  # Continue with repairs
    
    # Stage 1: Basic fixes
    text = _apply_basic_json_fixes(text)
    
    # Try parsing after basic fixes
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass  # Continue with more aggressive repairs
    
    # Stage 2: Fix structural issues (unterminated strings, missing commas)
    text = _fix_json_structure(text)
    
    # Try parsing after structural fixes
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass
    
    # Stage 3: Use json_repair library as fallback
    try:
        from json_repair import repair_json
        repaired = repair_json(text, return_objects=False)
        # Validate the repaired JSON
        json.loads(repaired)
        return repaired
    except ImportError:
        logger.warning("json_repair not installed, cannot auto-fix malformed JSON")
    except Exception as e:
        logger.debug(f"json_repair failed: {e}")
    
    # Return the best effort cleaned text
    return text


def _apply_basic_json_fixes(text: str) -> str:
    """Apply basic JSON fixes that are safe and fast."""
    # Fix JavaScript-style unquoted property names: {key: "value"} -> {"key": "value"}
    # Pattern: matches word characters (a-zA-Z0-9_) as keys that aren't already quoted
    text = re.sub(
        r'(?<=[{,])\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:',
        r' "\1":',
        text
    )
    
    # Fix trailing commas before ] or } (common Gemini error)
    text = re.sub(r',\s*([\]}])', r'\1', text)
    
    # Remove control characters that shouldn't be in JSON (except \n, \r, \t)
    # These can cause parsing issues
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)
    
    return text


def _fix_json_structure(text: str) -> str:
    """Fix structural JSON issues like unterminated strings and missing commas."""
    # Fix unterminated strings at end of lines
    # Pattern: line ends with text after ": that doesn't end with ",
    # This handles cases like: "reasoning": "The candidate has strong experience
    lines = text.split('\n')
    fixed_lines = []
    in_string = False
    
    for i, line in enumerate(lines):
        # Count unescaped quotes to track string state
        quote_count = 0
        j = 0
        while j < len(line):
            if line[j] == '"' and (j == 0 or line[j-1] != '\\'):
                quote_count += 1
            j += 1
        
        # If odd number of quotes, we have an unterminated string
        if quote_count % 2 == 1:
            # Check if this is likely a truncated string value
            stripped = line.rstrip()
            if not stripped.endswith(('"', ',', '{', '[', '}', ']', ':')):
                # Try to close the string
                # Look at next line to see if it continues
                if i < len(lines) - 1:
                    next_line = lines[i + 1].strip()
                    # If next line starts with a new key or closing bracket, close this string
                    if (next_line.startswith('"') or 
                        next_line.startswith('}') or 
                        next_line.startswith(']') or
                        re.match(r'^"[^"]+"\s*:', next_line)):
                        line = stripped + '"'
                else:
                    # Last line with unterminated string - close it
                    line = stripped + '"'
        
        fixed_lines.append(line)
    
    text = '\n'.join(fixed_lines)
    
    # Fix missing commas between elements
    # Pattern: "value"\n  "key": or "value"\n  } should have comma
    # Look for: end of string/number/bool/null followed by newline and new element
    text = re.sub(
        r'("|\d|true|false|null)\s*\n(\s*"[^"]+"\s*:)',
        r'\1,\n\2',
        text
    )
    
    # Fix missing commas in arrays: ["item1"\n  "item2"]
    text = re.sub(
        r'("|\d|true|false|null|\]|\})\s*\n(\s*"[^"]*"(?:\s*[,\]\}]|\s*$))',
        r'\1,\n\2',
        text
    )
    
    # Fix missing commas between array elements on same line  
    # Pattern: "item1" "item2" -> "item1", "item2"
    text = re.sub(r'"\s+"(?=[^:]*(?:\]|,|$))', '", "', text)
    
    # Fix missing commas after closing brackets/braces
    text = re.sub(
        r'(\]|\})\s*\n(\s*"[^"]+"\s*:)',
        r'\1,\n\2',
        text
    )
    
    # Ensure proper closing brackets
    # Count brackets to see if we need to close any
    open_braces = text.count('{') - text.count('}')
    open_brackets = text.count('[') - text.count(']')
    
    if open_braces > 0 or open_brackets > 0:
        # Need to close some brackets - add them at the end
        text = text.rstrip()
        # Close arrays first, then objects
        text += ']' * open_brackets
        text += '}' * open_braces
    
    return text

from google import genai
from google.genai import types

from pathlib import Path

from src.config import get_config

logger = logging.getLogger(__name__)


class GeminiRateLimiter:
    """Thread-safe rate limiter for Gemini API calls.

    Enforces minimum spacing between calls and retries with exponential
    backoff on 429 errors. Includes a circuit breaker that stops retrying
    for a cooldown period after repeated 429s, so batch operations fail
    fast instead of blocking the worker for minutes.

    Two-tier rate limiting is supported via the ``upstream`` parameter.
    Per-model limiters should pass the shared API-key-level limiter as
    ``upstream`` so that the combined call rate across all models stays
    within the project's quota.  The key-level limiter itself has no
    upstream (``upstream=None``).

    Call flow for a per-model limiter with an upstream:
        1. upstream._acquire_slot()  — enforce shared per-key minimum gap
        2. self._acquire_slot()      — enforce per-model minimum gap on top
        3. make the API call
    """

    def __init__(
        self,
        min_interval: float = 0.4,
        max_retries: int = 2,
        circuit_breaker_cooldown: float = 120.0,
        upstream: Optional["GeminiRateLimiter"] = None,
    ):
        self._min_interval = min_interval
        self._max_retries = max_retries
        self._last_call_time = 0.0
        self._lock = threading.Lock()
        # Circuit breaker: skip calls entirely after repeated 429s
        self._circuit_open_until = 0.0
        self._circuit_breaker_cooldown = circuit_breaker_cooldown
        # Shared key-level gate (None for the key limiter itself)
        self._upstream = upstream

    @property
    def circuit_open(self) -> bool:
        """Check if circuit breaker is tripped (quota exhausted)."""
        return time.monotonic() < self._circuit_open_until

    def _acquire_slot(self) -> None:
        """Claim one rate-limit slot (thread-safe).

        Blocks until the minimum interval has elapsed since the last slot
        was claimed by any thread using this limiter instance.
        """
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_call_time
            if elapsed < self._min_interval:
                time.sleep(self._min_interval - elapsed)
            self._last_call_time = time.monotonic()

    def wait(self) -> None:
        """Block until both the shared key limit and per-model limit allow the call.

        Waits for the upstream (shared API-key-level limiter) first, then for
        this limiter's own per-model minimum interval.  If there is no upstream,
        only the per-model interval is enforced.
        """
        if self._upstream is not None:
            self._upstream._acquire_slot()
        self._acquire_slot()

    def _trip_circuit_breaker(self) -> None:
        """Open this limiter's circuit breaker for the full cooldown period."""
        self._circuit_open_until = time.monotonic() + self._circuit_breaker_cooldown

    def call_with_retry(self, fn, *args, **kwargs):
        """Call fn with rate limiting and retry on 429 errors.

        If the circuit breaker is open (recent 429 quota exhaustion),
        raises immediately without making an API call.  When quota is
        exhausted after all retries, trips both this limiter's circuit
        breaker AND the upstream (shared key-level) circuit breaker so
        that all models pause during the cooldown.

        Args:
            fn: Callable that makes the Gemini API call
            *args, **kwargs: Passed to fn

        Returns:
            The result of fn()

        Raises:
            The last exception if all retries are exhausted or circuit is open
        """
        if self.circuit_open:
            raise Exception("Gemini rate limit circuit breaker open — skipping call (quota exhausted)")
        if self._upstream is not None and self._upstream.circuit_open:
            raise Exception("Gemini API key quota exhausted (shared circuit breaker open)")

        last_error = None
        for attempt in range(self._max_retries + 1):
            self.wait()
            try:
                return fn(*args, **kwargs)
            except Exception as e:
                error_str = str(e)
                if '429' in error_str or 'Resource exhausted' in error_str or 'RESOURCE_EXHAUSTED' in error_str:
                    last_error = e
                    if attempt < self._max_retries:
                        backoff = min(2 ** attempt * 5, 30)  # 5s, 10s, cap 30s
                        logger.warning(
                            f"Gemini 429 rate limit (attempt {attempt + 1}/{self._max_retries + 1}), "
                            f"backing off {backoff}s"
                        )
                        time.sleep(backoff)
                    else:
                        # All retries exhausted — trip both local and key-level circuit breakers
                        self._trip_circuit_breaker()
                        if self._upstream is not None:
                            self._upstream._trip_circuit_breaker()
                        logger.warning(
                            f"Gemini quota exhausted after {self._max_retries + 1} attempts. "
                            f"Circuit breaker open for {self._circuit_breaker_cooldown}s — "
                            f"subsequent calls will be skipped."
                        )
                else:
                    raise
        raise last_error


# Explicit prefix list for known thinking/reasoning model names.
# These have lower RPM limits and need a slower per-call interval.
# Config override: gemini.rate_limit.thinking_model_prefixes (list of strings)
# Use model-name PREFIXES rather than broad version substrings — "2.5" would
# also match hypothetical names like "gemini-1.25-pro" and can't distinguish
# gemini-2.5-flash from a future gemini-2.5-flash-lite that may not be a thinking model.
_DEFAULT_THINKING_MODEL_PREFIXES = [
    "gemini-3-flash",       # Gemini 3 Flash (and preview variants)
    "gemini-3-pro",         # Gemini 3 Pro (and preview variants)
    "gemini-3.1-pro",       # Gemini 3.1 Pro (and preview variants)
    "gemini-2.5-flash",     # Legacy (deprecating June 2026)
    "gemini-2.5-pro",       # Legacy (deprecating June 2026)
    "gemini-exp-",          # experimental models are typically thinking variants
]


def _is_thinking_model(model_name: str) -> bool:
    """Return True if model_name is a known thinking/reasoning model.

    Uses an explicit prefix allowlist (config: gemini.rate_limit.thinking_model_prefixes)
    rather than broad version-number substrings. When a new thinking model is released,
    add its prefix to the config or the default list above — a wrong classification
    will produce a logged warning, not a silent misconfiguration.
    """
    try:
        config = get_config()
        prefixes = config.get(
            "gemini.rate_limit.thinking_model_prefixes",
            _DEFAULT_THINKING_MODEL_PREFIXES,
        )
    except Exception:
        prefixes = _DEFAULT_THINKING_MODEL_PREFIXES
    is_thinking = any(model_name.startswith(p) for p in prefixes)
    if is_thinking:
        logger.debug(f"Model '{model_name}' classified as thinking model (slower rate limit)")
    return is_thinking


_rate_limiter_cache: Dict[str, GeminiRateLimiter] = {}
_rate_limiter_cache_lock = threading.Lock()

# Shared per-API-key limiter (lazily created on first use, never at import time).
# ALL per-model limiters gate through this first, so the combined call rate across
# all models never exceeds the project's quota.
_shared_key_limiter: Optional[GeminiRateLimiter] = None
_shared_key_limiter_lock = threading.Lock()


def _get_shared_key_limiter() -> GeminiRateLimiter:
    """Return (or lazily create) the shared per-API-key rate limiter.

    The Gemini quota is per project/API key, not per model.  A single shared
    limiter ensures that the combined rate from all models (enrichment flash +
    matching thinking) stays within the key's RPM cap.

    Config: ``gemini.rate_limit.global_min_interval_ms`` (default 400 ms = 150 RPM).
    """
    global _shared_key_limiter
    with _shared_key_limiter_lock:
        if _shared_key_limiter is None:
            try:
                config = get_config()
                min_interval_ms = config.get("gemini.rate_limit.global_min_interval_ms", 400)
                max_retries = config.get("gemini.rate_limit.max_retries", 2)
                cooldown = config.get("gemini.rate_limit.circuit_breaker_cooldown_s", 120.0)
            except Exception:
                min_interval_ms, max_retries, cooldown = 400, 2, 120.0
            _shared_key_limiter = GeminiRateLimiter(
                min_interval=min_interval_ms / 1000.0,
                max_retries=int(max_retries),
                circuit_breaker_cooldown=float(cooldown),
                upstream=None,  # The key limiter is the root — no further upstream
            )
            logger.debug(
                f"Gemini shared key limiter: global_min_interval={min_interval_ms}ms, "
                f"max_retries={max_retries}, cooldown={cooldown}s"
            )
        return _shared_key_limiter


def get_rate_limiter(model_name: str) -> GeminiRateLimiter:
    """Get (or create) a per-model rate limiter backed by the shared key-level gate.

    Each model gets its own limiter calibrated to the model's RPM limit.
    All limiters share a common upstream (``_get_shared_key_limiter()``) so
    the combined call rate across every model stays within the API key's quota.

    Args:
        model_name: The Gemini model name (e.g. "gemini-2.0-flash")

    Returns:
        A GeminiRateLimiter calibrated for that model, backed by the shared key limiter.
    """
    with _rate_limiter_cache_lock:
        if model_name not in _rate_limiter_cache:
            _rate_limiter_cache[model_name] = _build_rate_limiter(model_name)
        return _rate_limiter_cache[model_name]


def _build_rate_limiter(model_name: str) -> GeminiRateLimiter:
    """Create a per-model rate limiter with config-driven parameters.

    The returned limiter gates through the shared key-level limiter (upstream)
    first, then enforces the model-specific minimum interval on top.
    """
    try:
        config = get_config()
        is_thinking = _is_thinking_model(model_name)

        if is_thinking:
            min_interval_ms = config.get("gemini.rate_limit.thinking_min_interval_ms", 2000)
        else:
            min_interval_ms = config.get("gemini.rate_limit.min_interval_ms", 400)

        max_retries = config.get("gemini.rate_limit.max_retries", 2)
        cooldown = config.get("gemini.rate_limit.circuit_breaker_cooldown_s", 120.0)
        model_type = "thinking" if is_thinking else "flash"
        limiter = GeminiRateLimiter(
            min_interval=min_interval_ms / 1000.0,
            max_retries=int(max_retries),
            circuit_breaker_cooldown=float(cooldown),
            upstream=_get_shared_key_limiter(),
        )
        logger.debug(
            f"Gemini rate limiter ({model_type}, {model_name}): "
            f"min_interval={min_interval_ms}ms, max_retries={max_retries}, cooldown={cooldown}s"
        )
        return limiter
    except Exception as e:
        logger.warning(f"Failed to read rate limiter config for {model_name}, using defaults: {e}")
        default_interval = 2.0 if _is_thinking_model(model_name) else 0.4
        return GeminiRateLimiter(
            min_interval=default_interval,
            max_retries=2,
            circuit_breaker_cooldown=120.0,
            upstream=_get_shared_key_limiter(),
        )


def _load_valid_domains() -> List[str]:
    """Load valid domains dynamically from domain_expertise.json.

    This ensures VALID_DOMAINS stays in sync with the domain configuration file.
    Falls back to a minimal default list if file not found.
    """
    config_path = Path(__file__).parent.parent.parent / "data" / "domain_expertise.json"

    try:
        with open(config_path) as f:
            data = json.load(f)

        domains = []
        for category in data.get("domains", {}).values():
            domains.extend(category.keys())

        if domains:
            logger.debug(f"Loaded {len(domains)} valid domains from domain_expertise.json")
            return domains

    except FileNotFoundError:
        logger.warning(f"domain_expertise.json not found at {config_path}, using defaults")
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse domain_expertise.json: {e}, using defaults")

    # Fallback to minimal default list
    return [
        "ecommerce", "fintech", "banking", "b2b_saas", "healthcare",
        "ai_ml", "devops", "salesforce", "stripe"
    ]


# Valid domain keys that can be extracted (loaded from domain_expertise.json)
VALID_DOMAINS = _load_valid_domains()

JOB_SUMMARY_PROMPT = """Summarize this job posting in 2-3 concise sentences. Focus on:
1. The core responsibilities and what the person will actually DO
2. Key requirements or qualifications that stand out
3. What makes this role unique or interesting

**Company:** {company}
**Job Title:** {title}

**Job Description:**
{description}

**Instructions:**
- Be specific and informative, avoid generic phrases
- Focus on the most important aspects that would help a job seeker decide if this role is right for them
- Keep it under 50 words
- Do NOT use bullet points, write in natural prose
- Do NOT start with "This role", "The candidate", or repeat the job title (e.g., "As Senior Product Manager")
- Jump straight into what the role does or requires

**Response format:** Just the summary text, no JSON or markdown."""

MATCH_RERANK_PROMPT = """You are an expert job matching assistant. Evaluate how well this candidate's resume matches the job posting.

**CANDIDATE PROFILE:**
Skills: {resume_skills}
Experience: {experience_years} years
Domain Expertise: {resume_domains}

**JOB POSTING:**
Title: {job_title}
Company: {company}
Location: {location}
Description:
{description}

**EVALUATION CRITERIA:**
1. Skills Alignment (40%): How well do the candidate's skills match the job requirements?
2. Experience Fit (25%): Is the candidate's experience level appropriate?
3. Domain Relevance (25%): Does the candidate have relevant industry experience?
4. Role Fit (10%): How well does the overall profile match this specific role?

**Instructions:**
- Be objective and realistic about the match quality
- Consider both explicit requirements and implied needs
- A score of 0.7+ should indicate a strong match
- A score of 0.5-0.7 indicates a moderate match with some gaps
- A score below 0.5 indicates significant misalignment

**Response format (JSON only, no markdown):**
{{"score": 0.XX, "reasoning": "2-3 sentence explanation of match quality", "strengths": ["strength1", "strength2"], "gaps": ["gap1", "gap2"]}}
"""

BULLET_REWRITE_PROMPT = """You are an expert resume writer specializing in ATS optimization and impactful bullet points.

**JOB CONTEXT:**
Title: {job_title}
Company: {company}
Key Requirements:
{requirements}

**RESUME ROLE CONTEXT:**
Role: {role_title} at {role_company}
Other bullets in this role (for context, do NOT rewrite these):
{other_bullets}

**BULLET TO IMPROVE:**
"{original_bullet}"
Current Alignment Score: {score}%

**INSTRUCTIONS:**
1. Generate exactly 3 alternative versions of this bullet
2. Naturally incorporate relevant keywords from the job requirements
3. PRESERVE THE TRUTH - do not fabricate accomplishments or metrics
4. If the original has quantitative metrics, keep them accurate
5. Use strong action verbs and STAR format (Situation, Task, Action, Result)
6. Keep each bullet under 2 lines (roughly 150 characters)
7. Make each suggestion distinct - different angles or emphasis

**Response format (JSON only, no markdown):**
{{"analysis": "Brief explanation of why this bullet scored low and what's missing", "suggestions": ["suggestion1", "suggestion2", "suggestion3"]}}
"""

REQUIREMENTS_EXTRACTION_PROMPT = """Analyze this job posting and extract structured requirements.

**Job Title:** {title}
**Company:** {company}

**Job Description:**
{description}

**Instructions:**
1. Distinguish between MUST-HAVE (required, essential, "must have") and NICE-TO-HAVE (preferred, bonus, "nice to have") skills
2. For each skill, include:
   - name: The skill name
   - context: How it's used (e.g., "for data pipelines", "in production environments") - null if not specified
   - level: beginner, intermediate, advanced, or expert (infer from requirements)
   - years: Specific years required for this skill (null if not specified)
3. Identify seniority level from title, years required, and responsibility scope
4. Identify required vs preferred domains/industries
5. Classify role focus as technical (IC work), strategic (leadership/vision), or hybrid

**Response format (JSON only, no markdown):**
{{
  "must_have_skills": [
    {{"name": "Python", "context": "for backend development", "level": "advanced", "years": 3}}
  ],
  "nice_to_have_skills": [
    {{"name": "Kubernetes", "context": null, "level": "intermediate", "years": null}}
  ],
  "min_years": 5,
  "max_years": 10,
  "seniority_level": "senior",
  "required_domains": ["fintech", "b2b_saas"],
  "preferred_domains": ["payments"],
  "role_focus": "hybrid",
  "key_responsibilities": ["Lead product roadmap", "Partner with engineering", "Define metrics"]
}}

Use null for unknown values. Keep key_responsibilities to top 5-7 items.
Valid seniority levels: entry, mid, senior, staff, principal, director
Valid role focus: technical, strategic, hybrid
"""

DOMAIN_EXTRACTION_PROMPT = """Analyze this job posting and identify the industry domains and technology platforms that are REQUIRED or strongly preferred for this role.

**Company:** {company}
**Job Title:** {title}

**Job Description:**
{description}

**Instructions:**
1. Identify domains based on the COMPANY'S ACTUAL BUSINESS and the role's requirements
2. Only include domains that are explicitly required or strongly emphasized
3. Do NOT include domains just because a generic word appears (e.g., "healthcare benefits" doesn't mean healthcare industry)
4. Consider the company's industry first, then the specific role requirements

**Valid domains to choose from:**
Industries: ecommerce, fintech, banking, investment_management, asset_management, financial_services, b2b, b2b_saas, healthcare, edtech, adtech, martech, logistics, real_estate, gaming, media, cybersecurity, hr_tech, legal_tech, construction, travel, automotive, agriculture, energy, government, nonprofit

Platforms: salesforce, shopify, sap, oracle, workday, adobe, hubspot, stripe, twilio, zendesk, servicenow, atlassian, snowflake, databricks

Technologies: headless_cms, composable, blockchain, ai_ml, data_engineering, devops, mobile, iot, ar_vr, voice

**Response format (JSON only, no markdown):**
{{"domains": ["domain1", "domain2"], "reasoning": "Brief explanation of why these domains apply"}}

If no specific domains are required, respond with:
{{"domains": [], "reasoning": "Generic role with no specific domain requirements"}}
"""


class GeminiClient:
    """Base Gemini client for API connectivity and health checks.

    Provides a unified interface for checking Gemini API availability
    and testing connectivity before operations.
    """

    def __init__(self):
        """Initialize the Gemini client."""
        self.config = get_config()
        self.enabled = self.config.get("gemini.enabled", False)
        self.api_key = self.config.get("gemini.api_key")
        self.model_name = self.config.get("gemini.matcher.model", "gemini-3-flash-preview")
        self.client = None

        if self.enabled and self.api_key:
            try:
                self.client = genai.Client(api_key=self.api_key)
                self._rate_limiter = get_rate_limiter(self.model_name)
                logger.info(f"GeminiClient initialized with model: {self.model_name}")
            except Exception as e:
                logger.error(f"Failed to initialize GeminiClient: {e}")
                self.enabled = False

    def is_available(self) -> bool:
        """Check if Gemini is available and properly configured."""
        return self.enabled and self.client is not None

    def test_connection(self) -> Dict:
        """Test Gemini API connectivity with a minimal request.

        Returns:
            Dict with test results:
                - available: True if connection successful
                - model: Model name if successful
                - latency_ms: Response time in milliseconds
                - error: Error message if failed
        """
        import time

        if not self.is_available():
            return {
                "available": False,
                "error": "Gemini client not initialized"
            }

        try:
            start_time = time.perf_counter()

            # Minimal test prompt - just ask for a single word
            response = self._rate_limiter.call_with_retry(
                self.client.models.generate_content,
                model=self.model_name,
                contents="Respond with only the word 'OK'.",
                config=types.GenerateContentConfig(
                    temperature=0.0,
                    max_output_tokens=10,
                )
            )

            latency_ms = (time.perf_counter() - start_time) * 1000

            # Check if we got a valid response
            if response.candidates and response.candidates[0].content.parts:
                return {
                    "available": True,
                    "model": self.model_name,
                    "latency_ms": round(latency_ms, 1)
                }
            else:
                finish_reason = response.candidates[0].finish_reason if response.candidates else 'unknown'
                return {
                    "available": False,
                    "model": self.model_name,
                    "latency_ms": round(latency_ms, 1),
                    "error": f"Empty response (finish_reason: {finish_reason})"
                }

        except Exception as e:
            logger.error(f"Gemini connection test failed: {e}")
            return {
                "available": False,
                "model": self.model_name,
                "error": str(e)
            }


class GeminiDomainExtractor:
    """Extract domains from job descriptions using Gemini LLM."""

    def __init__(self):
        """Initialize the Gemini client."""
        self.config = get_config()
        self.enabled = self.config.get("gemini.enabled", False)
        # Use cheapest model for structured extraction tasks
        self.model_name = self.config.get("gemini.extractor.model", "gemini-3.1-flash-lite-preview")
        # Token limits - increased to prevent truncation issues
        self.domain_max_tokens = self.config.get("gemini.extractor.domain_max_tokens", 500)
        self.summary_max_tokens = self.config.get("gemini.extractor.summary_max_tokens", 300)
        self.api_key = self.config.get("gemini.api_key")
        self.client = None

        if self.enabled and self.api_key:
            try:
                self.client = genai.Client(api_key=self.api_key)
                self._rate_limiter = get_rate_limiter(self.model_name)
                logger.info(f"Gemini extractor initialized with model: {self.model_name}")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini client: {e}")
                self.enabled = False

    def is_available(self) -> bool:
        """Check if Gemini extraction is available."""
        return self.enabled and self.client is not None


    def extract_domains(
        self,
        description: str,
        company: str = "",
        title: str = ""
    ) -> Dict[str, any]:
        """Extract domains from a job description using Gemini.

        Args:
            description: Job description text
            company: Company name
            title: Job title

        Returns:
            Dict with 'domains' (list of domain keys) and 'reasoning' (explanation)
        """
        if not self.is_available():
            logger.warning("Gemini not available, returning empty domains")
            return {"domains": [], "reasoning": "Gemini not configured"}

        if not description:
            return {"domains": [], "reasoning": "No description provided"}

        # Truncate very long descriptions to save tokens
        max_chars = 8000
        if len(description) > max_chars:
            description = description[:max_chars] + "..."

        prompt = DOMAIN_EXTRACTION_PROMPT.format(
            company=company or "Unknown",
            title=title or "Unknown",
            description=description
        )

        try:
            response = self._rate_limiter.call_with_retry(
                self.client.models.generate_content,
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.1,  # Low temperature for consistent results
                    max_output_tokens=self.domain_max_tokens,
                    response_mime_type="application/json",
                )
            )

            # Parse the response safely
            # Parse the response safely
            response_text = ""
            if response.candidates and response.candidates[0].content.parts:
                try:
                    response_text = response.text or ""
                except ValueError:
                    # Handle "non-text parts" warning
                    parts = []
                    for part in response.candidates[0].content.parts:
                        if hasattr(part, 'text') and part.text:
                            parts.append(part.text)
                    response_text = "".join(parts)
            else:
                finish_reason = response.candidates[0].finish_reason if response.candidates else 'unknown'

                # Handle specific finish reasons
                if finish_reason and finish_reason.name == "MAX_TOKENS":
                    logger.warning(f"Gemini response truncated (MAX_TOKENS) for domain extraction: {title}")
                    return {"domains": [], "reasoning": "Response incomplete - token limit exceeded"}
                elif finish_reason and finish_reason.name == "SAFETY":
                    logger.warning(f"Gemini response blocked for domain extraction: {title}")
                    return {"domains": [], "reasoning": "Response blocked by content filter"}
                else:
                    logger.warning(f"Gemini returned no content for domain extraction. Finish reason: {finish_reason}")
                    return {"domains": [], "reasoning": f"No content returned (reason: {finish_reason})"}

            cleaned_text = clean_json_text(response_text)
            result = json.loads(cleaned_text)

            # Validate domains
            valid_domains = [d for d in result.get("domains", []) if d in VALID_DOMAINS]

            return {
                "domains": valid_domains,
                "reasoning": result.get("reasoning", "")
            }

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini response: {e}")
            logger.debug(f"Raw text: {response_text if 'response_text' in locals() else 'N/A'}")
            return {"domains": [], "reasoning": None}
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return {"domains": [], "reasoning": None}

# ... (similarly for _evaluate_match and rewrite_bullet)


    def extract_domains_batch(
        self,
        jobs: List[Dict]
    ) -> List[Dict]:
        """Extract domains for multiple jobs.

        Args:
            jobs: List of dicts with 'description', 'company', 'title' keys

        Returns:
            List of extraction results
        """
        results = []
        for i, job in enumerate(jobs):
            logger.info(f"Processing job {i+1}/{len(jobs)}: {job.get('title', 'Unknown')} @ {job.get('company', 'Unknown')}")
            result = self.extract_domains(
                description=job.get("description", ""),
                company=job.get("company", ""),
                title=job.get("title", "")
            )
            results.append(result)
        return results

    def summarize_job(
        self,
        description: str,
        company: str = "",
        title: str = ""
    ) -> Optional[str]:
        """Generate a concise summary of a job description.

        Args:
            description: Job description text
            company: Company name
            title: Job title

        Returns:
            Summary string or None if failed
        """
        if not self.is_available():
            logger.warning("Gemini not available, cannot generate summary")
            return None

        if not description:
            return None

        # Truncate very long descriptions to save tokens
        max_chars = 6000
        if len(description) > max_chars:
            description = description[:max_chars] + "..."

        prompt = JOB_SUMMARY_PROMPT.format(
            company=company or "Unknown",
            title=title or "Unknown",
            description=description
        )

        try:
            response = self._rate_limiter.call_with_retry(
                self.client.models.generate_content,
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.3,  # Slightly higher for more natural writing
                    max_output_tokens=self.summary_max_tokens,
                )
            )

            if not response.candidates or not response.candidates[0].content.parts:
                finish_reason = response.candidates[0].finish_reason if response.candidates else 'unknown'

                # Handle specific finish reasons
                if finish_reason and finish_reason.name == "MAX_TOKENS":
                    logger.warning(f"Gemini summary truncated (MAX_TOKENS) for: {title}")
                elif finish_reason and finish_reason.name == "SAFETY":
                    logger.warning(f"Gemini summary blocked for: {title}")
                else:
                    logger.warning(f"Gemini returned no summary. Finish reason: {finish_reason}")
                return None

            try:
                summary = response.text.strip()
            except ValueError:
                 parts = []
                 for part in response.candidates[0].content.parts:
                     if hasattr(part, 'text') and part.text:
                         parts.append(part.text)
                 summary = "".join(parts).strip()

            # Clean up any markdown or quotes
            if summary.startswith('"') and summary.endswith('"'):
                summary = summary[1:-1]
            if summary.startswith("```"):
                lines = summary.split("\n")
                summary = "\n".join(lines[1:-1]).strip()

            return summary

        except Exception as e:
            logger.error(f"Gemini summarization error: {e}")
            return None


def get_gemini_extractor() -> Optional[GeminiDomainExtractor]:
    """Factory function to get a Gemini extractor instance.

    Returns:
        GeminiDomainExtractor if available, None otherwise
    """
    extractor = GeminiDomainExtractor()
    if extractor.is_available():
        return extractor
    return None


class GeminiRequirementsExtractor:
    """Extract structured requirements from job descriptions using Gemini LLM.

    This class extracts:
    - Must-have vs nice-to-have skills with context and levels
    - Experience requirements (min/max years)
    - Seniority level
    - Required/preferred domains
    - Role focus (technical/strategic/hybrid)
    - Key responsibilities
    """

    def __init__(self):
        """Initialize the Gemini requirements extractor."""
        self.config = get_config()
        self.enabled = self.config.get("gemini.enabled", False)
        # Use cheapest model for structured extraction tasks
        self.model_name = self.config.get("gemini.extractor.model", "gemini-3.1-flash-lite-preview")
        self.api_key = self.config.get("gemini.api_key")
        self.client = None

        if self.enabled and self.api_key:
            try:
                self.client = genai.Client(api_key=self.api_key)
                self._rate_limiter = get_rate_limiter(self.model_name)
                logger.info(f"Gemini requirements extractor initialized with model: {self.model_name}")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini requirements extractor: {e}")
                self.enabled = False

    def is_available(self) -> bool:
        """Check if Gemini extraction is available."""
        return self.enabled and self.client is not None

    def extract_requirements(
        self,
        description: str,
        title: str = "",
        company: str = ""
    ) -> Optional[Dict]:
        """Extract structured requirements from a job description.

        Args:
            description: Job description text
            title: Job title
            company: Company name

        Returns:
            Dict with structured requirements or None if extraction fails
        """
        if not self.is_available():
            logger.warning("Gemini not available for requirements extraction")
            return None

        if not description:
            return None

        # Truncate very long descriptions to save tokens
        max_chars = 10000
        if len(description) > max_chars:
            description = description[:max_chars] + "..."

        prompt = REQUIREMENTS_EXTRACTION_PROMPT.format(
            title=title or "Unknown",
            company=company or "Unknown",
            description=description
        )

        try:
            response = self._rate_limiter.call_with_retry(
                self.client.models.generate_content,
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.1,  # Low temperature for consistent extraction
                    max_output_tokens=1024,  # Needs more tokens for detailed output
                    response_mime_type="application/json",
                )
            )

            # Parse response safely
            response_text = ""
            if response.candidates and response.candidates[0].content.parts:
                try:
                    response_text = response.text or ""
                except ValueError:
                    # Handle non-text parts
                    parts = []
                    for part in response.candidates[0].content.parts:
                        if hasattr(part, 'text') and part.text:
                            parts.append(part.text)
                    response_text = "".join(parts)
            else:
                finish_reason = response.candidates[0].finish_reason if response.candidates else 'unknown'
                logger.warning(f"Gemini returned no content for requirements extraction. Finish reason: {finish_reason}")
                return None

            cleaned_text = clean_json_text(response_text)
            result = json.loads(cleaned_text)

            # Validate and normalize the result
            normalized = self._normalize_result(result)

            # Add metadata
            from datetime import datetime, timezone
            normalized["extraction_model"] = self.model_name
            normalized["extraction_timestamp"] = datetime.now(timezone.utc).isoformat()

            return normalized

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini requirements response: {e}")
            logger.debug(f"Raw text: {response_text if 'response_text' in locals() else 'N/A'}")
            return None
        except Exception as e:
            logger.error(f"Gemini requirements extraction error: {e}")
            return None

    def _normalize_result(self, result: Dict) -> Dict:
        """Normalize and validate the extraction result.

        Args:
            result: Raw result from Gemini

        Returns:
            Normalized result with valid values
        """
        # Valid enum values
        valid_seniority = ["entry", "mid", "senior", "staff", "principal", "director"]
        valid_role_focus = ["technical", "strategic", "hybrid"]
        valid_skill_levels = ["beginner", "intermediate", "advanced", "expert"]

        # Normalize must_have_skills
        must_have = []
        for skill in result.get("must_have_skills", []):
            if isinstance(skill, dict) and skill.get("name"):
                level = skill.get("level", "intermediate")
                if level not in valid_skill_levels:
                    level = "intermediate"
                must_have.append({
                    "name": skill["name"],
                    "context": skill.get("context"),
                    "level": level,
                    "years": skill.get("years")
                })

        # Normalize nice_to_have_skills
        nice_to_have = []
        for skill in result.get("nice_to_have_skills", []):
            if isinstance(skill, dict) and skill.get("name"):
                level = skill.get("level", "intermediate")
                if level not in valid_skill_levels:
                    level = "intermediate"
                nice_to_have.append({
                    "name": skill["name"],
                    "context": skill.get("context"),
                    "level": level,
                    "years": skill.get("years")
                })

        # Normalize seniority_level
        seniority = result.get("seniority_level", "mid")
        if seniority not in valid_seniority:
            seniority = "mid"

        # Normalize role_focus
        role_focus = result.get("role_focus", "hybrid")
        if role_focus not in valid_role_focus:
            role_focus = "hybrid"

        return {
            "must_have_skills": must_have,
            "nice_to_have_skills": nice_to_have,
            "min_years": result.get("min_years"),
            "max_years": result.get("max_years"),
            "seniority_level": seniority,
            "required_domains": result.get("required_domains", []),
            "preferred_domains": result.get("preferred_domains", []),
            "role_focus": role_focus,
            "key_responsibilities": result.get("key_responsibilities", [])[:7]
        }


def get_requirements_extractor() -> Optional[GeminiRequirementsExtractor]:
    """Factory function to get a Gemini requirements extractor instance.

    Returns:
        GeminiRequirementsExtractor if available, None otherwise
    """
    extractor = GeminiRequirementsExtractor()
    if extractor.is_available():
        return extractor
    return None


class GeminiMatchReranker:
    """Re-rank job matches using Gemini LLM for more accurate scoring."""

    def __init__(self):
        """Initialize the Gemini re-ranker."""
        self.config = get_config()
        self.enabled = self.config.get("matching.gemini_rerank.enabled", False)
        self.top_n = self.config.get("matching.gemini_rerank.top_n", 15)
        self.min_score_threshold = self.config.get("matching.gemini_rerank.min_score_threshold", 0.65)
        self.model_name = self.config.get("gemini.model", "gemini-3-flash-preview")
        self.api_key = self.config.get("gemini.api_key")
        self.client = None

        if self.enabled and self.api_key:
            try:
                self.client = genai.Client(api_key=self.api_key)
                self._rate_limiter = get_rate_limiter(self.model_name)
                logger.info(f"Gemini re-ranker initialized with model: {self.model_name}")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini re-ranker: {e}")
                self.enabled = False

    def is_available(self) -> bool:
        """Check if Gemini re-ranking is available."""
        return self.enabled and self.client is not None

    def rerank_matches(
        self,
        matches: List[Dict],
        resume_skills: List[str],
        experience_years: float,
        resume_domains: List[str] = None
    ) -> List[Dict]:
        """Re-rank a list of matches using Gemini.

        Args:
            matches: List of match dictionaries with job details
            resume_skills: List of candidate skills
            experience_years: Years of experience
            resume_domains: List of domain expertise

        Returns:
            List of matches with added 'gemini_score', 'gemini_reasoning', 'strengths', 'gaps'
        """
        if not self.is_available():
            logger.warning("Gemini re-ranker not available")
            return matches

        # Filter to top N matches above threshold
        eligible = [
            m for m in matches
            if m.get('overall_score', 0) >= self.min_score_threshold
        ][:self.top_n]

        logger.info(f"Re-ranking {len(eligible)} matches with Gemini")

        for match in eligible:
            result = self._evaluate_match(
                match=match,
                resume_skills=resume_skills,
                experience_years=experience_years,
                resume_domains=resume_domains or []
            )

            if result.get('score') is not None:
                match['gemini_score'] = result['score'] * 100  # Convert to 0-100 scale
                match['gemini_reasoning'] = result.get('reasoning', '')
                match['gemini_strengths'] = result.get('strengths', [])
                match['gemini_gaps'] = result.get('gaps', [])

        return matches


    def _evaluate_match(
        self,
        match: Dict,
        resume_skills: List[str],
        experience_years: float,
        resume_domains: List[str]
    ) -> Dict:
        """Evaluate a single match using Gemini.

        Args:
            match: Match dictionary with job details
            resume_skills: List of candidate skills
            experience_years: Years of experience
            resume_domains: List of domain expertise

        Returns:
            Dict with 'score', 'reasoning', 'strengths', 'gaps'
        """
        # Truncate description to save tokens (matches extract_domains)
        description = match.get('description', '')[:8000]

        prompt = MATCH_RERANK_PROMPT.format(
            resume_skills=", ".join(resume_skills[:30]),  # Limit skills for prompt
            experience_years=experience_years,
            resume_domains=", ".join(resume_domains) if resume_domains else "Not specified",
            job_title=match.get('job_title', 'Unknown'),
            company=match.get('company', 'Unknown'),
            location=match.get('location', 'Not specified'),
            description=description
        )

        try:
            response = self._rate_limiter.call_with_retry(
                self.client.models.generate_content,
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.2,  # Low for consistent scoring
                    max_output_tokens=2048,  # Increased to prevent truncation
                    response_mime_type="application/json",
                )
            )

            # Check for empty response BEFORE accessing response.text
            if not response.candidates or not response.candidates[0].content.parts:
                finish_reason = response.candidates[0].finish_reason if response.candidates else 'unknown'

                # Handle specific finish reasons with enhanced logging
                job_title = match.get('job_title', 'Unknown')
                company = match.get('company', 'Unknown')

                if finish_reason and finish_reason.name == "MAX_TOKENS":
                    logger.warning(
                        f"❌ GEMINI FALLBACK → NLP | Reason: MAX_TOKENS (response truncated) | "
                        f"Job: '{job_title}' @ {company}"
                    )
                    return {'score': None, 'reasoning': None, 'strengths': [], 'gaps': []}
                elif finish_reason and finish_reason.name == "SAFETY":
                    logger.warning(
                        f"❌ GEMINI FALLBACK → NLP | Reason: SAFETY (content filter) | "
                        f"Job: '{job_title}' @ {company}"
                    )
                    return {'score': None, 'reasoning': None, 'strengths': [], 'gaps': []}
                else:
                    logger.warning(
                        f"❌ GEMINI FALLBACK → NLP | Reason: UNKNOWN (finish_reason={finish_reason}) | "
                        f"Job: '{job_title}' @ {company}"
                    )
                    return {'score': None, 'reasoning': None, 'strengths': [], 'gaps': []}

            # Extract text parts only (ignore thought_signature and other non-text parts)
            text_parts = []
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'text') and part.text:
                    text_parts.append(part.text)

            if not text_parts:
                job_title = match.get('job_title', 'Unknown')
                company = match.get('company', 'Unknown')
                logger.warning(
                    f"❌ GEMINI FALLBACK → NLP | Reason: NO_TEXT_PARTS (response has no text) | "
                    f"Job: '{job_title}' @ {company}"
                )
                return {'score': None, 'reasoning': None, 'strengths': [], 'gaps': []}

            response_text = "".join(text_parts)
            logger.debug(f"Raw response (first 200 chars): {response_text[:200]}")
            cleaned = clean_json_text(response_text)
            logger.debug(f"Cleaned (first 200 chars): {cleaned[:200]}")
            result = json.loads(cleaned)

            # Validate score is in range
            score = result.get('score', 0)
            if not isinstance(score, (int, float)) or score < 0 or score > 1:
                score = 0

            return {
                'score': round(score, 3),
                'reasoning': result.get('reasoning', ''),
                'strengths': result.get('strengths', []),
                'gaps': result.get('gaps', [])
            }

        except json.JSONDecodeError as e:
            job_title = match.get('job_title', 'Unknown')
            company = match.get('company', 'Unknown')
            logger.error(
                f"❌ GEMINI FALLBACK → NLP | Reason: JSON_PARSE_ERROR ({str(e)[:100]}) | "
                f"Job: '{job_title}' @ {company}"
            )
            if 'response_text' in locals():
                logger.debug(f"Raw response text (first 500 chars): {response_text[:500] if response_text else 'EMPTY'}")
                logger.debug(f"Cleaned text (first 500 chars): {cleaned[:500] if 'cleaned' in locals() and cleaned else 'EMPTY'}")
            return {'score': None, 'reasoning': None, 'strengths': [], 'gaps': []}
        except Exception as e:
            job_title = match.get('job_title', 'Unknown')
            company = match.get('company', 'Unknown')
            logger.error(
                f"❌ GEMINI FALLBACK → NLP | Reason: EXCEPTION ({type(e).__name__}: {str(e)[:100]}) | "
                f"Job: '{job_title}' @ {company}"
            )
            return {'score': None, 'reasoning': None, 'strengths': [], 'gaps': []}


def get_gemini_reranker() -> Optional[GeminiMatchReranker]:
    """Factory function to get a Gemini re-ranker instance.

    Returns:
        GeminiMatchReranker if available, None otherwise
    """
    reranker = GeminiMatchReranker()
    if reranker.is_available():
        return reranker
    return None


class GeminiBulletRewriter:
    """Rewrite resume bullets to better match job descriptions using Gemini."""

    def __init__(self):
        """Initialize the Gemini bullet rewriter."""
        self.config = get_config()
        self.enabled = self.config.get("gemini.enabled", False)
        # Use best reasoning model for bullet rewrites (most critical for resume quality)
        self.model_name = self.config.get(
            "targeting.gemini.model",
            "gemini-3-flash-preview"  # Best reasoning model for high-quality rewrites
        )
        self.api_key = self.config.get("gemini.api_key")
        self.temperature = self.config.get("targeting.gemini.temperature", 0.35)
        self.max_tokens = self.config.get("targeting.gemini.max_tokens", 8192)  # Thinking models need headroom (thinking uses ~2000-6000 tokens)
        self.client = None

        if self.enabled and self.api_key:
            try:
                self.client = genai.Client(api_key=self.api_key)
                self._rate_limiter = get_rate_limiter(self.model_name)
                logger.info(f"Gemini bullet rewriter initialized with model: {self.model_name}")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini bullet rewriter: {e}")
                self.enabled = False

    def is_available(self) -> bool:
        """Check if Gemini rewriting is available."""
        return self.enabled and self.client is not None

    def extract_requirements(self, job_description: str) -> List[str]:
        """Extract key requirements from a job description.

        Args:
            job_description: Full job description text

        Returns:
            List of requirement strings
        """
        requirements = []

        # Look for common requirement patterns
        lines = job_description.split('\n')
        in_requirements_section = False

        for line in lines:
            line = line.strip()
            lower = line.lower()

            # Detect requirements section headers
            if any(header in lower for header in [
                'requirements', 'qualifications', 'what you need',
                'what we\'re looking for', 'must have', 'required skills'
            ]):
                in_requirements_section = True
                continue

            # Detect end of requirements section
            if in_requirements_section and any(header in lower for header in [
                'responsibilities', 'what you\'ll do', 'benefits', 'perks',
                'about us', 'about the company', 'nice to have', 'preferred'
            ]):
                in_requirements_section = False
                continue

            # Extract bullet points in requirements section
            if in_requirements_section and (
                line.startswith(('-', '•', '*', '·')) or
                (len(line) > 2 and line[0].isdigit() and line[1] in '.)')
            ):
                # Clean up the bullet point
                clean_line = line.lstrip('-•*·0123456789.) ').strip()
                if len(clean_line) > 10:  # Skip very short items
                    requirements.append(clean_line)

        # If no structured requirements found, extract key phrases
        if not requirements:
            # Look for common skill/requirement patterns
            patterns = [
                r'(\d+\+?\s*years?\s+(?:of\s+)?experience\s+(?:in|with)\s+[^.]+)',
                r'(proficient\s+(?:in|with)\s+[^.]+)',
                r'(strong\s+(?:experience|knowledge|skills)\s+(?:in|with)\s+[^.]+)',
                r'(expertise\s+in\s+[^.]+)',
            ]
            for pattern in patterns:
                matches = re.findall(pattern, job_description, re.IGNORECASE)
                requirements.extend(matches[:3])  # Limit per pattern

        return requirements[:10]  # Return max 10 requirements

    def rewrite_bullet(
        self,
        original_bullet: str,
        score: float,
        job_title: str,
        company: str,
        job_description: str,
        role_title: str,
        role_company: str,
        other_bullets: List[str] = None
    ) -> Dict:
        """Generate alternative versions of a resume bullet.

        Args:
            original_bullet: The bullet text to rewrite
            score: Current alignment score (0.0-1.0)
            job_title: Target job title
            company: Target company name
            job_description: Full job description
            role_title: Resume role title
            role_company: Resume role company
            other_bullets: Other bullets in this role for context

        Returns:
            Dict with 'analysis' and 'suggestions' keys
        """
        if not self.is_available():
            logger.warning("Gemini not available for bullet rewriting")
            return {"analysis": "Gemini not configured", "suggestions": []}

        # Truncate job description to prevent token overflow (matches extract_domains)
        max_desc_chars = 8000
        if len(job_description) > max_desc_chars:
            job_description = job_description[:max_desc_chars] + "..."

        # Extract requirements for context
        requirements = self.extract_requirements(job_description)
        requirements_text = "\n".join(f"- {r}" for r in requirements) if requirements else "Not specified"

        # Format and truncate other bullets to prevent overflow
        truncated_bullets = []
        for b in (other_bullets or [])[:5]:
            if len(b) > 200:
                truncated_bullets.append(b[:200] + "...")
            else:
                truncated_bullets.append(b)
        other_bullets_text = "\n".join(f"- {b}" for b in truncated_bullets)
        if not other_bullets_text:
            other_bullets_text = "(No other bullets)"

        prompt = BULLET_REWRITE_PROMPT.format(
            job_title=job_title or "Unknown",
            company=company or "Unknown",
            requirements=requirements_text,
            role_title=role_title or "Unknown",
            role_company=role_company or "Unknown",
            other_bullets=other_bullets_text,
            original_bullet=original_bullet,
            score=int(score * 100)
        )

        try:
            response = self._rate_limiter.call_with_retry(
                self.client.models.generate_content,
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=self.temperature,
                    max_output_tokens=self.max_tokens,
                    # response_mime_type intentionally omitted — thinking models
                    # (gemini-3-flash-preview) produce empty arrays with JSON constraint.
                    # clean_json_text() handles free-form responses reliably.
                    # Safety settings to prevent false positives on professional content
                    safety_settings=[
                        types.SafetySetting(category="HARM_CATEGORY_HARASSMENT",        threshold="BLOCK_MEDIUM_AND_ABOVE"),
                        types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH",       threshold="BLOCK_MEDIUM_AND_ABOVE"),
                        types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_MEDIUM_AND_ABOVE"),
                        types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_MEDIUM_AND_ABOVE"),
                    ],
                ),
            )

            # (Duplicate call removed)

            # Check for empty response BEFORE accessing response.text
            if not response.candidates or not response.candidates[0].content.parts:
                finish_reason = response.candidates[0].finish_reason if response.candidates else 'unknown'

                # Handle specific finish reasons
                if finish_reason and finish_reason.name == "MAX_TOKENS":
                    logger.warning("Gemini response truncated (MAX_TOKENS) for bullet rewrite")
                    return {
                        "analysis": "Response incomplete - input too large. Try shorter job description.",
                        "suggestions": []
                    }
                elif finish_reason and finish_reason.name == "SAFETY":
                    logger.warning("Gemini response blocked by safety filter")
                    # Log safety ratings for debugging
                    if response.candidates and response.candidates[0].safety_ratings:
                        for rating in response.candidates[0].safety_ratings:
                            logger.warning(f"  Safety rating: {rating.category} = {rating.probability}")
                    return {"analysis": "Response blocked by content filter", "suggestions": []}
                else:
                    logger.warning(f"Gemini returned no content. Finish reason: {finish_reason}")
                    return {"analysis": f"AI generation failed (reason: {finish_reason})", "suggestions": []}

            # Now safe to access response.text
            try:
                response_text = response.text or ""
            except ValueError:
                # Handle non-text parts gracefully
                parts = []
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'text') and part.text:
                        parts.append(part.text)
                response_text = "".join(parts)

            cleaned = clean_json_text(response_text)
            result = json.loads(cleaned)

            return {
                "analysis": result.get("analysis", ""),
                "suggestions": result.get("suggestions", [])[:3]  # Limit to 3
            }

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini bullet rewrite response: {e}")
            return {"analysis": f"Parse error: {e}", "suggestions": []}
        except Exception as e:
            logger.error(f"Gemini bullet rewrite error: {e}")
            return {"analysis": f"API error: {e}", "suggestions": []}

    def rewrite_bullets_batch(
        self,
        bullets: List[Dict],
        job_title: str,
        company: str,
        job_description: str,
        role_title: str,
        role_company: str,
        threshold: float = 0.7
    ) -> List[Dict]:
        """Rewrite multiple bullets that fall below threshold.

        Args:
            bullets: List of dicts with 'text' and 'score' keys
            job_title: Target job title
            company: Target company
            job_description: Full job description
            role_title: Resume role title
            role_company: Resume role company
            threshold: Only rewrite bullets below this score

        Returns:
            List of dicts with original bullet info plus 'analysis' and 'suggestions'
        """
        results = []
        all_bullet_texts = [b.get('text', '') for b in bullets]

        for bullet in bullets:
            text = bullet.get('text', '')
            score = bullet.get('score', 0)

            result = {
                'original': text,
                'score': score,
                'analysis': '',
                'suggestions': []
            }

            if score < threshold:
                # Get other bullets for context (excluding current)
                other_bullets = [b for b in all_bullet_texts if b != text]

                rewrite_result = self.rewrite_bullet(
                    original_bullet=text,
                    score=score,
                    job_title=job_title,
                    company=company,
                    job_description=job_description,
                    role_title=role_title,
                    role_company=role_company,
                    other_bullets=other_bullets
                )

                result['analysis'] = rewrite_result.get('analysis', '')
                result['suggestions'] = rewrite_result.get('suggestions', [])

            results.append(result)

        return results


def get_bullet_rewriter() -> Optional[GeminiBulletRewriter]:
    """Factory function to get a Gemini bullet rewriter instance.

    Returns:
        GeminiBulletRewriter if available, None otherwise
    """
    rewriter = GeminiBulletRewriter()
    if rewriter.is_available():
        return rewriter
    return None
