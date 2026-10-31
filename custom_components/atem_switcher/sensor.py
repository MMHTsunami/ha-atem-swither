"""Sensors for the ATEM Switcher integration."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN, MANUFACTURER
from .coordinator import AtemCoordinator

DESCRIPTION = SensorEntityDescription(
    key="distinct_field_types",
    name="Distinct Field Types",
    icon="mdi:counter",
    entity_category=EntityCategory.DIAGNOSTIC,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ATEM diagnostic sensors."""
    coordinator: AtemCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([AtemFieldCountSensor(coordinator, entry)])


class AtemFieldCountSensor(
    CoordinatorEntity[DataUpdateCoordinator[dict]], SensorEntity
):
    """Count the distinct ATEM fields received so far."""

    entity_description = DESCRIPTION

    def __init__(self, coordinator: AtemCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_distinct_field_types"
        self._attr_device_info = coordinator.device_info(entry.entry_id)

    @property
    def native_value(self) -> int:
        """Return the number of distinct fields received."""
        return len(self.coordinator.data["fields"]) if self.coordinator.data else 0
