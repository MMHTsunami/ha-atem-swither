"""Binary sensors for the ATEM Switcher integration."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN, MANUFACTURER
from .coordinator import AtemCoordinator

DESCRIPTION = BinarySensorEntityDescription(
    key="connection",
    name="Connection",
    device_class="connectivity",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ATEM connection sensors."""
    coordinator: AtemCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([AtemConnectionSensor(coordinator, entry)])


class AtemConnectionSensor(
    CoordinatorEntity[DataUpdateCoordinator[dict]], BinarySensorEntity
):
    """Represent the switcher's connection state."""

    entity_description = DESCRIPTION

    def __init__(self, coordinator: AtemCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_connection"
        self._attr_device_info = coordinator.device_info(entry.entry_id)

    @property
    def is_on(self) -> bool:
        """Return whether the switcher connection is active."""
        return bool(self.coordinator.data and self.coordinator.data["connected"])
