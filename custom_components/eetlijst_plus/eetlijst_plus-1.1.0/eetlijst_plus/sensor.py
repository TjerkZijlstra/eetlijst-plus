"""Sensors: today's dinner, every housemate's status, token expiry."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import ALL_STATES, DAYS_AHEAD, STATUS_NONE
from .coordinator import Day, EetlijstConfigEntry, EetlijstCoordinator
from .entity import EetlijstEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EetlijstConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            EatersTodaySensor(coordinator, "eaters_today"),
            CookTodaySensor(coordinator, "cook_today"),
            TokenExpirySensor(coordinator, "token_expires"),
        ]
    )

    known: set[str] = set()

    @callback
    def _add_members() -> None:
        new = [uid for uid in coordinator.data.members if uid not in known]
        if not new:
            return
        known.update(new)
        async_add_entities(MemberStatusSensor(coordinator, uid) for uid in new)

    _add_members()
    entry.async_on_unload(coordinator.async_add_listener(_add_members))


def _summary(c: EetlijstCoordinator, day: Day) -> dict[str, Any]:
    groups: dict[str, list[str]] = {s: [] for s in ALL_STATES}
    for uid in c.data.members:
        groups[day.status_of(uid) if day.status_of(uid) in groups else STATUS_NONE].append(
            c.name_of(uid)
        )
    guests = {
        c.name_of(uid): a.guests for uid, a in day.attendance.items() if a.guests
    }
    comments = {
        c.name_of(uid): a.comment for uid, a in day.attendance.items() if a.comment
    }
    return {
        "date": day.day.isoformat(),
        "open": day.open,
        "deadline": day.deadline.isoformat() if day.deadline else None,
        "cooking": groups["cook"],
        "eating": groups["eat_only"],
        "groceries": groups["got_groceries"],
        "not_eating": groups["not_attending"],
        "dont_know_yet": groups["dont_know_yet"],
        "no_status": groups[STATUS_NONE],
        "guests": guests,
        "comments": comments,
    }


class EatersTodaySensor(EetlijstEntity, SensorEntity):
    """How many people eat today (guests included)."""

    _attr_translation_key = "eaters_today"
    _attr_icon = "mdi:silverware-fork-knife"
    _attr_native_unit_of_measurement = "personen"

    @property
    def native_value(self) -> int | None:
        """Count."""
        day = self.coordinator.day(0)
        return None if day is None else day.total_eating()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Who's what."""
        day = self.coordinator.day(0)
        return {} if day is None else _summary(self.coordinator, day)


class CookTodaySensor(EetlijstEntity, SensorEntity):
    """Who cooks today."""

    _attr_translation_key = "cook_today"
    _attr_icon = "mdi:chef-hat"

    @property
    def native_value(self) -> str | None:
        """Cook name(s)."""
        day = self.coordinator.day(0)
        if day is None:
            return None
        cooks = [self.coordinator.name_of(uid) for uid in day.cooks()]
        return ", ".join(cooks) if cooks else "Niemand"


class TokenExpirySensor(EetlijstEntity, SensorEntity):
    """When the API key stops working."""

    _attr_translation_key = "token_expires"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> datetime | None:
        """Expiry."""
        return self.coordinator.api.expires


class MemberStatusSensor(EetlijstEntity, SensorEntity):
    """Status of one housemate today, with the coming week as attributes."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ALL_STATES
    _attr_translation_key = "member_status"

    def __init__(self, coordinator: EetlijstCoordinator, user_id: str) -> None:
        """Init."""
        super().__init__(coordinator, f"member_{user_id}")
        self._uid = user_id
        self._attr_translation_placeholders = {"name": coordinator.name_of(user_id)}

    @property
    def available(self) -> bool:
        """Only while still in the group."""
        return super().available and self._uid in self.coordinator.data.members

    @property
    def native_value(self) -> str | None:
        """Today's status."""
        day = self.coordinator.day(0)
        return None if day is None else day.status_of(self._uid)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Week overview."""
        week: dict[str, str] = {}
        week_guests: dict[str, int] = {}
        week_open: dict[str, bool] = {}
        today = self.coordinator.today
        for offset in range(DAYS_AHEAD):
            d = today + timedelta(days=offset)
            day = self.coordinator.data.days.get(d)
            if day is not None:
                key = d.isoformat()
                week[key] = day.status_of(self._uid)
                a = day.attendance.get(self._uid)
                week_guests[key] = a.guests if a else 0
                week_open[key] = day.open
        day = self.coordinator.day(0)
        att = day.attendance.get(self._uid) if day else None
        members = list(self.coordinator.data.members)
        return {
            "name": self.coordinator.name_of(self._uid),
            "is_me": self._uid == self.coordinator.user_id,
            "order": members.index(self._uid) if self._uid in members else 99,
            "guests": att.guests if att else 0,
            "comment": att.comment if att else None,
            "week": week,
            "week_guests": week_guests,
            "week_open": week_open,
        }
