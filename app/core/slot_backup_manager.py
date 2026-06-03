from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any, Optional, Union

from app.core.atomic_write import atomic_write_bytes
from app.core.slot_transfer import (
    DEFAULT_EXTENSION,
    SlotPackage,
    SlotTransferResult,
    copy_slot_between_bytes,
    import_slot_package_file_into_bytes,
    read_slot_package,
    write_slot_package,
)


@dataclass(frozen=True)
class SlotBackupInfo:
    """Metadata for one portable slot backup package."""

    path: Path
    package: SlotPackage
    size: int
    modified_ts: float

    @property
    def source_slot(self) -> int:
        return self.package.source_slot

    @property
    def display_label(self) -> str:
        return self.package.display_label

    @property
    def summary(self) -> dict[str, Any]:
        value = self.package.metadata.get("summary", {})
        return value if isinstance(value, dict) else {}

    @property
    def modified_label(self) -> str:
        try:
            return datetime.fromtimestamp(self.modified_ts).strftime("%Y-%m-%d %H:%M:%S")
        except (OverflowError, OSError, ValueError):
            return "Unknown"

    @property
    def created_label(self) -> str:
        created = str(self.package.metadata.get("created_utc", "") or "").strip()
        if not created:
            return self.modified_label
        try:
            dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
            return dt.astimezone().strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            return created

    @property
    def size_label(self) -> str:
        size = int(self.size)
        if size >= 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        if size >= 1024:
            return f"{size / 1024:.1f} KB"
        return f"{size} B"

    @property
    def location_label(self) -> str:
        return str(self.summary.get("location", "") or "")

    @property
    def xp_label(self) -> str:
        try:
            return f"{int(self.summary.get('xp', 0) or 0):,}"
        except Exception:
            return "0"

    @property
    def hacksilver_label(self) -> str:
        try:
            return f"{int(self.summary.get('hacksilver', 0) or 0):,}"
        except Exception:
            return "0"


_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _raw_bytes(raw: Union[bytes, bytearray]) -> bytes:
    if isinstance(raw, bytearray):
        return bytes(raw)
    if isinstance(raw, bytes):
        return raw
    raise TypeError("raw must be bytes or bytearray")


def slot_backup_dir_for_save(save_path: Optional[Path]) -> Optional[Path]:
    """Return the per-save folder that stores slot backup packages."""
    if save_path is None:
        return None
    save_path = Path(save_path)
    return save_path.parent / f"{save_path.name}.slot_backups"


def _slug(value: Any, *, fallback: str = "slot") -> str:
    text = str(value or "").strip()
    if not text:
        text = fallback
    text = _SAFE_NAME_RE.sub("-", text).strip("-._")
    return text[:64] or fallback


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    for index in range(1, 1000):
        candidate = path.with_name(f"{stem}-{index:02d}{suffix}")
        if not candidate.exists():
            return candidate
    raise FileExistsError(f"Could not create a unique slot backup path near {path}")


def default_slot_backup_path(save_path: Path, source_slot: int, summary: Optional[dict[str, Any]] = None, *, display_label: str = "") -> Path:
    """Build a human-readable default package path for a slot backup."""
    folder = slot_backup_dir_for_save(save_path)
    if folder is None:
        raise ValueError("A save path is required to create a slot backup path.")
    folder.mkdir(parents=True, exist_ok=True)

    summary = summary or {}
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    label = _slug(display_label, fallback="")
    loc = _slug(summary.get("location", ""), fallback="gow2018")
    label_part = f"-{label}" if label else ""
    filename = f"slot{int(source_slot):02d}{label_part}-{loc}-{stamp}{DEFAULT_EXTENSION}"
    return _unique_path(folder / filename)


def create_slot_backup(
    raw: Union[bytes, bytearray],
    save_path: Path,
    source_slot: int,
    *,
    output_path: Optional[Path] = None,
    display_label: str = "",
) -> SlotBackupInfo:
    """Export one slot from the loaded save into the save's slot-backup folder."""
    from app.core.slot_transfer import summarize_slot  # local import avoids circular surprises in tests

    data = _raw_bytes(raw)
    summary = summarize_slot(data, int(source_slot))
    if output_path is None:
        output_path = default_slot_backup_path(Path(save_path), int(source_slot), summary, display_label=display_label)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    package = write_slot_package(data, int(source_slot), output_path, source_path=Path(save_path), display_label=display_label)
    stat = output_path.stat()
    return SlotBackupInfo(path=output_path, package=package, size=stat.st_size, modified_ts=stat.st_mtime)


def list_slot_backups_for_save(save_path: Optional[Path]) -> list[SlotBackupInfo]:
    """List valid .gow2018slot backups for the loaded save, newest first."""
    folder = slot_backup_dir_for_save(save_path)
    if folder is None or not folder.exists():
        return []

    backups: list[SlotBackupInfo] = []
    for path in folder.glob(f"*{DEFAULT_EXTENSION}"):
        if not path.is_file():
            continue
        try:
            package = read_slot_package(path)
            stat = path.stat()
        except Exception:
            continue
        backups.append(SlotBackupInfo(path=path, package=package, size=stat.st_size, modified_ts=stat.st_mtime))
    backups.sort(key=lambda item: (item.modified_ts, item.path.name), reverse=True)
    return backups


def import_slot_backup_into_bytes(
    target_raw: Union[bytes, bytearray],
    backup_path: Path,
    target_slot: int,
) -> tuple[bytes, SlotTransferResult]:
    """Stage a slot backup package into an in-memory target save."""
    return import_slot_package_file_into_bytes(_raw_bytes(target_raw), Path(backup_path), int(target_slot))


def clone_slot_within_bytes(
    raw: Union[bytes, bytearray],
    source_slot: int,
    target_slot: int,
    *,
    source_path: Optional[Path] = None,
) -> tuple[bytes, SlotTransferResult]:
    """Stage a full physical slot copy within the same save buffer."""
    data = _raw_bytes(raw)
    return copy_slot_between_bytes(data, int(source_slot), data, int(target_slot), source_path=source_path)


def write_slot_backup_to_memory_dat(
    backup_path: Path,
    target_path: Path,
    target_slot: int,
) -> Path:
    """Write a slot backup into another memory.dat on disk and return the rollback .bak path."""
    target_path = Path(target_path)
    if not target_path.exists() or not target_path.is_file():
        raise FileNotFoundError(f"Target save does not exist: {target_path}")
    new_raw, _result = import_slot_backup_into_bytes(target_path.read_bytes(), backup_path, int(target_slot))
    rollback = atomic_write_bytes(target_path, new_raw, create_backup=True)
    if rollback is None:
        raise RuntimeError("External slot transfer did not create a rollback backup.")
    return rollback


def copy_slot_to_memory_dat(
    source_raw: Union[bytes, bytearray],
    source_slot: int,
    target_path: Path,
    target_slot: int,
    *,
    source_path: Optional[Path] = None,
) -> Path:
    """Copy a slot from the loaded save into another memory.dat on disk."""
    target_path = Path(target_path)
    if not target_path.exists() or not target_path.is_file():
        raise FileNotFoundError(f"Target save does not exist: {target_path}")
    new_raw, _result = copy_slot_between_bytes(
        _raw_bytes(source_raw),
        int(source_slot),
        target_path.read_bytes(),
        int(target_slot),
        source_path=source_path,
    )
    rollback = atomic_write_bytes(target_path, new_raw, create_backup=True)
    if rollback is None:
        raise RuntimeError("External slot transfer did not create a rollback backup.")
    return rollback
