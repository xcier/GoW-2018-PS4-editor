from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import datetime
import shutil
from typing import Iterable, List, Optional

from app.core.atomic_write import atomic_write_bytes


@dataclass(frozen=True)
class BackupInfo:
    path: Path
    size: int
    modified_ts: float

    @property
    def modified_label(self) -> str:
        try:
            return datetime.datetime.fromtimestamp(self.modified_ts).strftime("%Y-%m-%d %H:%M:%S")
        except (OverflowError, OSError, ValueError):
            return "Unknown"

    @property
    def size_label(self) -> str:
        size = int(self.size)
        if size >= 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        if size >= 1024:
            return f"{size / 1024:.1f} KB"
        return f"{size} B"


def backup_glob_for(target: Path) -> str:
    return f"{Path(target).name}.*.bak"


def list_backups_for_save(target: Optional[Path]) -> List[BackupInfo]:
    """List timestamped backups next to a save path, newest first."""
    if target is None:
        return []
    target = Path(target)
    if not target.parent.exists():
        return []

    backups: list[BackupInfo] = []
    for path in target.parent.glob(backup_glob_for(target)):
        if not path.is_file():
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        backups.append(BackupInfo(path=path, size=stat.st_size, modified_ts=stat.st_mtime))
    backups.sort(key=lambda info: (info.modified_ts, info.path.name), reverse=True)
    return backups


def restore_backup_to_save(backup_path: Path, target_path: Path) -> Path:
    """Restore a backup over the active save using the same atomic+backup discipline.

    A backup of the current target is created before the restore. The returned
    path is that pre-restore backup. This function deliberately writes raw bytes
    rather than constructing SaveFile, because SaveFile.to_bytes() would sync the
    currently selected slot fields and could alter a pristine backup.
    """
    backup_path = Path(backup_path)
    target_path = Path(target_path)
    if not backup_path.exists() or not backup_path.is_file():
        raise FileNotFoundError(f"Backup does not exist: {backup_path}")
    if not target_path.exists() or not target_path.is_file():
        raise FileNotFoundError(f"Target save does not exist: {target_path}")

    data = backup_path.read_bytes()
    created_backup = atomic_write_bytes(target_path, data, create_backup=True)
    if created_backup is None:
        raise RuntimeError("Restore did not create a pre-restore backup.")
    return created_backup
