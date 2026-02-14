"""
Unit tests for edge daemon configuration (EdgeSettings).

Tests verify:
- Config loads from environment variables with correct defaults.
- Config validation rejects missing required variables.
- VPS_BASE_URL is validated as HTTPS (HC-003).
- Numeric constraints are enforced (poll_interval, batch_size, port, slave_id).
- DEVICE_ID defaults to SUNGROW_HOST when not set.

CHANGELOG:
- 2026-02-14: Initial creation (STORY-001)

TODO:
- None
"""

import pytest
from edge.src.config import EdgeSettings
from pydantic import ValidationError


class TestEdgeSettingsLoadsFromEnv:
    """Config loads all values from environment variables."""

    def test_loads_all_env_vars(self, env_vars_full: dict[str, str]) -> None:
        """All env vars are read and assigned correctly."""
        settings = EdgeSettings()

        assert settings.sungrow_host == env_vars_full["SUNGROW_HOST"]
        assert settings.sungrow_port == int(env_vars_full["SUNGROW_PORT"])
        assert settings.sungrow_slave_id == int(env_vars_full["SUNGROW_SLAVE_ID"])
        assert settings.poll_interval_s == int(env_vars_full["POLL_INTERVAL_S"])
        assert settings.inter_register_delay_ms == int(
            env_vars_full["INTER_REGISTER_DELAY_MS"]
        )
        assert settings.vps_base_url == env_vars_full["VPS_BASE_URL"]
        assert settings.vps_device_token == env_vars_full["VPS_DEVICE_TOKEN"]
        assert settings.device_id == env_vars_full["DEVICE_ID"]
        assert settings.batch_size == int(env_vars_full["BATCH_SIZE"])
        assert settings.upload_interval_s == int(env_vars_full["UPLOAD_INTERVAL_S"])
        assert settings.spool_path == env_vars_full["SPOOL_PATH"]

    def test_defaults_applied_when_optional_vars_missing(
        self, env_vars_required_only: dict[str, str]
    ) -> None:
        """Optional variables use default values when not set."""
        settings = EdgeSettings()

        assert settings.sungrow_host == env_vars_required_only["SUNGROW_HOST"]
        assert settings.vps_base_url == env_vars_required_only["VPS_BASE_URL"]
        assert settings.vps_device_token == env_vars_required_only["VPS_DEVICE_TOKEN"]
        # Defaults from Architecture.md
        assert settings.sungrow_port == 502
        assert settings.sungrow_slave_id == 1
        assert settings.poll_interval_s == 5
        assert settings.inter_register_delay_ms == 20
        assert settings.batch_size == 30
        assert settings.upload_interval_s == 10
        assert settings.spool_path == "/data/spool.db"


