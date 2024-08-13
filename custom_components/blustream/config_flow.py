"""Config flow for Blustream Matrix integration."""

from __future__ import annotations

from asyncio import timeout
import logging
from typing import Any

from pyblustream.matrix import Matrix
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import CONF_POWER_ON_APP_SOURCE_CHANGE, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default="Matrix"): str,
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=23): int,
        vol.Required(CONF_POWER_ON_APP_SOURCE_CHANGE, default=False): bool
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    matrix = Matrix(hostname=data[CONF_HOST], port=data[CONF_PORT])

    try:
        async with timeout(5.0):
            await matrix.async_connect()
    except (ConnectionRefusedError, TimeoutError, ConnectionResetError) as exp:
        _LOGGER.exception("Error connecting to Matrix")
        matrix.close()
        raise CannotConnect from exp

    # Return info that you want to store in the config entry.
    return {"title": data[CONF_NAME]}


class ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Blustream Matrix."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
