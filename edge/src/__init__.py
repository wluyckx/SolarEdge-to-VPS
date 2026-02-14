"""
Edge daemon package for Sungrow-to-VPS pipeline.

Reads telemetry from Sungrow SH4.0RS hybrid inverter via WiNet-S Modbus TCP,
normalizes and buffers data locally, and uploads to VPS over HTTPS.

CHANGELOG:
- 2026-02-14: Initial creation (STORY-001)

TODO:
- None
"""