class TestEdgeSettingsRequiredVars:
    """Config validation rejects missing required variables."""

    def test_missing_sungrow_host_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """SUNGROW_HOST is required."""
        monkeypatch.setenv("VPS_BASE_URL", "https://example.com")
        monkeypatch.setenv("VPS_DEVICE_TOKEN", "device-token")

        with pytest.raises(ValidationError) as exc_info:
            EdgeSettings()
        assert "sungrow_host" in str(exc_info.value).lower()

    def test_missing_vps_base_url_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """VPS_BASE_URL is required."""
        monkeypatch.setenv("SUNGROW_HOST", "192.168.1.1")
        monkeypatch.setenv("VPS_DEVICE_TOKEN", "device-token")

        with pytest.raises(ValidationError) as exc_info:
            EdgeSettings()
        assert "vps_base_url" in str(exc_info.value).lower()

    def test_missing_vps_device_token_raises(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """VPS_DEVICE_TOKEN is required."""
        monkeypatch.setenv("SUNGROW_HOST", "192.168.1.1")
        monkeypatch.setenv("VPS_BASE_URL", "https://example.com")

        with pytest.raises(ValidationError) as exc_info:
            EdgeSettings()
        assert "vps_device_token" in str(exc_info.value).lower()

    def test_missing_all_required_raises(self) -> None:
        """All three required vars missing causes validation error."""
        with pytest.raises(ValidationError) as exc_info:
            EdgeSettings()
        errors = str(exc_info.value).lower()
        assert "sungrow_host" in errors
        assert "vps_base_url" in errors
        assert "vps_device_token" in errors


class TestVpsBaseUrlHttpsValidation:
    """VPS_BASE_URL must be HTTPS per HC-003."""

    def test_http_url_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """HTTP URL is rejected with a clear error message."""
        monkeypatch.setenv("SUNGROW_HOST", "192.168.1.1")
        monkeypatch.setenv("VPS_BASE_URL", "http://insecure.example.com")
        monkeypatch.setenv("VPS_DEVICE_TOKEN", "device-token")

        with pytest.raises(ValidationError) as exc_info:
            EdgeSettings()
        assert "https" in str(exc_info.value).lower()

    def test_https_url_accepted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """HTTPS URL passes validation."""
        monkeypatch.setenv("SUNGROW_HOST", "192.168.1.1")
        monkeypatch.setenv("VPS_BASE_URL", "https://secure.example.com")
        monkeypatch.setenv("VPS_DEVICE_TOKEN", "device-token")

        settings = EdgeSettings()
        assert settings.vps_base_url == "https://secure.example.com"

    def test_empty_url_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Empty string is not a valid HTTPS URL."""
        monkeypatch.setenv("SUNGROW_HOST", "192.168.1.1")
        monkeypatch.setenv("VPS_BASE_URL", "")
        monkeypatch.setenv("VPS_DEVICE_TOKEN", "device-token")

        with pytest.raises(ValidationError) as exc_info:
            EdgeSettings()
        assert "https" in str(exc_info.value).lower()

    def test_ftp_url_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Non-HTTP schemes (ftp, etc.) are rejected."""
        monkeypatch.setenv("SUNGROW_HOST", "192.168.1.1")
        monkeypatch.setenv("VPS_BASE_URL", "ftp://files.example.com")
        monkeypatch.setenv("VPS_DEVICE_TOKEN", "device-token")

        with pytest.raises(ValidationError) as exc_info:
            EdgeSettings()
        assert "https" in str(exc_info.value).lower()


class TestDeviceIdConfig:
    """DEVICE_ID defaults to sungrow_host but can be overridden."""

    def test_device_id_defaults_to_sungrow_host(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When DEVICE_ID is not set, it defaults to SUNGROW_HOST."""
        monkeypatch.setenv("SUNGROW_HOST", "192.168.1.5")
        monkeypatch.setenv("VPS_BASE_URL", "https://example.com")
        monkeypatch.setenv("VPS_DEVICE_TOKEN", "device-token")

        settings = EdgeSettings()
        assert settings.device_id == "192.168.1.5"

    def test_device_id_explicit_overrides_host(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Explicit DEVICE_ID overrides the sungrow_host default."""
        monkeypatch.setenv("SUNGROW_HOST", "192.168.1.5")
        monkeypatch.setenv("VPS_BASE_URL", "https://example.com")
        monkeypatch.setenv("VPS_DEVICE_TOKEN", "device-token")
        monkeypatch.setenv("DEVICE_ID", "my-sungrow-inverter")

        settings = EdgeSettings()
        assert settings.device_id == "my-sungrow-inverter"


class TestNumericConstraints:
    """Numeric configuration values must be within valid ranges."""

    def test_poll_interval_below_minimum_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """POLL_INTERVAL_S must be >= 5 (HC-004: WiNet-S stability)."""
        monkeypatch.setenv("SUNGROW_HOST", "192.168.1.1")
        monkeypatch.setenv("VPS_BASE_URL", "https://example.com")
        monkeypatch.setenv("VPS_DEVICE_TOKEN", "device-token")
        monkeypatch.setenv("POLL_INTERVAL_S", "4")

        with pytest.raises(ValidationError) as exc_info:
            EdgeSettings()
        assert "poll_interval_s" in str(exc_info.value).lower()

    def test_poll_interval_zero_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """POLL_INTERVAL_S of 0 is rejected."""
        monkeypatch.setenv("SUNGROW_HOST", "192.168.1.1")
        monkeypatch.setenv("VPS_BASE_URL", "https://example.com")
        monkeypatch.setenv("VPS_DEVICE_TOKEN", "device-token")
        monkeypatch.setenv("POLL_INTERVAL_S", "0")

        with pytest.raises(ValidationError):
            EdgeSettings()

    def test_poll_interval_negative_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Negative POLL_INTERVAL_S is rejected."""
        monkeypatch.setenv("SUNGROW_HOST", "192.168.1.1")
        monkeypatch.setenv("VPS_BASE_URL", "https://example.com")
        monkeypatch.setenv("VPS_DEVICE_TOKEN", "device-token")
        monkeypatch.setenv("POLL_INTERVAL_S", "-1")

        with pytest.raises(ValidationError):
            EdgeSettings()

    def test_poll_interval_minimum_accepted(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """POLL_INTERVAL_S of exactly 5 is accepted (minimum for HC-004)."""
        monkeypatch.setenv("SUNGROW_HOST", "192.168.1.1")
        monkeypatch.setenv("VPS_BASE_URL", "https://example.com")
        monkeypatch.setenv("VPS_DEVICE_TOKEN", "device-token")
        monkeypatch.setenv("POLL_INTERVAL_S", "5")

        settings = EdgeSettings()
        assert settings.poll_interval_s == 5

    def test_batch_size_zero_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """BATCH_SIZE must be >= 1."""
        monkeypatch.setenv("SUNGROW_HOST", "192.168.1.1")
        monkeypatch.setenv("VPS_BASE_URL", "https://example.com")
        monkeypatch.setenv("VPS_DEVICE_TOKEN", "device-token")
        monkeypatch.setenv("BATCH_SIZE", "0")

        with pytest.raises(ValidationError) as exc_info:
            EdgeSettings()
        assert "batch_size" in str(exc_info.value).lower()

    def test_batch_size_over_1000_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """BATCH_SIZE must be <= 1000."""
        monkeypatch.setenv("SUNGROW_HOST", "192.168.1.1")
        monkeypatch.setenv("VPS_BASE_URL", "https://example.com")
        monkeypatch.setenv("VPS_DEVICE_TOKEN", "device-token")
        monkeypatch.setenv("BATCH_SIZE", "1001")

        with pytest.raises(ValidationError) as exc_info:
            EdgeSettings()
        assert "batch_size" in str(exc_info.value).lower()

    def test_sungrow_port_invalid_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """SUNGROW_PORT must be between 1 and 65535."""
        monkeypatch.setenv("SUNGROW_HOST", "192.168.1.1")
        monkeypatch.setenv("VPS_BASE_URL", "https://example.com")
        monkeypatch.setenv("VPS_DEVICE_TOKEN", "device-token")
        monkeypatch.setenv("SUNGROW_PORT", "0")

        with pytest.raises(ValidationError) as exc_info:
            EdgeSettings()
        assert "sungrow_port" in str(exc_info.value).lower()

    def test_sungrow_port_over_65535_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """SUNGROW_PORT above 65535 is rejected."""
        monkeypatch.setenv("SUNGROW_HOST", "192.168.1.1")
        monkeypatch.setenv("VPS_BASE_URL", "https://example.com")
        monkeypatch.setenv("VPS_DEVICE_TOKEN", "device-token")
        monkeypatch.setenv("SUNGROW_PORT", "70000")

        with pytest.raises(ValidationError) as exc_info:
            EdgeSettings()
        assert "sungrow_port" in str(exc_info.value).lower()

    def test_valid_custom_numeric_values(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Custom valid numeric values are accepted."""
        monkeypatch.setenv("SUNGROW_HOST", "192.168.1.1")
        monkeypatch.setenv("VPS_BASE_URL", "https://example.com")
        monkeypatch.setenv("VPS_DEVICE_TOKEN", "device-token")
        monkeypatch.setenv("POLL_INTERVAL_S", "10")
        monkeypatch.setenv("BATCH_SIZE", "100")
        monkeypatch.setenv("UPLOAD_INTERVAL_S", "30")
        monkeypatch.setenv("SUNGROW_PORT", "1502")

        settings = EdgeSettings()
        assert settings.poll_interval_s == 10
        assert settings.batch_size == 100
        assert settings.upload_interval_s == 30
        assert settings.sungrow_port == 1502
