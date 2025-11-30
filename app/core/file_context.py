from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.core.save_file import SaveFile


@dataclass
class FileContext:
    path: Optional[Path] = None
    save: Optional[SaveFile] = None
    dirty: bool = False

    def load(self, path: Path) -> None:
        """Load a save file from disk into memory."""
        self.path = path
        self.save = SaveFile.from_path(path)
        self.dirty = False

    def mark_dirty(self) -> None:
        self.dirty = True

    def save_to_disk(self, target: Optional[Path] = None) -> None:
        """Write the current save to disk.

        If target is None, overwrite the original path.
        """
        if self.save is None:
            return
        if target is None:
            if self.path is None:
                raise RuntimeError("No save path set.")
            target = self.path
        self.save.write_to_path(target)
        self.path = target
        self.dirty = False
