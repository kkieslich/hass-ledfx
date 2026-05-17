"""Switch component."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import ENTITY_ID_FORMAT, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_DEVICE,
    ATTR_FIELD_EFFECTS,
    ATTR_FIELD_TYPE,
    ATTR_LEDFX_DEVICE,
    ATTR_LEDFX_ENTITY_TYPE,
    ATTR_LEDFX_SUPPORTED_EFFECTS,
    ATTR_LIGHT_EFFECT,
    ATTR_LIGHT_EFFECT_CONFIG,
    ATTR_LIGHT_STATE,
    ATTR_SCENE_ACTIVE,
    ATTR_STATE,
    SIGNAL_NEW_SWITCH,
    SWITCH_ICONS,
)
from .entity import LedFxEntity
from .enum import ActionType
from .helper import generate_entity_id
from .updater import LedFxEntityDescription, LedFxUpdater, async_get_updater

PARALLEL_UPDATES = 0

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up LedFx number entry.

    :param hass: HomeAssistant: Home Assistant object
    :param config_entry: ConfigEntry: ConfigEntry object
    :param async_add_entities: AddEntitiesCallback: AddEntitiesCallback callback object
    """

    updater: LedFxUpdater = async_get_updater(hass, config_entry.entry_id)

    @callback
    def add_switch(entity: LedFxEntityDescription) -> None:
        """Add switch.

        :param entity: LedFxEntityDescription: Sensor object
        """

        # Different unique_id format for scene vs device switches
        if entity.type == ActionType.SCENE:
            unique_id = f"{config_entry.entry_id}-scene-{entity.description.key}"
        else:
            unique_id = f"{config_entry.entry_id}-{entity.device_code}-{entity.description.key}"

        async_add_entities([LedFxSwitch(unique_id, entity, updater)])

    for switch in updater.switches.values():
        add_switch(switch)

    updater.new_switch_callback = async_dispatcher_connect(
        hass, SIGNAL_NEW_SWITCH, add_switch
    )


# pylint: disable=too-many-ancestors
class LedFxSwitch(LedFxEntity, SwitchEntity):
    """LedFx switch entry."""

    _type: ActionType

    def __init__(
        self,
        unique_id: str,
        entity: LedFxEntityDescription,
        updater: LedFxUpdater,
    ) -> None:
        """Initialize switch.

        :param unique_id: str: Unique ID
        :param entity: LedFxEntityDescription object
        :param updater: LedFxUpdater: Luci updater object
        """

        LedFxEntity.__init__(
            self, unique_id, entity.description, updater, ENTITY_ID_FORMAT
        )

        self._type = entity.type
        self._attr_device_info = entity.device_info
        self._attr_available: bool = True
        self._attr_device_code = entity.device_code

        if self._type == ActionType.SCENE:
            # Scene switch initialization
            self.entity_id = generate_entity_id(
                ENTITY_ID_FORMAT,
                updater.ip,
                f"scene_{entity.description.key}",
            )

            self._attr_is_on = bool(
                updater.data.get(f"{entity.description.key}_{ATTR_SCENE_ACTIVE}", False)
            )

            self._attr_extra_state_attributes = {
                ATTR_LEDFX_ENTITY_TYPE: "scene",
            }
            self._attr_available = updater.data.get(ATTR_STATE, False)
        else:
            # Device effect property switch initialization
            self.entity_id = generate_entity_id(
                ENTITY_ID_FORMAT,
                updater.ip,
                f"{entity.device_code}_{entity.description.key}",
            )

            self._attr_is_on = bool(
                updater.data.get(
                    f"{entity.device_code}_{ATTR_LIGHT_EFFECT_CONFIG}", {}
                ).get(entity.description.key, False)
            )

            self._attr_extra_state_attributes = {
                ATTR_DEVICE: self._attr_device_code,
                ATTR_LEDFX_DEVICE: self._attr_device_code,
                ATTR_LEDFX_ENTITY_TYPE: "effect_control",
                ATTR_FIELD_EFFECTS: entity.extra.get(ATTR_FIELD_EFFECTS, [])
                if entity.extra
                else [],
            }
            self._attr_extra_state_attributes[ATTR_LEDFX_SUPPORTED_EFFECTS] = (
                self._attr_extra_state_attributes[ATTR_FIELD_EFFECTS]
            )

            if entity.extra:
                self._attr_field_type = entity.extra.get(ATTR_FIELD_TYPE)

            self._attr_available = bool(
                updater.data.get(ATTR_STATE, False)
                and updater.data.get(f"{self._attr_device_code}_{ATTR_LIGHT_STATE}")
                and updater.data.get(f"{self._attr_device_code}_{ATTR_LIGHT_EFFECT}")
                in self._attr_extra_state_attributes[ATTR_FIELD_EFFECTS]
            )

            if entity.description.key in SWITCH_ICONS:
                self._attr_icon = SWITCH_ICONS[entity.description.key]

    def _handle_coordinator_update(self) -> None:
        """Update state."""

        if self._type == ActionType.SCENE:
            # Scene switch state update
            is_on = bool(
                self._updater.data.get(
                    f"{self.entity_description.key}_{ATTR_SCENE_ACTIVE}", False
                )
            )
            is_available = self._updater.data.get(ATTR_STATE, False)
        else:
            # Device effect property switch state update
            is_on = bool(
                self._updater.data.get(
                    f"{self._attr_device_code}_{ATTR_LIGHT_EFFECT_CONFIG}", {}
                ).get(self.entity_description.key, False)
            )

            is_available = bool(
                self._updater.data.get(ATTR_STATE, False)
                and self._updater.data.get(f"{self._attr_device_code}_{ATTR_LIGHT_STATE}")
                and self._updater.data.get(f"{self._attr_device_code}_{ATTR_LIGHT_EFFECT}")
                in self._attr_extra_state_attributes.get(ATTR_FIELD_EFFECTS, [])
            )

        if self._attr_is_on == is_on and self._attr_available == is_available:
            return

        self._attr_available = is_available
        self._attr_is_on = is_on

        self.async_write_ha_state()

    async def _device_toggle(self, state: bool) -> None:
        """Device effect property toggle.

        :param state: bool: State
        """

        await self.async_update_effect(self.entity_description.key, state)

    async def _scene_toggle(self, state: bool) -> None:
        """Scene toggle.

        :param state: bool: State
        """

        if state:
            await self._updater.client.run_scene(self.entity_description.key)
        else:
            await self._updater.client.deactivate_scene(self.entity_description.key)

        # Update local data immediately for responsiveness
        self._updater.data[f"{self.entity_description.key}_{ATTR_SCENE_ACTIVE}"] = state

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Set turn on.

        :param **kwargs: Any
        """

        if action := getattr(self, f"_{self._type}_toggle", None):
            await action(True)

            self._attr_is_on = True

            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Set turn off.

        :param **kwargs: Any
        """

        if action := getattr(self, f"_{self._type}_toggle", None):
            await action(False)

            self._attr_is_on = False

            self.async_write_ha_state()
