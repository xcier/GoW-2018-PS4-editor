from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from app.core.change_report import ChangeReport, build_change_report
from app.core.save_file import SaveFile


@dataclass
class FileContext:
    path: Optional[Path] = None
    save: Optional[SaveFile] = None
    dirty: bool = False
    original_bytes: Optional[bytes] = None
    on_dirty_changed: Optional[Callable[[bool], None]] = None

    def _set_dirty(self, value: bool) -> None:
        if self.dirty == value:
            return
        self.dirty = value
        if self.on_dirty_changed is not None:
            self.on_dirty_changed(value)

    def load(self, path: Path) -> None:
        """Load a save file and select the newest active slot automatically."""
        self.path = path
        self.save = SaveFile.from_path(path)
        self.original_bytes = bytes(self.save.raw)
        self._set_dirty(False)

    def mark_dirty(self) -> None:
        self._set_dirty(True)

    def current_bytes(self) -> bytes:
        if self.save is None:
            return b""
        return self.save.to_bytes()

    def has_byte_changes(self) -> bool:
        if self.save is None:
            return False
        before = self.original_bytes if self.original_bytes is not None else b""
        return before != self.current_bytes()

    def build_change_report(self) -> ChangeReport:
        if self.save is None:
            return ChangeReport()
        return build_change_report(
            self.original_bytes if self.original_bytes is not None else b"",
            self.current_bytes(),
            active_slot=int(getattr(self.save, "active_slot", 1) or 1),
        )

    def save_to_disk(self, target: Optional[Path] = None) -> None:
        """Write the current save to disk.

        If target is None, overwrite the original path.
        """
        if self.save is None:
            raise RuntimeError("No save is loaded.")
        if target is None:
            if self.path is None:
                raise RuntimeError("No save path set.")
            target = self.path
        self.save.write_to_path(target)
        self.path = target
        self.original_bytes = bytes(self.save.raw)
        self._set_dirty(False)
