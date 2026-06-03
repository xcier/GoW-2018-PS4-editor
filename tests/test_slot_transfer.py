from __future__ import annotations

from pathlib import Path
import tempfile

import pytest

from app.core import gow2018_data
from app.core.slot_transfer import (
    SlotTransferError,
    copy_slot_between_bytes,
    import_slot_package_file_into_bytes,
    read_slot_package,
    replace_slot_bytes,
    slot_looks_used,
    write_slot_package,
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


def test_slot_block_size_is_derived_from_actual_slot_table() -> None:
    assert gow2018_data.get_slot_block_size() == 0x1998C8
    start, end = gow2018_data.slot_range_for_slot(33_554_400, 11)
    assert end - start == 0x1998C8


def test_copy_slot_between_bytes_replaces_only_target_slot_range() -> None:
    source = _full_raw()
    target = _full_raw()
    _mark_slot(source, 3, b"SRC3")
    _mark_slot(target, 7, b"TGT7")
    before = bytes(target)

    new_raw, result = copy_slot_between_bytes(source, 3, target, 7)
    src_start, src_end = gow2018_data.slot_range_for_slot(len(source), 3)
    dst_start, dst_end = gow2018_data.slot_range_for_slot(len(target), 7)

    assert result.target_slot == 7
    assert new_raw[dst_start:dst_end] == bytes(source[src_start:src_end])
    assert new_raw[:dst_start] == before[:dst_start]
    assert new_raw[dst_end:] == before[dst_end:]
    assert slot_looks_used(new_raw, 7)


def test_slot_package_roundtrip_imports_into_target_slot() -> None:
    raw = _full_raw()
    target = _full_raw()
    _mark_slot(raw, 5, b"PKG5")
    _mark_slot(target, 1, b"TARG")

    with tempfile.TemporaryDirectory() as td:
        package_path = Path(td) / "slot5.gow2018slot"
        package = write_slot_package(raw, 5, package_path)
        loaded = read_slot_package(package_path)
        assert loaded.sha256 == package.sha256

        new_raw, result = import_slot_package_file_into_bytes(target, package_path, 2)

    src_start, src_end = gow2018_data.slot_range_for_slot(len(raw), 5)
    dst_start, dst_end = gow2018_data.slot_range_for_slot(len(target), 2)
    assert result.source_slot == 5
    assert new_raw[dst_start:dst_end] == bytes(raw[src_start:src_end])


def test_refuses_to_export_empty_slot() -> None:
    raw = _full_raw()
    with tempfile.TemporaryDirectory() as td:
        with pytest.raises(SlotTransferError):
            write_slot_package(raw, 1, Path(td) / "empty.gow2018slot")


def test_replace_refuses_wrong_sized_slot_block() -> None:
    target = _full_raw()
    with pytest.raises(SlotTransferError):
        replace_slot_bytes(target, 1, b"too small")


def test_slot_package_display_label_roundtrip() -> None:
    raw = _full_raw()
    _mark_slot(raw, 4, b"LAB4")
    with tempfile.TemporaryDirectory() as td:
        package_path = Path(td) / "custom.gow2018slot"
        write_slot_package(raw, 4, package_path, display_label="100 percent source")
        loaded = read_slot_package(package_path)
    assert loaded.display_label == "100 percent source"
    assert loaded.source_slot == 4
