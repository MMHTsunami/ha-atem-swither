"""Select entities for the ATEM Switcher integration."""

from __future__ import annotations

from collections.abc import Callable

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    AUX_OUTPUT_SOURCE_ID_BASE,
    DOMAIN,
    ME_OUTPUT_SOURCE_ID_BASE,
    PREVIEW_OUTPUT_SOURCE_IDS,
    PROGRAM_OUTPUT_SOURCE_IDS,
)
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
                (
                    *PROGRAM_OUTPUT_SOURCE_IDS,
                    ME_OUTPUT_SOURCE_ID_BASE,
                )
                if me == 0
                else (ME_OUTPUT_SOURCE_ID_BASE + 10 * me,),
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
                (
                    *PREVIEW_OUTPUT_SOURCE_IDS,
                    ME_OUTPUT_SOURCE_ID_BASE + 1,
                )
                if me == 0
                else (ME_OUTPUT_SOURCE_ID_BASE + 10 * me + 1,),
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
                (AUX_OUTPUT_SOURCE_ID_BASE + aux,),
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
        output_source_ids: tuple[int, ...],
    ) -> None:
        super().__init__(coordinator)
        self._getter = getter
        self._setter = setter
        self._output_source_ids = output_source_ids
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = coordinator.device_info(entry.entry_id)

    @property
    def name(self) -> str:
        """Return the ATEM long name for this output when available."""
        for source in self._output_source_ids:
            output_name = self.coordinator.output_names.get(source)
            if output_name:
                return output_name
        return self._attr_name

    def _source_names(self) -> dict[int, str]:
        """Map source ids to unique ATEM long names."""
        source_names: dict[int, str] = {}
        seen: set[str] = set()
        for source, source_name in sorted(self.coordinator.input_names.items()):
            if source_name in seen:
                source_name = f"{source_name} ({source})"
            seen.add(source_name)
            source_names[source] = source_name
        return source_names

    @property
    def available(self) -> bool:
        """Return whether the switcher is connected."""
        return self.coordinator.connected

    @property
    def options(self) -> list[str]:
        """Return the available video sources."""
        return list(self._source_names().values())

    @property
    def current_option(self) -> str | None:
        """Return the currently selected source."""
        source = self._getter(self.coordinator)
        return None if source is None else self._source_names().get(source)

    async def async_select_option(self, option: str) -> None:
        """Route the chosen source."""
        for source, source_name in self._source_names().items():
            if source_name == option:
                try:
                    self._setter(self.coordinator, source)
                except AtemConnectionError as err:
                    raise HomeAssistantError(str(err)) from err
                return
        raise HomeAssistantError(f"Unknown ATEM source: {option}")
