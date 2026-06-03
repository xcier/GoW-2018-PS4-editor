from __future__ import annotations

from pathlib import Path
import datetime
import os
import shutil
import tempfile
from typing import Optional


def make_backup_path(path: Path) -> Path:
    """Return a timestamped, non-colliding backup path next to ``path``."""
    path = Path(path)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = path.with_name(f"{path.name}.{stamp}.bak")
    counter = 1
    while backup.exists():
        backup = path.with_name(f"{path.name}.{stamp}.{counter}.bak")
        counter += 1
    return backup


def atomic_write_bytes(path: Path, data: bytes | bytearray, *, create_backup: bool = True) -> Optional[Path]:
    """Atomically write bytes to ``path`` and optionally preserve the old file.

    Returns the backup path when one was created, otherwise ``None``.
    """
    path = Path(path)
    payload = bytes(data)
    path.parent.mkdir(parents=True, exist_ok=True)

    backup_path: Optional[Path] = None
    if create_backup and path.exists():
        backup_path = make_backup_path(path)
        shutil.copy2(path, backup_path)

    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise

    return backup_path
