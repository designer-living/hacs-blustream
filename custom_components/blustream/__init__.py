"""The Blustream Matrix integration."""

from __future__ import annotations

from asyncio import sleep, timeout
import logging

from pyblustream.listener import LoggingListener, TurningOnListener
from pyblustream.matrix import Matrix

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, Platform
from homeassistant.core import HomeAssistant

from .const import CONF_POWER_ON_APP_SOURCE_CHANGE, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER]

# TODO Create ConfigEntry type alias with API object
# TODO Rename type alias and update all entry annotations
# type New_NameConfigEntry = ConfigEntry[MyApi]  # noqa: F821


# TODO Update entry annotation
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Blustream Matrix from a config entry."""
    hostname = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    # turn_on_listener = False
    turn_on_listener = entry.data[CONF_POWER_ON_APP_SOURCE_CHANGE]

    matrix = Matrix(hostname, port)
    try:
        matrix.register_listener(LoggingListener())
        if turn_on_listener:
            _LOGGER.info("Registering listener to turn on matrix when app source is changed")
            matrix.register_listener(TurningOnListener(matrix))
        async with timeout(5.0):
            await matrix.async_connect()
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = matrix

        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    except (ConnectionRefusedError, TimeoutError, ConnectionResetError):
        _LOGGER.exception("Error connecting to Matrix")
    else:
        return True
    return False


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    matrix: Matrix = hass.data[DOMAIN][entry.entry_id]
    matrix.close()

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
