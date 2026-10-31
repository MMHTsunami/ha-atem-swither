"""Constants for the ATEM Switcher integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "atem_switcher"
MANUFACTURER = "Blackmagic Design"
DEFAULT_PORT = 9910
CONNECTION_TIMEOUT = 10
PLATFORMS = ["binary_sensor", "select", "sensor"]
UPDATE_INTERVAL = timedelta(seconds=30)
