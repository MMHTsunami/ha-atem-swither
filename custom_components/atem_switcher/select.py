"""Select entities for the ATEM Switcher integration."""

from __future__ import annotations

from collections.abc import Callable

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AtemConnectionError, AtemCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up program, preview and aux select entities."""
    coordinator: AtemCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[AtemSourceSelect] = []

    for me in range(coordinator.me_count):
        suffix = "" if coordinator.me_count == 1 else f" {me + 1}"
        entities.append(
            AtemSourceSelect(
                coordinator,
                entry,
                f"program_{me}",
                f"Program{suffix}",
                lambda c, me=me: c.program.get(me),
                lambda c, src, me=me: c.set_program(me, src),
            )
        )
        entities.append(
            AtemSourceSelect(
                coordinator,
                entry,
                f"preview_{me}",
                f"Preview{suffix}",
                lambda c, me=me: c.preview.get(me),
                lambda c, src, me=me: c.set_preview(me, src),
            )
        )

    for aux in range(coordinator.aux_count):
        entities.append(
            AtemSourceSelect(
                coordinator,
                entry,
                f"aux_{aux}",
                f"Aux {aux + 1}",
                lambda c, aux=aux: c.aux.get(aux),
                lambda c, src, aux=aux: c.set_aux(aux, src),
            )
        )

    async_add_entities(entities)


class AtemSourceSelect(CoordinatorEntity[AtemCoordinator], SelectEntity):
    """Select a video source for a program, preview or aux output."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AtemCoordinator,
        entry: ConfigEntry,
        key: str,
        name: str,
        getter: Callable[[AtemCoordinator], int | None],
        setter: Callable[[AtemCoordinator, int], None],
    ) -> None:
        super().__init__(coordinator)
        self._getter = getter
        self._setter = setter
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = coordinator.device_info(entry.entry_id)

    def _labels(self) -> dict[int, str]:
        """Map source ids to unique display labels."""
        labels: dict[int, str] = {}
        seen: set[str] = set()
        for source, label in sorted(self.coordinator.inputs.items()):
            if label in seen:
                label = f"{label} ({source})"
            seen.add(label)
            labels[source] = label
        return labels

    @property
    def available(self) -> bool:
        """Return whether the switcher is connected."""
        return self.coordinator.connected

    @property
    def options(self) -> list[str]:
        """Return the available video sources."""
        return list(self._labels().values())

    @property
    def current_option(self) -> str | None:
        """Return the currently selected source."""
        source = self._getter(self.coordinator)
        return None if source is None else self._labels().get(source)

    async def async_select_option(self, option: str) -> None:
        """Route the chosen source."""
        for source, label in self._labels().items():
            if label == option:
                try:
                    self._setter(self.coordinator, source)
                except AtemConnectionError as err:
                    raise HomeAssistantError(str(err)) from err
                return
        raise HomeAssistantError(f"Unknown ATEM source: {option}")
