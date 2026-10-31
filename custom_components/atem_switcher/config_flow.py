"""Config flow for the ATEM Switcher integration."""

from __future__ import annotations

import ipaddress
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.helpers import selector

from .const import DOMAIN
from .coordinator import AtemConnectionError, AtemClient


async def _async_validate_connection(host: str) -> None:
    """Validate the ATEM handshake before creating a config entry."""
    client = AtemClient(host, lambda _fields: None, lambda: None)
    try:
        await client.async_connect()
    finally:
        client.async_close()


class AtemConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ATEM switchers."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> config_entries.FlowResult:
        """Accept a switcher IP address and validate its connection."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            try:
                host = str(ipaddress.ip_address(host))
            except ValueError:
                errors["base"] = "invalid_host"
            else:
                await self.async_set_unique_id(host)
                self._abort_if_unique_id_configured()
                try:
                    await _async_validate_connection(host)
                except AtemConnectionError:
                    errors["base"] = "cannot_connect"
                else:
                    return self.async_create_entry(
                        title=f"ATEM Switcher ({host})",
                        data={CONF_HOST: host},
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): selector.TextSelector(
                        selector.TextSelectorConfig()
                    )
                }
            ),
            errors=errors,
        )
