"""My status for today/tomorrow as a dropdown you can change."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import SETTABLE_STATUSES, STATUS_NONE
from .coordinator import EetlijstConfigEntry, EetlijstCoordinator
from .entity import EetlijstEntity

PARALLEL_UPDATES = 1

DAYS = {0: "my_status_today", 1: "my_status_tomorrow"}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EetlijstConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up."""
    coordinator = entry.runtime_data
    async_add_entities(MyStatusSelect(coordinator, offset, key) for offset, key in DAYS.items())


class MyStatusSelect(EetlijstEntity, SelectEntity):
    """Dropdown with my status for a day."""

    _attr_options = SETTABLE_STATUSES

    def __init__(self, coordinator: EetlijstCoordinator, offset: int, key: str) -> None:
        """Init."""
        super().__init__(coordinator, key)
        self._offset = offset
        self._attr_translation_key = key

    @property
    def current_option(self) -> str | None:
        """Current status."""
        day = self.coordinator.day(self._offset)
        if day is None:
            return None
        status = day.status_of(self.coordinator.user_id)
        return None if status == STATUS_NONE else status

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Extra info."""
        day = self.coordinator.day(self._offset)
        if day is None:
            return {"date": None}
        me = day.attendance.get(self.coordinator.user_id)
        return {
            "date": day.day.isoformat(),
            "open": day.open,
            "deadline": day.deadline.isoformat() if day.deadline else None,
            "guests": me.guests if me else 0,
            "comment": me.comment if me else None,
        }

    async def async_select_option(self, option: str) -> None:
        """Change my status."""
        day = self.coordinator.today + timedelta(days=self._offset)
        await self.coordinator.async_set_attendance(day, status=option)
