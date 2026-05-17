"""LedFx custom integration."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import (
    DEFAULT_CALL_DELAY,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SLEEP,
    DEFAULT_TIMEOUT,
    DOMAIN,
    NAME,
    OPTION_IS_FROM_FLOW,
    PLATFORMS,
    UPDATE_LISTENER,
    UPDATER,
)
from .helper import build_auth, get_config_value
from .updater import LedFxUpdater

_LOGGER = logging.getLogger(__name__)

PANEL_URL_PATH = "ledfx"
PANEL_WEB_COMPONENT = "ledfx-panel"
PANEL_STATIC_PATH = "/ledfx_static"
PANEL_REGISTERED = "panel_registered"
PANEL_STATIC_REGISTERED = "panel_static_registered"
EFFECT_CONTROL_DOMAINS = {"number", "select", "switch"}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up entry configured via user interface.

    :param hass: HomeAssistant: Home Assistant object
    :param entry: ConfigEntry: Config Entry object
    :return bool: Is success
    """

    is_new: bool = get_config_value(entry, OPTION_IS_FROM_FLOW, False)

    if is_new:
        hass.config_entries.async_update_entry(entry, data=entry.data, options={})

    _updater: LedFxUpdater = LedFxUpdater(
        hass,
        get_config_value(entry, CONF_IP_ADDRESS),
        get_config_value(entry, CONF_PORT),
        build_auth(
            get_config_value(entry, CONF_USERNAME),
            get_config_value(entry, CONF_PASSWORD),
        ),
        get_config_value(entry, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        get_config_value(entry, CONF_TIMEOUT, DEFAULT_TIMEOUT),
    )

    hass.data.setdefault(DOMAIN, {})

    await _async_register_panel(hass)

    hass.data[DOMAIN][entry.entry_id] = {UPDATER: _updater}

    hass.data[DOMAIN][entry.entry_id][UPDATE_LISTENER] = entry.add_update_listener(
        async_update_options
    )

    async def async_start(with_sleep: bool = False) -> None:
        """Async start.

        :param with_sleep: bool
        """

        await _updater.async_config_entry_first_refresh()
        _async_enable_effect_controls(hass, entry)

        if with_sleep:
            await asyncio.sleep(DEFAULT_SLEEP)

        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    if is_new:
        await async_start()
        await asyncio.sleep(DEFAULT_SLEEP)
    else:
        hass.loop.call_later(
            DEFAULT_CALL_DELAY,
            lambda: hass.async_create_task(async_start(True)),
        )

    async def async_stop(event: Event) -> None:
        """Async stop"""

        await _updater.async_stop()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_stop)

    return True


async def _async_register_panel(hass: HomeAssistant) -> None:
    """Register the LedFx sidebar panel."""

    if not hass.data[DOMAIN].get(PANEL_STATIC_REGISTERED):
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(
                    PANEL_STATIC_PATH,
                    str(Path(__file__).parent / "frontend"),
                    True,
                )
            ]
        )
        hass.data[DOMAIN][PANEL_STATIC_REGISTERED] = True

    try:
        await panel_custom.async_register_panel(
            hass=hass,
            frontend_url_path=PANEL_URL_PATH,
            webcomponent_name=PANEL_WEB_COMPONENT,
            sidebar_title=NAME,
            sidebar_icon="mdi:led-strip-variant",
            module_url=f"{PANEL_STATIC_PATH}/ledfx-panel.js",
            require_admin=False,
            config={"domain": DOMAIN},
        )
    except ValueError as err:
        if "Overwriting panel" not in str(err):
            raise

    hass.data[DOMAIN][PANEL_REGISTERED] = True


def _async_enable_effect_controls(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Enable LedFx effect controls that older versions created disabled."""

    registry = er.async_get(hass)

    for entity_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        if (
            entity_entry.platform == DOMAIN
            and entity_entry.domain in EFFECT_CONTROL_DOMAINS
            and entity_entry.disabled_by == er.RegistryEntryDisabler.INTEGRATION
        ):
            registry.async_update_entity(entity_entry.entity_id, disabled_by=None)


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options for entry that was configured via user interface.

    :param hass: HomeAssistant: Home Assistant object
    :param entry: ConfigEntry: Config Entry object
    """

    if entry.entry_id not in hass.data[DOMAIN]:
        return

    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Remove entry configured via user interface.

    :param hass: HomeAssistant: Home Assistant object
    :param entry: ConfigEntry: Config Entry object
    :return bool: Is success
    """

    if is_unload := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        _updater: LedFxUpdater = hass.data[DOMAIN][entry.entry_id][UPDATER]
        await _updater.async_stop()

        _update_listener: CALLBACK_TYPE = hass.data[DOMAIN][entry.entry_id][
            UPDATE_LISTENER
        ]
        _update_listener()

        hass.data[DOMAIN].pop(entry.entry_id)

        if not any(
            isinstance(value, dict) and UPDATER in value
            for value in hass.data[DOMAIN].values()
        ):
            if hasattr(frontend, "async_remove_panel"):
                frontend.async_remove_panel(
                    hass, PANEL_URL_PATH, warn_if_unknown=False
                )
            hass.data[DOMAIN].pop(PANEL_REGISTERED, None)

    return is_unload
