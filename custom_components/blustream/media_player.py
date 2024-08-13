"""Platform for media_player integration."""

from __future__ import annotations

import logging

from pyblustream.listener import SourceChangeListener
from pyblustream.matrix import Matrix

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo, format_mac
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add media_player for passed config_entry in HA."""
    # The hub is loaded from the associated hass.data entry that was created in the
    # __init__.async_setup_entry function
    matrix: Matrix = hass.data[DOMAIN][config_entry.entry_id]

    name = config_entry.data[CONF_NAME]

    _LOGGER.debug("Setting up matrix entities for %s", name)

    my_listener = MyListener()
    matrix.register_listener(my_listener)
    outputs = []

    # Setup the main matrix entity
    _LOGGER.debug("Setting up matrix entity")
    matrix_entity = MatrixEntity(name, matrix)
    my_listener.add_matrix_entity(matrix_entity)
    outputs.append(matrix_entity)

    # Setup the individual output entites
    for output_id, output_name in matrix.outputs_by_id.items():
        _LOGGER.debug("Setting up output entity for output_id: %s, %s", output_id, output_name)
        matrix_output = MatrixOutput(output_id, output_name, matrix)
        my_listener.add_matrix_output_entity(output_id, matrix_output)
        outputs.append(matrix_output)

    # Request a status update so all listeners are notified with current status
    _LOGGER.info("Refreshing status after setup")
    matrix.update_status()
    async_add_entities(outputs)


class MyListener(SourceChangeListener):
    """Listener to direct messages to correct entities."""

    def __init__(self) -> None:
        """Init."""
        self.matrix_output_entities: dict[int, MatrixOutput] = {}
        self.matrix_entities: list[MatrixEntity] = []

    def add_matrix_output_entity(self, output_id, entity):
        """Add a Matrix Output Entity."""
        self.matrix_output_entities[output_id] = entity

    def add_matrix_entity(self, entity):
        """Add a Matrix Entity."""
        self.matrix_entities.append(entity)

    def source_changed(self, output_id: int, input_id: int):
        """Source changed callback."""
        _LOGGER.debug(
            "Source changed Output ID %s changed to input ID: %s", output_id, input_id
        )
        entity = self.matrix_output_entities.get(output_id)
        if entity:
            _LOGGER.debug("Updating entity for source changed")
            entity.set_source(input_id)

    def connected(self):
        """Matrix connected callback. No action as status will be updated."""

    def disconnected(self):
        """Matrix disconnected callback."""
        _LOGGER.warning("Matrix disconnected")
        for entity in self.matrix_entities:
            _LOGGER.debug("Updating %s", entity)
            entity.set_state(None)
        for entity in self.matrix_output_entities.values():
            _LOGGER.debug("Updating %s", entity)
            entity.set_state(None)

    def power_changed(self, power):
        """Power changed callback."""
        if power == "ON":
            state = MediaPlayerState.ON
        elif power == "OFF":
            state = MediaPlayerState.OFF
        else:
            state = None
        _LOGGER.info("Power changed to: %s, state: %s", power, state)

        for entity in self.matrix_entities:
            _LOGGER.debug("Updating %s", entity)
            entity.set_state(state)
        for entity in self.matrix_output_entities.values():
            _LOGGER.debug("Updating %s", entity)
            entity.set_state(state)

    def error(self, error_message: str):
        """Error callback not required for us."""

    def source_change_requested(self, output_id: int, input_id: int):
        """Ignore callback from API - not required for us."""


class MatrixEntity(MediaPlayerEntity):
    """Represents the Matrix itself."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_name = None
    _attr_supported_features = (
        MediaPlayerEntityFeature.TURN_ON | MediaPlayerEntityFeature.TURN_OFF
    )
    _attr_device_class = MediaPlayerDeviceClass.RECEIVER

    def __init__(self, name, matrix) -> None:
        """Init."""
        self._matrix = matrix

        mac = format_mac(self._matrix.mac)
        self._attr_unique_id = mac
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mac)},
            manufacturer="Blustream",
            configuration_url=f"http://{self._matrix.hostname}",
            model=self._matrix.device_name,
            sw_version=self._matrix.firmware_version,
        )

    def set_state(self, state):
        """Set the power."""
        self._attr_state = state
        self.schedule_update_ha_state()

    def turn_on(self) -> None:
        """Turn the media player on."""
        self._matrix.turn_on()

    def turn_off(self) -> None:
        """Turn the media player off."""
        self._matrix.turn_off()


class MatrixOutput(MediaPlayerEntity):
    """Represents the Outputs of the Matrix."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_name = None

    _attr_supported_features = MediaPlayerEntityFeature.SELECT_SOURCE
    _attr_device_class = MediaPlayerDeviceClass.RECEIVER

    def __init__(self, output_id, output_name, matrix) -> None:
        """Init."""
        self.output_id = output_id
        self._matrix: Matrix = matrix
        self._attr_source_list = list(matrix.input_names)

        mac = format_mac(self._matrix.mac)
        self._attr_unique_id = f"{mac}-output{output_id}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            name=output_name,
            manufacturer="Blustream",
            configuration_url=f"http://{self._matrix.hostname}",
            model=self._matrix.device_name,
            sw_version=self._matrix.firmware_version,
            via_device=(DOMAIN, mac),
        )

    def set_state(self, state):
        """Set the power."""
        self._attr_state = state
        self.schedule_update_ha_state()

    def set_source(self, input_id):
        """Set the state."""
        self._attr_source = self._matrix.inputs_by_id[input_id]
        self.schedule_update_ha_state()

    def select_source(self, source: str) -> None:
        """Select the source."""
        input_id = self._matrix.inputs_by_name.get(source)
        if input_id:
            self._matrix.change_source(
                output_id=self.output_id, input_id=input_id
            )
        else:
            _LOGGER.error("Invalid input source: %s, valid sources %s", source, self._attr_source_list)
