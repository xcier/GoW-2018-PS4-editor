from __future__ import annotations

from pathlib import Path
import tempfile

from app.core.backup_manager import list_backups_for_save, restore_backup_to_save
from app.core.change_report import build_change_report
from app.core.file_context import FileContext
from app.core.save_file import SaveFile


def test_backup_manager_lists_and_restores_without_savefile_resync() -> None:
    with tempfile.TemporaryDirectory() as td:
        folder = Path(td)
        target = folder / "memory.dat"
        backup = folder / "memory.dat.20260101-010101.bak"
        target.write_bytes(b"current")
        backup.write_bytes(b"backup")

        backups = list_backups_for_save(target)
        assert [b.path for b in backups] == [backup]

        rollback = restore_backup_to_save(backup, target)
        assert target.read_bytes() == b"backup"
        assert rollback.exists()
        assert rollback.read_bytes() == b"current"


def test_file_context_tracks_original_bytes_after_save() -> None:
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "memory.dat"
        path.write_bytes(b"abc")
        ctx = FileContext()
        ctx.load(path)
        assert ctx.original_bytes == b"abc"
        ctx.save.raw = b"abd"  # type: ignore[union-attr]
        assert ctx.has_byte_changes()
        ctx.save_to_disk(path)
        assert ctx.original_bytes == b"abd"
        assert not ctx.has_byte_changes()


def test_change_report_mentions_core_stats_and_byte_ranges() -> None:
    # Use a full slot-1-sized buffer so summarize_slot can read core fields.
    raw = bytearray(0x200000)
    save_old = SaveFile(raw=bytes(raw), active_slot=1)
    save_old._init_layout()
    save_old.difficulty = 1
    save_old.kratos_xp = 10
    save_old.hacksilver = 20
    save_old.commit_core_stats()

    save_new = SaveFile(raw=bytes(save_old.raw), active_slot=1)
    save_new._init_layout()
    save_new.difficulty = 3
    save_new.kratos_xp = 999
    save_new.hacksilver = 888
    save_new.commit_core_stats()

    report = build_change_report(save_old.raw, save_new.raw, active_slot=1)
    text = report.to_text()
    assert "Slot 1 active" in text
    assert "Kratos XP: 10 → 999" in text
    assert "Hacksilver: 20 → 888" in text
    assert "Raw byte ranges changed" in text


def test_change_report_has_no_changes_for_identical_bytes() -> None:
    report = build_change_report(b"same", b"same")
    assert not report.has_changes
    assert report.to_text() == "No byte changes detected."
