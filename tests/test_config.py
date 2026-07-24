"""Unit tests for video_tool.config module.

Covers credential management, LLM config, credential validation, and masking.
The get_credential() env-var fallback is new in the PR refactor/project-audit-fixes;
tests for that behavior are SKIP-marked until the PR is merged.
"""

import stat
from pathlib import Path

import pytest

from video_tool.config import (
    CREDENTIAL_KEYS,
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    _is_valid_credential,
    clear_credentials,
    get_credential,
    load_config,
    load_credentials,
    mask_credential,
    save_credentials,
    set_credential,
)

# Check if the PR's env-var fallback is available
try:
    # In the PR, get_credential falls back to env vars when keys are missing in yaml.
    # On master, it only checks credentials.yaml.
    _CFG_HAS_ENV_FALLBACK = "bunny_video_id" in CREDENTIAL_KEYS
except Exception:
    _CFG_HAS_ENV_FALLBACK = False


class TestCredentialKeysRegistry:
    """Test that CREDENTIAL_KEYS is correctly structured."""

    def test_all_current_keys_present(self) -> None:
        """Verify keys that exist on both master and PR."""
        assert "openai_api_key" in CREDENTIAL_KEYS
        assert "groq_api_key" in CREDENTIAL_KEYS
        assert "bunny_library_id" in CREDENTIAL_KEYS
        assert "bunny_access_key" in CREDENTIAL_KEYS
        assert "bunny_collection_id" in CREDENTIAL_KEYS
        assert "replicate_api_token" in CREDENTIAL_KEYS
        assert "x_api_key" in CREDENTIAL_KEYS
        assert "x_api_secret" in CREDENTIAL_KEYS
        assert "x_access_token" in CREDENTIAL_KEYS
        assert "x_access_token_secret" in CREDENTIAL_KEYS
        assert "linkedin_access_token" in CREDENTIAL_KEYS
        assert "linkedin_author_urn" in CREDENTIAL_KEYS

    @pytest.mark.skipif(
        not _CFG_HAS_ENV_FALLBACK,
        reason="bunny_video_id/bunny_caption_language keys added in PR refactor/project-audit-fixes",
    )
    def test_new_bunny_keys_are_registered(self) -> None:
        """PR adds bunny_video_id and bunny_caption_language."""
        assert "bunny_video_id" in CREDENTIAL_KEYS
        assert "bunny_caption_language" in CREDENTIAL_KEYS

    @pytest.mark.skipif(
        not _CFG_HAS_ENV_FALLBACK,
        reason="bunny_video_id/bunny_caption_language keys added in PR",
    )
    def test_bunny_video_id_maps_to_env_var(self) -> None:
        assert CREDENTIAL_KEYS["bunny_video_id"] == "BUNNY_VIDEO_ID"

    @pytest.mark.skipif(
        not _CFG_HAS_ENV_FALLBACK,
        reason="bunny_video_id/bunny_caption_language keys added in PR",
    )
    def test_bunny_caption_language_maps_to_env_var(self) -> None:
        assert CREDENTIAL_KEYS["bunny_caption_language"] == "BUNNY_CAPTION_LANGUAGE"

    def test_all_env_var_values_are_upper_snake(self) -> None:
        for key, env_var in CREDENTIAL_KEYS.items():
            assert env_var == env_var.upper(), f"Env var for {key} should be uppercase: {env_var}"


