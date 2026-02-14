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

if bashio::config.has_value 'device_id'; then
  export DEVICE_ID="$(bashio::config 'device_id')"
fi

exec python -m edge.src.main
