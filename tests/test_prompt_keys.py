"""Unit tests for prompt key integrity and content generation prompt access.

The PR renames YAML prompt keys from snake_case (generate_description) to
kebab-case (generate-description). On the current branch (master), the keys
are snake_case. After the merge, they become kebab-case. These tests verify
both states and will catch regressions.
"""

import yaml
from pathlib import Path
from unittest.mock import patch

import pytest

from video_tool.video_processor import VideoProcessor


PROMPTS_FILE = Path(__file__).resolve().parent.parent / "video_tool" / "prompts.yaml"

# Detect current key format by loading the yaml
_prompts_data = yaml.safe_load(PROMPTS_FILE.read_text(encoding="utf-8")) if PROMPTS_FILE.exists() else {}
# We check for kebab-case in the keys that matter (generate-description vs generate_description)
# The 'generate-timestamps-from-transcript' key has always been kebab-case, so we check
# the other keys that the PR changes.
_KEBAB_CASE_KEYS = {
    "generate-description", "polish-description", "generate-seo-keywords",
    "generate-linkedin-post", "generate-twitter-post", "generate-context-cards",
}
_SNAKE_CASE_KEYS = {
    "generate_description", "polish_description", "generate_seo_keywords",
    "generate_linkedin_post", "generate_twitter_post", "generate_context_cards",
}
_KEBAB_CASE = bool(_KEBAB_CASE_KEYS & set(_prompts_data.keys()))
_SNAKE_CASE = bool(_SNAKE_CASE_KEYS & set(_prompts_data.keys()))


class TestPromptsYamlKeys:
    """Verify that prompts.yaml uses consistent key naming."""

    def test_prompts_file_exists(self) -> None:
        assert PROMPTS_FILE.exists(), f"prompts.yaml not found at {PROMPTS_FILE}"

    def test_prompts_file_is_valid_yaml(self) -> None:
        content = PROMPTS_FILE.read_text(encoding="utf-8")
        data = yaml.safe_load(content)
        assert isinstance(data, dict)
        assert len(data) > 0

    def test_all_prompts_have_format_placeholders(self) -> None:
        content = PROMPTS_FILE.read_text(encoding="utf-8")
        data = yaml.safe_load(content)
        for key, value in data.items():
            if isinstance(value, str):
                assert "{" in value, f"Prompt '{key}' has no format placeholders"

    def test_all_prompts_are_strings(self) -> None:
        data = yaml.safe_load(PROMPTS_FILE.read_text(encoding="utf-8"))
        for key, value in data.items():
            assert isinstance(value, str), f"Prompt '{key}' is not a string"

    @pytest.mark.skipif(
        not _KEBAB_CASE,
        reason="Re-run after merging refactor/project-audit-fixes (kebab-case keys)",
    )
    def test_all_expected_kebab_case_keys_present(self) -> None:
        expected = {
            "generate-description",
            "polish-description",
            "generate-timestamps-from-transcript",
            "generate-seo-keywords",
            "generate-linkedin-post",
            "generate-twitter-post",
            "generate-context-cards",
        }
        missing = expected - set(_prompts_data.keys())
        assert not missing, f"Missing kebab-case prompt keys: {missing}"

    @pytest.mark.skipif(
        _KEBAB_CASE,
        reason="On master, snake_case keys are expected; skip after PR merge",
    )
    def test_old_snake_case_keys_still_present_on_master(self) -> None:
        """On master, keys are still snake_case — verify they work."""
        assert "generate_description" in _prompts_data, "Old snake_case keys missing on master"
        assert "polish_description" in _prompts_data

    @pytest.mark.skipif(
        not _KEBAB_CASE,
        reason="Re-run after merging refactor/project-audit-fixes (kebab-case keys)",
    )
    def test_no_old_snake_case_keys_after_merge(self) -> None:
        old_keys = {
            "generate_description",
            "polish_description",
            "generate_seo_keywords",
            "generate_linkedin_post",
            "generate_twitter_post",
            "generate_context_cards",
        }
        stale = old_keys & set(_prompts_data.keys())
        assert not stale, f"Old snake_case keys still present: {stale}"


class TestContentGenerationWithProcessor:
    """Test that VideoProcessor loads prompts and can format them."""

    @pytest.fixture
    def processor(self, tmp_path):
        with patch("video_tool.video_processor.base.OpenAI"), \
             patch("video_tool.video_processor.base.Groq"), \
             patch("video_tool.config.get_credential", return_value="test-key"):
            proc = VideoProcessor(str(tmp_path))
            return proc

    def test_processor_loads_prompts(self, processor) -> None:
        prompts = processor.prompts
        assert isinstance(prompts, dict)
        assert len(prompts) > 0

    def test_description_prompt_exists(self, processor) -> None:
        prompts = processor.prompts
        # On master: generate_description; on PR: generate-description
        key = "generate-description" if "generate-description" in prompts else "generate_description"
        assert key in prompts
        prompt = prompts[key]
        assert "{transcript}" in prompt

    def test_polish_prompt_exists(self, processor) -> None:
        prompts = processor.prompts
        key = "polish-description" if "polish-description" in prompts else "polish_description"
        assert key in prompts
        prompt = prompts[key]
        assert "{description}" in prompt

    def test_seo_keywords_prompt_exists(self, processor) -> None:
        prompts = processor.prompts
        key = "generate-seo-keywords" if "generate-seo-keywords" in prompts else "generate_seo_keywords"
        assert key in prompts

    def test_linkedin_post_prompt_exists(self, processor) -> None:
        prompts = processor.prompts
        key = "generate-linkedin-post" if "generate-linkedin-post" in prompts else "generate_linkedin_post"
        assert key in prompts

    def test_twitter_post_prompt_exists(self, processor) -> None:
        prompts = processor.prompts
        key = "generate-twitter-post" if "generate-twitter-post" in prompts else "generate_twitter_post"
        assert key in prompts

    def test_context_cards_prompt_exists(self, processor) -> None:
        prompts = processor.prompts
        key = "generate-context-cards" if "generate-context-cards" in prompts else "generate_context_cards"
        assert key in prompts

    def test_timestamps_prompt_exists(self, processor) -> None:
        prompts = processor.prompts
        # This key is already kebab-case on both branches
        assert "generate-timestamps-from-transcript" in prompts

    def test_description_prompt_is_formatable(self, processor) -> None:
        prompts = processor.prompts
        key = "generate-description" if "generate-description" in prompts else "generate_description"
        prompt = prompts[key]
        formatted = prompt.format(transcript="This is a test transcript.")
        assert "This is a test transcript." in formatted
        assert "{transcript}" not in formatted

    def test_polish_prompt_is_formatable(self, processor) -> None:
        prompts = processor.prompts
        key = "polish-description" if "polish-description" in prompts else "polish_description"
        prompt = prompts[key]
        formatted = prompt.format(description="Polish this description content.")
        assert "Polish this description content." in formatted