"""Guard against DOMAIN_EXTRACTION_PROMPT drifting from the domain taxonomy.

`DOMAIN_EXTRACTION_PROMPT` hardcodes the list of valid domain keys it offers the
model. `data/domain_expertise.json` is the actual taxonomy the matching engine
compares against. Nothing linked the two, so adding a key to the JSON silently
left it unextractable: the resume could claim a domain that no job posting could
ever be tagged with, quietly dragging down the domain component of every match.

That happened for real — `esg`, `regulatory_compliance`, and `azure` were added
to the taxonomy on 2026-08-24 and the prompt was not updated, joining `aws` and
`gcp` which had been missing already. This test exists so the next person who
edits one file is told to edit the other.
"""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TAXONOMY_PATH = PROJECT_ROOT / "data" / "domain_expertise.json"


def _prompt_domain_block() -> str:
    """The 'Valid domains to choose from' section of the extraction prompt."""
    from src.integrations.gemini_client import DOMAIN_EXTRACTION_PROMPT

    return DOMAIN_EXTRACTION_PROMPT.split("**Valid domains to choose from:**")[1].split(
        "**Response format"
    )[0]


def _taxonomy_keys() -> list:
    domains = json.loads(TAXONOMY_PATH.read_text())["domains"]
    return [(cat, key) for cat, keys in domains.items() for key in keys]


def test_every_taxonomy_key_is_offered_in_the_prompt():
    block = _prompt_domain_block()
    missing = [f"{cat}.{key}" for cat, key in _taxonomy_keys() if key not in block]
    assert not missing, (
        "Domain keys exist in data/domain_expertise.json but are absent from "
        "DOMAIN_EXTRACTION_PROMPT, so Gemini can never extract them: "
        f"{missing}. Add them to the prompt's 'Valid domains' list."
    )


def test_prompt_offers_no_keys_outside_the_taxonomy():
    """The reverse drift: a key the model is told to use but the engine rejects.

    Matching compares domains by exact key, so an invented key would be extracted,
    stored, and then never match anything.
    """
    block = _prompt_domain_block()
    known = {key for _, key in _taxonomy_keys()}

    listed = set()
    for line in block.splitlines():
        if ":" not in line:
            continue
        _, _, values = line.partition(":")
        for token in values.split(","):
            token = token.strip()
            if token and " " not in token:
                listed.add(token)

    unknown = sorted(listed - known)
    assert not unknown, (
        "DOMAIN_EXTRACTION_PROMPT offers domain keys that are not in "
        f"data/domain_expertise.json: {unknown}. The matching engine compares by "
        "exact key, so these would never match."
    )
