"""Data coordinator for Eetlijst+."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import EetlijstApi, EetlijstAuthError, EetlijstError
from .const import (
    CONF_GROUP_ID,
    CONF_GROUP_NAME,
    DAYS_AHEAD,
    DOMAIN,
    EATING_STATUSES,
    LOGGER,
    STATUS_COOK,
    STATUS_NONE,
    UPDATE_INTERVAL,
)

type EetlijstConfigEntry = ConfigEntry[EetlijstCoordinator]


@dataclass
class Attendance:
    """One person's attendance for a day."""

    status: str
    guests: int = 0
    comment: str | None = None


@dataclass
class Day:
    """The dinner of one day."""

    day: date
    event_id: str
    name: str | None
    open: bool
    deadline: datetime | None
    attendance: dict[str, Attendance] = field(default_factory=dict)

    def status_of(self, user_id: str) -> str:
        """Status of a user (no_status if they have none)."""
        att = self.attendance.get(user_id)
        if att is None or att.status in (None, "", "unspecified"):
            return STATUS_NONE
        return att.status

    def eaters(self) -> list[str]:
        """User ids that eat along."""
        return [uid for uid, a in self.attendance.items() if a.status in EATING_STATUSES]

    def cooks(self) -> list[str]:
        """User ids that cook."""
        return [uid for uid, a in self.attendance.items() if a.status == STATUS_COOK]

    def total_eating(self) -> int:
        """Number of people eating, guests included."""
        return sum(1 + (a.guests or 0) for a in self.attendance.values() if a.status in EATING_STATUSES)


@dataclass
class EetlijstData:
    """Everything the entities need."""

    group_name: str
    members: dict[str, str]  # user_id -> name (house order)
    days: dict[date, Day]
    shopping: list[dict]


def _local_midnight(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=dt_util.get_default_time_zone())


class EetlijstCoordinator(DataUpdateCoordinator[EetlijstData]):
    """Polls Eetlijst and performs changes."""

    config_entry: EetlijstConfigEntry

    def __init__(self, hass: HomeAssistant, entry: EetlijstConfigEntry) -> None:
        """Init."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.api = EetlijstApi(async_get_clientsession(hass), entry.data[CONF_TOKEN])
        self.group_id: str = entry.data[CONF_GROUP_ID]
        self.user_id: str = self.api.user_id or ""
        self._populated: set[date] = set()

    # ------------------------------------------------------------------
    async def _async_update_data(self) -> EetlijstData:
        try:
            return await self._fetch()
        except EetlijstAuthError as err:
            raise ConfigEntryAuthFailed(
                "Eetlijst-token is ongeldig of verlopen"
            ) from err
        except EetlijstError as err:
            raise UpdateFailed(f"Fout bij ophalen Eetlijst: {err}") from err

    async def _populate(self, day: date) -> None:
        """Ask Eetlijst to create the dinner for a day (as the app does)."""
        now = dt_util.now()
        when = now if day == now.date() else datetime.combine(day, time(12), tzinfo=now.tzinfo)
        try:
            await self.api.populate_dinners(self.group_id, when)
            self._populated.add(day)
        except EetlijstAuthError:
            raise
        except EetlijstError as err:
            LOGGER.debug("Kon maaltijd voor %s niet aanmaken: %s", day, err)

    async def _fetch(self) -> EetlijstData:
        today = dt_util.now().date()
        if today not in self._populated:
            await self._populate(today)

        group = await self.api.get_group(self.group_id)
        if group is None:
            raise EetlijstError("Eetlijst-groep niet gevonden")
        members = {
            m["user"]["id"]: m["user"]["name"]
            for m in group.get("users_in_groups") or []
            if m.get("user")
        }

        events = await self.api.get_events(
            self.group_id,
            _local_midnight(today),
            _local_midnight(today + timedelta(days=DAYS_AHEAD)),
        )
        days: dict[date, Day] = {}
        for event in events:
            start = dt_util.parse_datetime(event["start_date"])
            if start is None:
                continue
            day = dt_util.as_local(start).date()
            if day in days:  # keep the first event of a day (the dinner)
                continue
            deadline = (
                dt_util.parse_datetime(event["signup_deadline"])
                if event.get("signup_deadline")
                else None
            )
            attendance: dict[str, Attendance] = {}
            for row in event.get("event_attendees") or []:
                user = (row.get("user_in_group") or {}).get("user") or {}
                if not user.get("id"):
                    continue
                attendance[user["id"]] = Attendance(
                    status=row.get("status"),
                    guests=row.get("number_guests") or 0,
                    comment=row.get("comment"),
                )
                members.setdefault(user["id"], user.get("name") or user["id"])
            days[day] = Day(
                day=day,
                event_id=event["id"],
                name=event.get("name"),
                open=bool(event.get("open", True)),
                deadline=deadline,
                attendance=attendance,
            )

        shopping = await self.api.get_list(self.group_id)
        return EetlijstData(
            group_name=group.get("name") or self.config_entry.data.get(CONF_GROUP_NAME, ""),
            members=members,
            days=days,
            shopping=shopping,
        )

    # ---- helpers for entities -----------------------------------------
    @property
    def today(self) -> date:
        """Local date."""
        return dt_util.now().date()

    def day(self, offset: int = 0) -> Day | None:
        """Dinner `offset` days from today."""
        if self.data is None:
            return None
        return self.data.days.get(self.today + timedelta(days=offset))

    async def _call(self, coro):
        """Run an API call, turning errors into HA errors."""
        try:
            return await coro
        except EetlijstAuthError as err:
            self.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError(
                "Eetlijst-token is verlopen, vul een nieuwe in bij de integratie"
            ) from err
        except EetlijstError as err:
            raise HomeAssistantError(f"Eetlijst: {err}") from err

    async def _event_id_for(self, day: date) -> str:
        if self.data and (d := self.data.days.get(day)):
            return d.event_id
        await self._call(self._populate(day))
        events = await self._call(
            self.api.get_events(
                self.group_id, _local_midnight(day), _local_midnight(day + timedelta(days=1))
            )
        )
        if not events:
            raise HomeAssistantError(f"Geen maaltijd gevonden op {day.isoformat()}")
        return events[0]["id"]

    async def async_set_attendance(
        self,
        day: date,
        *,
        status: str | None = None,
        guests: int | None = None,
        comment: str | None = None,
        clear_comment: bool = False,
    ) -> None:
        """Change my attendance for a day."""
        if not self.user_id:
            raise HomeAssistantError("Gebruikers-id ontbreekt in de token")
        event_id = await self._event_id_for(day)
        await self._call(
            self.api.set_attendance(
                event_id,
                self.user_id,
                status=status,
                guests=guests,
                comment=comment,
                clear_comment=clear_comment,
            )
        )
        await self.async_refresh()

    async def async_add_item(self, text: str) -> None:
        """Add a shopping list item."""
        await self._call(self.api.add_list_item(self.group_id, text))
        await self.async_refresh()

    async def async_update_item(self, item_id: str, changes: dict) -> None:
        """Change a shopping list item."""
        await self._call(self.api.update_list_item(item_id, changes))

    def name_of(self, user_id: str) -> str:
        """Name of a member."""
        if self.data and user_id in self.data.members:
            return self.data.members[user_id]
        return user_id