class TestGetCredentialCurrentBehavior:
    """Test get_credential behavior.

    get_credential checks credentials.yaml first, then falls back to
    environment variables (this behavior was added by the PR).
    """

    def test_returns_credential_from_yaml(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("video_tool.config.CREDENTIALS_PATH", tmp_path / "creds.yaml")
        save_credentials({"openai_api_key": "sk-test12345678"})
        # Even with env var set, yaml should take precedence
        monkeypatch.setenv("OPENAI_API_KEY", "sk-from-env-should-not-win")
        result = get_credential("openai_api_key")
        assert result == "sk-test12345678"

    def test_returns_none_when_key_missing_everywhere(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("video_tool.config.CREDENTIALS_PATH", tmp_path / "creds.yaml")
        # Clear the env var too
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        result = get_credential("openai_api_key")
        assert result is None

    def test_invalid_credential_in_yaml_falls_back_to_env(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("video_tool.config.CREDENTIALS_PATH", tmp_path / "creds.yaml")
        save_credentials({"openai_api_key": "..."})  # Invalid per _is_valid_credential
        monkeypatch.setenv("OPENAI_API_KEY", "sk-valid-fallback-key")
        result = get_credential("openai_api_key")
        assert result == "sk-valid-fallback-key"

    def test_returns_none_for_unknown_key_even_with_env(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("video_tool.config.CREDENTIALS_PATH", tmp_path / "creds.yaml")
        # Unknown key has no env var mapping, so should always return None
        result = get_credential("totally_unknown_key_xyz")
        assert result is None


class TestGetCredentialEnvFallback:
    """Test get_credential env var fallback (new in PR refactor/project-audit-fixes).

    These tests verify that after the PR merge, credentials.yaml still takes
    precedence over env vars, but env vars serve as fallback.
    """

    @pytest.mark.skipif(
        not _CFG_HAS_ENV_FALLBACK,
        reason="env-var fallback in get_credential added in PR refactor/project-audit-fixes",
    )
    def test_falls_back_to_env_var_when_yaml_empty(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("video_tool.config.CREDENTIALS_PATH", tmp_path / "creds.yaml")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-from-env-12345")
        result = get_credential("openai_api_key")
        assert result == "sk-from-env-12345"

    @pytest.mark.skipif(
        not _CFG_HAS_ENV_FALLBACK,
        reason="env-var fallback added in PR",
    )
    def test_yaml_takes_precedence_over_env_var(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("video_tool.config.CREDENTIALS_PATH", tmp_path / "creds.yaml")
        save_credentials({"openai_api_key": "sk-from-yaml-12345"})
        monkeypatch.setenv("OPENAI_API_KEY", "sk-from-env-67890")
        result = get_credential("openai_api_key")
        assert result == "sk-from-yaml-12345"

    @pytest.mark.skipif(
        not _CFG_HAS_ENV_FALLBACK,
        reason="env-var fallback added in PR",
    )
    def test_invalid_yaml_credential_falls_back_to_env(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("video_tool.config.CREDENTIALS_PATH", tmp_path / "creds.yaml")
        save_credentials({"openai_api_key": "..."})  # Invalid
        monkeypatch.setenv("OPENAI_API_KEY", "sk-valid-key-12345")
        result = get_credential("openai_api_key")
        assert result == "sk-valid-key-12345"

    @pytest.mark.skipif(
        not _CFG_HAS_ENV_FALLBACK,
        reason="env-var fallback added in PR",
    )
    def test_env_var_whitespace_is_stripped(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("video_tool.config.CREDENTIALS_PATH", tmp_path / "creds.yaml")
        monkeypatch.setenv("OPENAI_API_KEY", "  sk-whitespace-key  ")
        result = get_credential("openai_api_key")
        assert result == "sk-whitespace-key"

    @pytest.mark.skipif(
        not _CFG_HAS_ENV_FALLBACK,
        reason="env-var fallback added in PR",
    )
    def test_empty_env_var_is_skipped(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("video_tool.config.CREDENTIALS_PATH", tmp_path / "creds.yaml")
        monkeypatch.setenv("OPENAI_API_KEY", "")
        result = get_credential("openai_api_key")
        assert result is None

    @pytest.mark.skipif(
        not _CFG_HAS_ENV_FALLBACK,
        reason="bunny keys added in PR",
    )
    def test_bunny_keys_use_env_fallback(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("video_tool.config.CREDENTIALS_PATH", tmp_path / "creds.yaml")
        monkeypatch.setenv("BUNNY_VIDEO_ID", "test-video-id-abc")
        monkeypatch.setenv("BUNNY_CAPTION_LANGUAGE", "fr")
        result_video = get_credential("bunny_video_id")
        result_lang = get_credential("bunny_caption_language")
        assert result_video == "test-video-id-abc"
        assert result_lang == "fr"


class TestIsValidCredential:
    """Test the _is_valid_credential helper (works on both branches)."""

    @pytest.mark.parametrize(
        "value,expected",
        [
            (None, False),
            ("", False),
            ("  ", False),
            ("...", False),
            ("Ellipsis", False),
            ("None", False),
            ("null", False),
            ("undefined", False),
            ("abc", False),  # Too short
            ("sk-valid-key", True),
            ("test1234", True),
            ("  test1234  ", True),
        ],
    )
    def test_credential_validation(self, value: str, expected: bool) -> None:
        result = _is_valid_credential(value)
        assert result is expected


class TestMaskCredential:
    """Test credential masking (works on both branches)."""

    def test_mask_short_value(self) -> None:
        assert mask_credential("abc") == "***"

    def test_mask_long_value(self) -> None:
        assert mask_credential("sk-abcdefgh12345678") == "sk-a...5678"

    def test_mask_none(self) -> None:
        assert mask_credential(None) == "***"

    def test_mask_empty(self) -> None:
        assert mask_credential("") == "***"


class TestSetCredential:
    """Test non-interactive credential setting."""

    def test_set_valid_credential(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("video_tool.config.CREDENTIALS_PATH", tmp_path / "creds.yaml")
        result = set_credential("openai_api_key", "sk-new-key-12345")
        assert result is True

    def test_set_invalid_key_name(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("video_tool.config.CREDENTIALS_PATH", tmp_path / "creds.yaml")
        result = set_credential("nonexistent_key", "value")
        assert result is False

    def test_set_invalid_credential_value(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("video_tool.config.CREDENTIALS_PATH", tmp_path / "creds.yaml")
        result = set_credential("openai_api_key", "...")
        assert result is False


class TestLoadAndSaveCredentials:
    """Test credentials file persistence."""

    def test_roundtrip_save_load(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        creds_path = tmp_path / "creds.yaml"
        monkeypatch.setattr("video_tool.config.CREDENTIALS_PATH", creds_path)
        creds = {"openai_api_key": "sk-1234567890", "groq_api_key": "gsk-abcdef1234567890"}
        save_credentials(creds)
        loaded = load_credentials()
        assert loaded == creds

    def test_load_missing_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("video_tool.config.CREDENTIALS_PATH", tmp_path / "nonexistent.yaml")
        assert load_credentials() == {}

    def test_save_sets_permissions(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        creds_path = tmp_path / "creds.yaml"
        monkeypatch.setattr("video_tool.config.CREDENTIALS_PATH", creds_path)
        save_credentials({"openai_api_key": "sk-test12345678"})
        mode = creds_path.stat().st_mode
        assert mode & stat.S_IRGRP == 0
        assert mode & stat.S_IWGRP == 0
        assert mode & stat.S_IROTH == 0
        assert mode & stat.S_IWOTH == 0

    def test_clear_credentials(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        creds_path = tmp_path / "creds.yaml"
        monkeypatch.setattr("video_tool.config.CREDENTIALS_PATH", creds_path)
        save_credentials({"openai_api_key": "sk-test12345678"})
        assert creds_path.exists()
        clear_credentials()
        assert not creds_path.exists()


class TestLLMConfig:
    """Test LLM configuration management."""

    def test_load_config_defaults(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("video_tool.config.CONFIG_PATH", tmp_path / "config.yaml")
        config = load_config()
        assert config["llm"]["default"]["base_url"] == DEFAULT_BASE_URL
        assert config["llm"]["default"]["model"] == DEFAULT_MODEL

    def test_set_and_get_llm_config(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("video_tool.config.CONFIG_DIR", tmp_path / "config_dir")
        monkeypatch.setattr("video_tool.config.CONFIG_PATH", tmp_path / "config_dir" / "config.yaml")
        from video_tool.config import get_llm_config, set_llm_config
        set_llm_config("description", base_url="https://custom.api.com", model="gpt-4o-mini")
        config = get_llm_config("description")
        assert config.base_url == "https://custom.api.com"
        assert config.model == "gpt-4o-mini"
