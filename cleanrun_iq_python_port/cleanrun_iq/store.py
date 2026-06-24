"""JSON-backed persistence replacing the Rork AsyncStorage store."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from pydantic import ValidationError

from cleanrun_iq.models import Item, Settings
from cleanrun_iq.seed import build_demo_items, build_demo_settings


class StoreError(RuntimeError):
    """Raised when the local store cannot be read or written."""


class JsonStore:
    """Small JSON-backed data store.

    Args:
        path: Directory used for JSON persistence.
    """

    def __init__(self, path: str | Path = "./data") -> None:
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)
        self.items_path = self.path / "items.json"
        self.settings_path = self.path / "settings.json"
        self._items: list[Item] | None = None
        self._settings: Settings | None = None

    def get_items(self) -> list[Item]:
        """Load items.

        Returns:
            List of items.

        Raises:
            StoreError: If JSON is invalid.
        """
        if self._items is not None:
            return self._items
        if not self.items_path.exists():
            self._items = build_demo_items()
            self.save_items(self._items)
            return self._items
        try:
            raw = json.loads(self.items_path.read_text(encoding="utf-8"))
            self._items = [Item.model_validate(item) for item in raw]
            return self._items
        except (json.JSONDecodeError, ValidationError) as exc:
            raise StoreError(f"Could not load items: {exc}") from exc

    def save_items(self, items: list[Item]) -> None:
        """Persist items.

        Args:
            items: Items to persist.

        Raises:
            StoreError: If writing fails.
        """
        try:
            self._items = items
            payload = [item.model_dump(by_alias=True, mode="json") for item in items]
            self.items_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except OSError as exc:
            raise StoreError(f"Could not save items: {exc}") from exc

    def get_settings(self) -> Settings:
        """Load settings.

        Returns:
            Settings instance.

        Raises:
            StoreError: If JSON is invalid.
        """
        if self._settings is not None:
            return self._settings
        if not self.settings_path.exists():
            self._settings = build_demo_settings()
            self.save_settings(self._settings)
            return self._settings
        try:
            raw = json.loads(self.settings_path.read_text(encoding="utf-8"))
            self._settings = Settings.model_validate(raw)
            return self._settings
        except (json.JSONDecodeError, ValidationError) as exc:
            raise StoreError(f"Could not load settings: {exc}") from exc

    def save_settings(self, settings: Settings) -> None:
        """Persist settings.

        Args:
            settings: Settings to persist.

        Raises:
            StoreError: If writing fails.
        """
        try:
            self._settings = settings
            self.settings_path.write_text(settings.model_dump_json(by_alias=True, indent=2), encoding="utf-8")
        except OSError as exc:
            raise StoreError(f"Could not save settings: {exc}") from exc

    def patch_item(self, item_id: str, mutator: Callable[[Item], Item]) -> Item:
        """Patch one item and persist the list.

        Args:
            item_id: ID of the item to update.
            mutator: Function returning the updated item.

        Returns:
            Updated item.

        Raises:
            KeyError: If the item does not exist.
        """
        items = self.get_items()
        updated: Item | None = None
        next_items: list[Item] = []
        for item in items:
            if item.id == item_id:
                updated = mutator(item)
                next_items.append(updated)
            else:
                next_items.append(item)
        if updated is None:
            raise KeyError(f"Item not found: {item_id}")
        self.save_items(next_items)
        return updated
