#!/usr/bin/with-contenv bashio
set -e

export SUNGROW_HOST="$(bashio::config 'sungrow_host')"
export VPS_BASE_URL="$(bashio::config 'vps_base_url')"
export VPS_DEVICE_TOKEN="$(bashio::config 'vps_device_token')"
export SUNGROW_PORT="$(bashio::config 'sungrow_port')"
export SUNGROW_SLAVE_ID="$(bashio::config 'sungrow_slave_id')"
export POLL_INTERVAL_S="$(bashio::config 'poll_interval_s')"
export INTER_REGISTER_DELAY_MS="$(bashio::config 'inter_register_delay_ms')"
export BATCH_SIZE="$(bashio::config 'batch_size')"
export UPLOAD_INTERVAL_S="$(bashio::config 'upload_interval_s')"
export SPOOL_PATH="$(bashio::config 'spool_path')"
export RAW_DEBUG_ENABLED="$(bashio::config 'raw_debug_enabled')"
export RAW_DEBUG_EVERY_N_POLLS="$(bashio::config 'raw_debug_every_n_polls')"

if bashio::config.has_value 'device_id'; then
  export DEVICE_ID="$(bashio::config 'device_id')"
fi

# --- Home Assistant local-MQTT publishing (opt-in) ---
export MQTT_ENABLED="$(bashio::config 'mqtt_enabled')"
export MQTT_HOST="$(bashio::config 'mqtt_host')"
export MQTT_PORT="$(bashio::config 'mqtt_port')"
export MQTT_DISCOVERY_PREFIX="$(bashio::config 'mqtt_discovery_prefix')"
export MQTT_BASE_TOPIC="$(bashio::config 'mqtt_base_topic')"
if bashio::config.has_value 'mqtt_username'; then
  export MQTT_USERNAME="$(bashio::config 'mqtt_username')"
fi
if bashio::config.has_value 'mqtt_password'; then
  export MQTT_PASSWORD="$(bashio::config 'mqtt_password')"
fi

# --- Battery control (opt-in; dry-run by default) ---
export CONTROL_ENABLED="$(bashio::config 'control_enabled')"
export CONTROL_DRY_RUN="$(bashio::config 'control_dry_run')"
export CONTROL_API_PORT="$(bashio::config 'control_api_port')"
if bashio::config.has_value 'control_api_token'; then
  export CONTROL_API_TOKEN="$(bashio::config 'control_api_token')"
fi

exec python -m edge.src.main
