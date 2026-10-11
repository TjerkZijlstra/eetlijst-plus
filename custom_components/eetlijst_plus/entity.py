"""Base entity."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EetlijstCoordinator


class EetlijstEntity(CoordinatorEntity[EetlijstCoordinator]):
    """Common bits."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: EetlijstCoordinator, key: str) -> None:
        """Init."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.group_id}_{coordinator.user_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{coordinator.group_id}_{coordinator.user_id}")},
            name=f"Eetlijst {coordinator.data.group_name}",
            manufacturer="Eetlijst",
            model=coordinator.api.user_name or "Eetlijst",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://v5.eetlijst.nl",
        )
