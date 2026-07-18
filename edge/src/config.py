"""
Edge daemon configuration loaded from environment variables.

Uses Pydantic BaseSettings for automatic env var loading and validation.
All configuration values come from environment variables or .env files;
no hardcoded IPs, URLs, or credentials.

CHANGELOG:
- 2026-07-18: Add battery control settings (opt-in, dry-run by default)
- 2026-02-14: Add raw debug snapshot configuration for Modbus payload inspection
- 2026-02-14: Initial creation (STORY-001)

TODO:
- None
"""

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings


class EdgeSettings(BaseSettings):
    """Edge daemon configuration for Sungrow-to-VPS pipeline.

    All values are loaded from environment variables. Required variables
    must be set; optional variables have sensible defaults.

    Attributes:
        sungrow_host: WiNet-S IP address / hostname on local LAN.
        sungrow_port: Modbus TCP port (default 502).
        sungrow_slave_id: Modbus slave / unit ID (default 1).
        poll_interval_s: Seconds between Modbus poll cycles (min 5, HC-004).
        inter_register_delay_ms: Milliseconds between register group reads
            within a single poll cycle (default 20, HC-004).
        vps_base_url: VPS base URL for ingestion (must be HTTPS, HC-003).
        vps_device_token: Per-device bearer token for VPS auth.
        device_id: Device identifier sent in samples. Defaults to
            sungrow_host if not set.
        batch_size: Max samples per upload batch.
        upload_interval_s: Seconds between upload attempts.
        spool_path: SQLite spool file path for local buffering.
        raw_debug_enabled: If True, logs periodic raw register snapshots.
        raw_debug_every_n_polls: Snapshot frequency (every N poll attempts).
    """

    sungrow_host: str
    sungrow_port: int = 502
    sungrow_slave_id: int = 1
    poll_interval_s: int = 5
    inter_register_delay_ms: int = 20
    vps_base_url: str
    vps_device_token: str
    device_id: str = ""
    batch_size: int = 30
    upload_interval_s: int = 10
    spool_path: str = "/data/spool.db"
    raw_debug_enabled: bool = False
    raw_debug_every_n_polls: int = 60

    # --- Home Assistant local-MQTT publishing (opt-in; off by default) ---
    # When disabled the daemon behaves exactly as before — no broker
    # connection, no behaviour change to the VPS upload path.
    mqtt_enabled: bool = False
    mqtt_host: str = "core-mosquitto"
    mqtt_port: int = 1883
    mqtt_username: str = ""
    mqtt_password: str = ""
    mqtt_discovery_prefix: str = "homeassistant"
    mqtt_base_topic: str = "sungrow_edge"

    # --- Battery control (opt-in; dry-run by default) ---
    # When control_enabled the daemon exposes the control API and runs the
    # deadman watchdog. control_dry_run=True audits the full command
    # lifecycle without ever writing to Modbus.
    control_enabled: bool = False
    control_dry_run: bool = True
    control_api_token: str = ""
    control_api_port: int = 8402
    control_max_charge_w: int = 4000
    control_max_discharge_w: int = 6600
    control_min_soc_pct: float = 12.0
    control_max_soc_pct: float = 100.0
    control_max_ttl_s: int = 21600
    control_state_path: str = "/data/control-state.json"
    control_audit_path: str = "/data/control-audit.jsonl"

    @model_validator(mode="after")
    def _default_device_id(self) -> "EdgeSettings":
        """Default device_id to sungrow_host when not explicitly set."""
        if not self.device_id:
            self.device_id = self.sungrow_host
        return self

    @model_validator(mode="after")
    def _control_requires_token(self) -> "EdgeSettings":
        """An enabled control API without a token would be an open door."""
        if self.control_enabled and not self.control_api_token:
            raise ValueError(
                "CONTROL_API_TOKEN must be set when CONTROL_ENABLED is true"
            )
        return self

    @model_validator(mode="after")
    def _control_soc_bounds_sane(self) -> "EdgeSettings":
        """SOC floor must sit below the ceiling, both within 0-100."""
        if not (0.0 <= self.control_min_soc_pct < self.control_max_soc_pct <= 100.0):
            raise ValueError(
                "CONTROL_MIN_SOC_PCT must be < CONTROL_MAX_SOC_PCT, both in 0-100"
            )
        return self

    @field_validator("control_api_port")
    @classmethod
    def control_api_port_must_be_valid(cls, v: int) -> int:
        """Validate control API port is in valid range."""
        if v < 1 or v > 65535:
            raise ValueError("CONTROL_API_PORT must be between 1 and 65535")
        return v

    @field_validator("control_max_ttl_s")
    @classmethod
    def control_max_ttl_must_be_sane(cls, v: int) -> int:
        """TTL ceiling must allow at least the 60s minimum command."""
        if v < 60:
            raise ValueError("CONTROL_MAX_TTL_S must be >= 60")
        return v

    @field_validator("vps_base_url")
    @classmethod
    def vps_base_url_must_be_https(cls, v: str) -> str:
        """Validate that VPS base URL uses HTTPS (HC-003).

        All edge-to-VPS communication must use HTTPS with valid certificates.
        HTTP URLs are rejected at startup to prevent insecure transport.
        """
        if not v.startswith("https://"):
            raise ValueError(
                "VPS_BASE_URL must use HTTPS (got: "
                f"'{v[:20]}...'). See HC-003: HTTPS Only."
            )
        return v

    @field_validator("poll_interval_s")
    @classmethod
    def poll_interval_must_respect_winet_s(cls, v: int) -> int:
        """Validate poll interval respects WiNet-S stability (HC-004).

        Minimum 5-second interval to avoid overloading the WiNet-S dongle.
        """
        if v < 5:
            raise ValueError("POLL_INTERVAL_S must be >= 5 (HC-004: WiNet-S stability)")
        return v

    @field_validator("batch_size")
    @classmethod
    def batch_size_must_be_valid(cls, v: int) -> int:
        """Validate batch size is between 1 and 1000."""
        if v < 1 or v > 1000:
            raise ValueError("BATCH_SIZE must be >= 1 and <= 1000")
        return v

    @field_validator("sungrow_port")
    @classmethod
    def sungrow_port_must_be_valid(cls, v: int) -> int:
        """Validate Modbus TCP port is in valid range."""
        if v < 1 or v > 65535:
            raise ValueError("SUNGROW_PORT must be between 1 and 65535")
        return v

    @field_validator("mqtt_port")
    @classmethod
    def mqtt_port_must_be_valid(cls, v: int) -> int:
        """Validate MQTT TCP port is in valid range."""
        if v < 1 or v > 65535:
            raise ValueError("MQTT_PORT must be between 1 and 65535")
        return v

    @field_validator("sungrow_slave_id")
    @classmethod
    def sungrow_slave_id_must_be_valid(cls, v: int) -> int:
        """Validate Modbus slave ID is in valid range (1-247)."""
        if v < 1 or v > 247:
            raise ValueError("SUNGROW_SLAVE_ID must be between 1 and 247")
        return v

    @field_validator("inter_register_delay_ms")
    @classmethod
    def inter_register_delay_must_be_non_negative(cls, v: int) -> int:
        """Validate inter-register delay is non-negative."""
        if v < 0:
            raise ValueError("INTER_REGISTER_DELAY_MS must be >= 0")
        return v

    @field_validator("raw_debug_every_n_polls")
    @classmethod
    def raw_debug_every_n_polls_must_be_positive(cls, v: int) -> int:
        """Validate raw snapshot interval is positive."""
        if v < 1:
            raise ValueError("RAW_DEBUG_EVERY_N_POLLS must be >= 1")
        return v

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}
