from __future__ import annotations

from pathlib import Path
import tempfile

from app.core import gow2018_data
from app.core.slot_backup_manager import (
    clone_slot_within_bytes,
    copy_slot_to_memory_dat,
    create_slot_backup,
    import_slot_backup_into_bytes,
    list_slot_backups_for_save,
    slot_backup_dir_for_save,
    write_slot_backup_to_memory_dat,
)


def _full_raw() -> bytearray:
    size = gow2018_data.resolve_slot_base_offset(20) + gow2018_data.get_slot_block_size()
    return bytearray(size)


def _mark_slot(raw: bytearray, slot: int, marker: bytes, timestamp: int = 1_700_000_000) -> None:
    start, end = gow2018_data.slot_range_for_slot(len(raw), slot)
    raw[start:end] = (marker * ((end - start) // len(marker) + 1))[: end - start]
    raw[start : start + 4] = int(timestamp).to_bytes(4, "little")
    location = f"Midgard - Slot {slot}".encode("utf-8")
    raw[start + 0x10 : start + 0x10 + len(location)] = location
    raw[start + 0x10 + len(location)] = 0
    inv_start, _ = gow2018_data.inventory_region_for_slot(len(raw), slot)
    raw[inv_start : inv_start + 8] = bytes.fromhex(gow2018_data.INVENTORY_TABLE_ANCHOR_ID)


def test_slot_backup_folder_is_per_save() -> None:
    assert slot_backup_dir_for_save(Path("/tmp/memory.dat")) == Path("/tmp/memory.dat.slot_backups")
    assert slot_backup_dir_for_save(None) is None


def test_create_and_list_slot_backups() -> None:
    raw = _full_raw()
    _mark_slot(raw, 4, b"SLOT")
    with tempfile.TemporaryDirectory() as td:
        save_path = Path(td) / "memory.dat"
        save_path.write_bytes(raw)

        info = create_slot_backup(raw, save_path, 4)
        assert info.path.exists()
        assert info.source_slot == 4
        assert info.path.parent == slot_backup_dir_for_save(save_path)

        listed = list_slot_backups_for_save(save_path)
        assert [item.path for item in listed] == [info.path]
        assert listed[0].source_slot == 4
        assert listed[0].location_label.startswith("Midgard")


def test_restore_slot_backup_into_bytes_changes_only_target_slot() -> None:
    source = _full_raw()
    target = _full_raw()
    _mark_slot(source, 6, b"SRC6")
    _mark_slot(target, 8, b"TGT8")
    before = bytes(target)

    with tempfile.TemporaryDirectory() as td:
        save_path = Path(td) / "memory.dat"
        save_path.write_bytes(source)
        info = create_slot_backup(source, save_path, 6)
        new_raw, result = import_slot_backup_into_bytes(target, info.path, 8)

    src_start, src_end = gow2018_data.slot_range_for_slot(len(source), 6)
    dst_start, dst_end = gow2018_data.slot_range_for_slot(len(target), 8)
    assert result.target_slot == 8
    assert new_raw[dst_start:dst_end] == bytes(source[src_start:src_end])
    assert new_raw[:dst_start] == before[:dst_start]
    assert new_raw[dst_end:] == before[dst_end:]


def test_clone_slot_within_bytes_changes_only_target_slot() -> None:
    raw = _full_raw()
    _mark_slot(raw, 2, b"SRC2")
    _mark_slot(raw, 3, b"TGT3")
    before = bytes(raw)

    new_raw, result = clone_slot_within_bytes(raw, 2, 3)

    src_start, src_end = gow2018_data.slot_range_for_slot(len(raw), 2)
    dst_start, dst_end = gow2018_data.slot_range_for_slot(len(raw), 3)
    assert result.source_slot == 2
    assert result.target_slot == 3
    assert new_raw[dst_start:dst_end] == before[src_start:src_end]
    assert new_raw[:dst_start] == before[:dst_start]
    assert new_raw[dst_end:] == before[dst_end:]


def test_write_slot_backup_to_other_memory_dat_creates_rollback() -> None:
    source = _full_raw()
    target = _full_raw()
    _mark_slot(source, 9, b"SRC9")
    _mark_slot(target, 10, b"TG10")
    with tempfile.TemporaryDirectory() as td:
        folder = Path(td)
        source_path = folder / "source_memory.dat"
        target_path = folder / "target_memory.dat"
        source_path.write_bytes(source)
        target_path.write_bytes(target)
        before_target = target_path.read_bytes()

        info = create_slot_backup(source, source_path, 9)
        rollback = write_slot_backup_to_memory_dat(info.path, target_path, 10)

        src_start, src_end = gow2018_data.slot_range_for_slot(len(source), 9)
        dst_start, dst_end = gow2018_data.slot_range_for_slot(len(target), 10)
        after_target = target_path.read_bytes()
        assert rollback.exists()
        assert rollback.read_bytes() == before_target
        assert after_target[dst_start:dst_end] == bytes(source[src_start:src_end])


def test_copy_loaded_slot_to_other_memory_dat_creates_rollback() -> None:
    source = _full_raw()
    target = _full_raw()
    _mark_slot(source, 11, b"S011")
    _mark_slot(target, 12, b"T012")
    with tempfile.TemporaryDirectory() as td:
        target_path = Path(td) / "target_memory.dat"
        target_path.write_bytes(target)
        before_target = target_path.read_bytes()

        rollback = copy_slot_to_memory_dat(source, 11, target_path, 12)

        src_start, src_end = gow2018_data.slot_range_for_slot(len(source), 11)
        dst_start, dst_end = gow2018_data.slot_range_for_slot(len(target), 12)
        after_target = target_path.read_bytes()
        assert rollback.exists()
        assert rollback.read_bytes() == before_target
        assert after_target[dst_start:dst_end] == bytes(source[src_start:src_end])


def test_slot_backup_display_label_is_saved() -> None:
    raw = _full_raw()
    _mark_slot(raw, 3, b"LBL3")
    with tempfile.TemporaryDirectory() as td:
        save_path = Path(td) / "memory.dat"
        save_path.write_bytes(raw)
        info = create_slot_backup(raw, save_path, 3, display_label="Fresh save import")
        listed = list_slot_backups_for_save(save_path)
    assert info.display_label == "Fresh save import"
    assert listed[0].display_label == "Fresh save import"
