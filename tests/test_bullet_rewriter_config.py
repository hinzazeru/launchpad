"""Tests for GeminiBulletRewriter config changes.

Verifies:
1. response_mime_type is NOT passed to GenerateContentConfig (thinking model fix)
2. max_output_tokens defaults to 8192 (thinking model token budget)
3. clean_json_text handles free-form (non-constrained) Gemini responses
"""

import json
from unittest.mock import patch, MagicMock, PropertyMock

import pytest

from src.integrations.gemini_client import clean_json_text


# ---------------------------------------------------------------------------
# Fix #1: response_mime_type must NOT be set for thinking models
# ---------------------------------------------------------------------------

class TestBulletRewriterConfig:
    """Verify GenerateContentConfig passed to generate_content."""

    @patch("src.integrations.gemini_client.get_rate_limiter")
    @patch("src.integrations.gemini_client.genai")
    @patch("src.integrations.gemini_client.get_config")
    def test_no_response_mime_type_in_config(self, mock_config, mock_genai, mock_rl):
        """response_mime_type must be omitted — thinking models produce empty arrays with it."""
        mock_config.return_value = MagicMock(
            get=lambda key, default=None: {
                "gemini.enabled": True,
                "gemini.api_key": "fake-key",
                "targeting.gemini.model": "gemini-3-flash-preview",
                "targeting.gemini.temperature": 0.35,
                "targeting.gemini.max_tokens": 8192,
            }.get(key, default)
        )

        # Build a realistic mock response
        mock_part = MagicMock()
        mock_part.text = json.dumps({
            "analysis": "Good match",
            "suggestions": [{"original": "Led team", "rewritten": "Led cross-functional team of 8", "reasoning": "Added specifics"}]
        })
        mock_candidate = MagicMock()
        mock_candidate.content.parts = [mock_part]
        mock_candidate.finish_reason = MagicMock(name="STOP")
        mock_response = MagicMock()
        mock_response.candidates = [mock_candidate]
        mock_response.text = mock_part.text

        # Make call_with_retry invoke the function and capture the config
        captured_configs = []

        def capture_call(fn, **kwargs):
            captured_configs.append(kwargs.get("config"))
            return mock_response

        mock_rl.return_value = MagicMock()
        mock_rl.return_value.call_with_retry = capture_call

        from src.integrations.gemini_client import GeminiBulletRewriter
        rewriter = GeminiBulletRewriter()

        result = rewriter.rewrite_bullet(
            original_bullet="Led team projects",
            score=0.5,
            job_title="Senior PM",
            company="Acme",
            job_description="Looking for a senior PM with leadership experience.",
            role_title="Product Manager",
            role_company="OldCo",
        )

        assert len(captured_configs) == 1, "Expected exactly one generate_content call"
        config = captured_configs[0]

        # The critical assertion: response_mime_type must NOT be set
        assert config.response_mime_type is None, (
            f"response_mime_type must be None for thinking models, got: {config.response_mime_type}"
        )

        # Verify result parsed correctly
        assert result["suggestions"], "Should have parsed suggestions from free-form response"

    @patch("src.integrations.gemini_client.get_rate_limiter")
    @patch("src.integrations.gemini_client.genai")
    @patch("src.integrations.gemini_client.get_config")
    def test_max_output_tokens_default_8192(self, mock_config, mock_genai, mock_rl):
        """max_output_tokens must default to 8192 for thinking model headroom."""
        mock_config.return_value = MagicMock(
            get=lambda key, default=None: {
                "gemini.enabled": True,
                "gemini.api_key": "fake-key",
                "targeting.gemini.model": "gemini-3-flash-preview",
                "targeting.gemini.temperature": 0.35,
                # NOT setting targeting.gemini.max_tokens — should use default
            }.get(key, default)
        )

        from src.integrations.gemini_client import GeminiBulletRewriter
        rewriter = GeminiBulletRewriter()

        assert rewriter.max_tokens == 8192, (
            f"Default max_tokens should be 8192 for thinking models, got: {rewriter.max_tokens}"
        )


# ---------------------------------------------------------------------------
# Fix #1 follow-up: clean_json_text handles free-form thinking model output
# ---------------------------------------------------------------------------

class TestCleanJsonTextFreeForm:
    """Verify clean_json_text handles responses without response_mime_type constraint."""

    def test_markdown_wrapped_json(self):
        """Thinking models often wrap JSON in markdown code blocks."""
        raw = '```json\n{"analysis": "Good", "suggestions": [{"original": "x", "rewritten": "y", "reasoning": "z"}]}\n```'
        result = json.loads(clean_json_text(raw))
        assert result["analysis"] == "Good"
        assert len(result["suggestions"]) == 1

    def test_thinking_preamble_then_json(self):
        """Model may output reasoning text before the JSON."""
        raw = (
            "Let me analyze this bullet point.\n\n"
            '{"analysis": "Needs metrics", "suggestions": [{"original": "Led projects", "rewritten": "Led 5 cross-functional projects", "reasoning": "Added count"}]}'
        )
        result = json.loads(clean_json_text(raw))
        assert result["analysis"] == "Needs metrics"

    def test_plain_json(self):
        """Clean JSON should pass through unchanged."""
        raw = '{"analysis": "Fine", "suggestions": []}'
        result = json.loads(clean_json_text(raw))
        assert result["analysis"] == "Fine"

    def test_trailing_text_after_json(self):
        """Model may add commentary after JSON."""
        raw = '{"analysis": "OK", "suggestions": []}\n\nHope this helps!'
        result = json.loads(clean_json_text(raw))
        assert result["analysis"] == "OK"
