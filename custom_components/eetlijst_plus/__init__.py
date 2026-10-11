"""Eetlijst+ — see and change your Eetlijst status from Home Assistant."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_COMMENT,
    ATTR_CONFIG_ENTRY,
    ATTR_DATE,
    ATTR_GUESTS,
    ATTR_STATUS,
    DOMAIN,
    SERVICE_SET_STATUS,
    SETTABLE_STATUSES,
)
from .coordinator import EetlijstConfigEntry, EetlijstCoordinator

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.TODO,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

SET_STATUS_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_CONFIG_ENTRY): cv.string,
        vol.Optional(ATTR_DATE): cv.date,
        vol.Optional(ATTR_STATUS): vol.In(SETTABLE_STATUSES),
        vol.Optional(ATTR_GUESTS): vol.All(vol.Coerce(int), vol.Range(min=0, max=20)),
        vol.Optional(ATTR_COMMENT): cv.string,
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the set_status action."""

    async def _set_status(call: ServiceCall) -> None:
        entries: list[EetlijstConfigEntry] = [
            e
            for e in hass.config_entries.async_entries(DOMAIN)
            if e.state is ConfigEntryState.LOADED
        ]
        if entry_id := call.data.get(ATTR_CONFIG_ENTRY):
            entries = [e for e in entries if e.entry_id == entry_id]
        if not entries:
            raise ServiceValidationError("Geen geladen Eetlijst gevonden")
        if len(entries) > 1:
            raise ServiceValidationError("Meerdere Eetlijsten: kies er één")
        if not any(k in call.data for k in (ATTR_STATUS, ATTR_GUESTS, ATTR_COMMENT)):
            raise ServiceValidationError("Geef een status, gasten of opmerking op")

        day = call.data.get(ATTR_DATE) or dt_util.now().date()
        comment = call.data.get(ATTR_COMMENT)
        await entries[0].runtime_data.async_set_attendance(
            day,
            status=call.data.get(ATTR_STATUS),
            guests=call.data.get(ATTR_GUESTS),
            comment=comment,
            clear_comment=comment == "",
        )

    hass.services.async_register(DOMAIN, SERVICE_SET_STATUS, _set_status, SET_STATUS_SCHEMA)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: EetlijstConfigEntry) -> bool:
    """Set up from a config entry."""
    coordinator = EetlijstCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: EetlijstConfigEntry) -> bool:
    """Unload."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
