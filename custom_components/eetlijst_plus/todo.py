"""The house shopping list as a Home Assistant to-do list."""

from __future__ import annotations

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
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
    async_add_entities([ShoppingList(entry.runtime_data, "shopping_list")])


class ShoppingList(EetlijstEntity, TodoListEntity):
    """Boodschappenlijst."""

    _attr_translation_key = "shopping_list"
    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
    )

    @property
    def todo_items(self) -> list[TodoItem] | None:
        """Items."""
        return [
            TodoItem(
                uid=item["id"],
                summary=item.get("text") or "",
                status=TodoItemStatus.COMPLETED if item.get("checked") else TodoItemStatus.NEEDS_ACTION,
            )
            for item in self.coordinator.data.shopping
        ]

    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Add."""
        await self.coordinator.async_add_item(item.summary or "")

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Rename / tick off."""
        changes = {"checked": item.status == TodoItemStatus.COMPLETED}
        if item.summary is not None:
            changes["text"] = item.summary
        await self.coordinator.async_update_item(item.uid, changes)
        await self.coordinator.async_refresh()

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        """Remove (hidden on Eetlijst)."""
        for uid in uids:
            await self.coordinator.async_update_item(uid, {"active": False})
        await self.coordinator.async_refresh()
