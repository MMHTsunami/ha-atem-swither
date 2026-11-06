"""Constants for the ATEM Switcher integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "atem_switcher"
MANUFACTURER = "Blackmagic Design"
DEFAULT_PORT = 9910
CONNECTION_TIMEOUT = 10
PLATFORMS = ["binary_sensor", "select", "sensor"]
UPDATE_INTERVAL = timedelta(seconds=30)

AUX_OUTPUT_SOURCE_ID_BASE = 8001
ME_OUTPUT_SOURCE_ID_BASE = 5010
PROGRAM_OUTPUT_SOURCE_IDS = (10010, 4000)
PREVIEW_OUTPUT_SOURCE_IDS = (10011, 4010)
