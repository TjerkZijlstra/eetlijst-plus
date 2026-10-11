"""Number of guests I bring today."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import EetlijstConfigEntry
from .entity import EetlijstEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EetlijstConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up."""
    async_add_entities([MyGuestsNumber(entry.runtime_data, "my_guests_today")])


class MyGuestsNumber(EetlijstEntity, NumberEntity):
    """Guests I bring to today's dinner."""

    _attr_translation_key = "my_guests_today"
    _attr_native_min_value = 0
    _attr_native_max_value = 10
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:account-multiple-plus"

    @property
    def native_value(self) -> float | None:
        """Current guests."""
        day = self.coordinator.day(0)
        if day is None:
            return None
        me = day.attendance.get(self.coordinator.user_id)
        return me.guests if me else 0

    async def async_set_native_value(self, value: float) -> None:
        """Set guests."""
        await self.coordinator.async_set_attendance(self.coordinator.today, guests=int(value))
