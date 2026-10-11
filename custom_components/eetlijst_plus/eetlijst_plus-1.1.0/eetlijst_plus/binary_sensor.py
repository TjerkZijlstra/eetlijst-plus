"""Am I signed up today / is the list still open."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import EATING_STATUSES
from .coordinator import EetlijstConfigEntry, EetlijstCoordinator
from .entity import EetlijstEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class EetlijstBinaryDescription(BinarySensorEntityDescription):
    """Description with value function."""

    value_fn: Callable[[EetlijstCoordinator], bool | None]


def _signed_up(c: EetlijstCoordinator) -> bool | None:
    day = c.day(0)
    return None if day is None else day.status_of(c.user_id) in EATING_STATUSES


def _signed_up_tomorrow(c: EetlijstCoordinator) -> bool | None:
    day = c.day(1)
    return None if day is None else day.status_of(c.user_id) in EATING_STATUSES


def _open(c: EetlijstCoordinator) -> bool | None:
    day = c.day(0)
    return None if day is None else day.open


DESCRIPTIONS = (
    EetlijstBinaryDescription(
        key="signed_up_today", translation_key="signed_up_today", value_fn=_signed_up
    ),
    EetlijstBinaryDescription(
        key="signed_up_tomorrow",
        translation_key="signed_up_tomorrow",
        value_fn=_signed_up_tomorrow,
    ),
    EetlijstBinaryDescription(key="list_open", translation_key="list_open", value_fn=_open),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EetlijstConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up."""
    async_add_entities(EetlijstBinarySensor(entry.runtime_data, d) for d in DESCRIPTIONS)


class EetlijstBinarySensor(EetlijstEntity, BinarySensorEntity):
    """Binary sensor."""

    entity_description: EetlijstBinaryDescription

    def __init__(self, coordinator: EetlijstCoordinator, description: EetlijstBinaryDescription) -> None:
        """Init."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        """State."""
        return self.entity_description.value_fn(self.coordinator)
