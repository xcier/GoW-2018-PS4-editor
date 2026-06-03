from __future__ import annotations

import struct
import tempfile
import pytest
from pathlib import Path

from app.core import gow2018_data
from app.core.file_context import FileContext
from app.core.inventory_model import HACKSILVER_ITEM_ID, InventoryCommitError, MAX_INVENTORY_QTY, commit_inventory_rows, read_inventory_rows
from app.core.save_file import SaveFile


def test_slot_table_contains_all_actual_data_pointers() -> None:
    slots = gow2018_data.get_save_slots()
    assert len(slots) == 20
    assert gow2018_data.resolve_slot_base_offset(1) == 0x00001040
    assert gow2018_data.resolve_slot_base_offset(2) == 0x0019A908
    assert gow2018_data.resolve_slot_base_offset(3) == 0x003341D0
    assert gow2018_data.resolve_slot_base_offset(20) == 0x01E66718


def test_inventory_region_uses_verified_resource_table_offset() -> None:
    # Two full slot blocks are enough to verify slot 1's inventory range.
    raw_len = gow2018_data.resolve_slot_base_offset(3)
    start, end = gow2018_data.inventory_region_for_slot(raw_len, 1)
    assert start == 0x00001040 + 0x001041D
    assert end > start
    # The incorrect modernization offset had an extra zero and landed far away
    # from the real resource table.
    assert start != 0x00001040 + 0x001041D0


def test_core_stat_commit_writes_expected_offsets() -> None:
    raw_len = gow2018_data.resolve_slot_base_offset(3)
    save = SaveFile(raw=bytes(raw_len), active_slot=1)
    save._init_layout()
    save.difficulty = 3
    save.kratos_xp = 123456
    save.hacksilver = 654321
    save.commit_core_stats()
    data = bytes(save.raw)
    base = gow2018_data.resolve_slot_base_offset(1)
    assert data[base + 0x0010419] == 3
    assert int.from_bytes(data[base + 0x0010425 : base + 0x0010429], "little") == 123456
    assert int.from_bytes(data[base + 0x0010455 : base + 0x0010459], "little") == 654321


def test_inventory_anchor_matches_xp_main_entry() -> None:
    raw = _slot1_raw_with_valid_anchor()
    assert gow2018_data.inventory_anchor_is_valid(raw, 1)
    raw[gow2018_data.resolve_slot_base_offset(1) + gow2018_data.INVENTORY_TABLE_REL_OFFSET] = 0
    assert not gow2018_data.inventory_anchor_is_valid(raw, 1)


def test_atomic_write_creates_backup() -> None:
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "memory.dat"
        path.write_bytes(b"original")
        save = SaveFile(raw=b"edited", path=path)
        save.write_to_path(path)
        assert path.read_bytes() == b"edited"
        backups = list(Path(td).glob("memory.dat.*.bak"))
        assert len(backups) == 1
        assert backups[0].read_bytes() == b"original"


def test_atomic_write_backup_names_do_not_collide() -> None:
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "memory.dat"
        path.write_bytes(b"first")
        save = SaveFile(raw=b"second", path=path)
        save.write_to_path(path)
        save.raw = b"third"
        save.write_to_path(path)
        assert path.read_bytes() == b"third"
        backups = sorted(Path(td).glob("memory.dat.*.bak"))
        assert len(backups) == 2
        assert {p.read_bytes() for p in backups} == {b"first", b"second"}


def test_boost_all_armor_stats_reports_patch_counts() -> None:
    marker1, marker2 = gow2018_data.ARMOR_STAT_MARKERS["strength"]
    raw = bytearray(b"prefix")
    raw += bytes.fromhex(marker1)
    raw += bytes.fromhex(marker2)
    raw += struct.pack("<f", 12.5)
    raw += b"suffix"

    save = SaveFile(raw=bytes(raw))
    result = save.boost_all_armor_stats(99.0)
    assert result["strength"] == 1
    assert sum(result.values()) == 1
    assert save.get_armor_stat_values("strength") == [99.0]


def _slot1_raw_with_room() -> bytearray:
    # Slot 1 inventory region is valid when the buffer reaches slot 2.
    return bytearray(gow2018_data.resolve_slot_base_offset(2))


def _slot1_raw_with_valid_anchor() -> bytearray:
    raw = _slot1_raw_with_room()
    start, _ = gow2018_data.inventory_region_for_slot(len(raw), 1)
    raw[start : start + 8] = bytes.fromhex(gow2018_data.INVENTORY_TABLE_ANCHOR_ID)
    raw[start + 8 : start + 12] = (100).to_bytes(4, "little")
    raw[start + 12 : start + 16] = (15).to_bytes(4, "little")
    return raw


def test_inventory_commit_preserves_existing_flag_bytes() -> None:
    raw = _slot1_raw_with_valid_anchor()
    start, _ = gow2018_data.inventory_region_for_slot(len(raw), 1)
    pos = start + gow2018_data.INVENTORY_ENTRY_SIZE
    item_id = "0084906486DF5D22"
    raw[pos : pos + 8] = bytes.fromhex(item_id)
    raw[pos + 8 : pos + 12] = (1).to_bytes(4, "little")
    raw[pos + 12 : pos + 16] = b"FLAG"

    snapshot = read_inventory_rows(raw, 1, {})
    staged = [dict(row) for row in snapshot.items]
    for row in staged:
        if row["id"] == item_id:
            row["qty"] = 77
    result = commit_inventory_rows(
        raw,
        1,
        staged,
        snapshot.write_info,
        snapshot.free_positions,
    )

    assert result.raw[pos : pos + 8] == bytes.fromhex(item_id)
    assert int.from_bytes(result.raw[pos + 8 : pos + 12], "little") == 77
    assert result.raw[pos + 12 : pos + 16] == b"FLAG"


def test_inventory_commit_keeps_zero_quantity_existing_records() -> None:
    raw = _slot1_raw_with_valid_anchor()
    start, _ = gow2018_data.inventory_region_for_slot(len(raw), 1)
    pos = start + gow2018_data.INVENTORY_ENTRY_SIZE
    item_id = "9692D43E7833A3FD"
    raw[pos : pos + 8] = bytes.fromhex(item_id)
    raw[pos + 8 : pos + 12] = (0).to_bytes(4, "little")
    raw[pos + 12 : pos + 16] = (28).to_bytes(4, "little")

    snapshot = read_inventory_rows(raw, 1, {})
    result = commit_inventory_rows(raw, 1, snapshot.items, snapshot.write_info, snapshot.free_positions)

    assert result.raw[pos : pos + 8] == bytes.fromhex(item_id)
    assert int.from_bytes(result.raw[pos + 8 : pos + 12], "little") == 0
    assert int.from_bytes(result.raw[pos + 12 : pos + 16], "little") == 28


def test_inventory_commit_zeroes_new_entry_before_write() -> None:
    raw = _slot1_raw_with_valid_anchor()
    start, _ = gow2018_data.inventory_region_for_slot(len(raw), 1)
    free_pos = start + gow2018_data.INVENTORY_ENTRY_SIZE
    # Simulate a free entry with stale flag bytes. The writer should clear the
    # whole record before writing the newly allocated ID/qty.
    raw[free_pos : free_pos + 16] = b"\x00" * 12 + b"JUNK"
    item_id = "0084906486DF5D22"

    snapshot = read_inventory_rows(raw, 1, {})
    result = commit_inventory_rows(
        raw,
        1,
        list(snapshot.items) + [{"id": item_id, "qty": 5}],
        snapshot.write_info,
        [free_pos],
    )

    assert result.raw[free_pos : free_pos + 8] == bytes.fromhex(item_id)
    assert int.from_bytes(result.raw[free_pos + 8 : free_pos + 12], "little") == 5
    assert result.raw[free_pos + 12 : free_pos + 16] == b"\x00" * 4



def test_inventory_noop_preserves_existing_high_uint32_quantities() -> None:
    raw = _slot1_raw_with_valid_anchor()
    start, _ = gow2018_data.inventory_region_for_slot(len(raw), 1)
    pos = start + gow2018_data.INVENTORY_ENTRY_SIZE
    item_id = "0084906486DF5D22"
    raw[pos : pos + 8] = bytes.fromhex(item_id)
    raw[pos + 8 : pos + 12] = (4_294_967_295).to_bytes(4, "little")

    snapshot = read_inventory_rows(raw, 1, gow2018_data.get_items_by_id())
    result = commit_inventory_rows(raw, 1, snapshot.items, snapshot.write_info, snapshot.free_positions)

    assert result.raw == bytes(raw)
    assert int.from_bytes(result.raw[pos + 8 : pos + 12], "little") == 4_294_967_295


def test_inventory_quantity_clamps_to_nine_digit_max() -> None:
    raw = _slot1_raw_with_valid_anchor()
    start, _ = gow2018_data.inventory_region_for_slot(len(raw), 1)
    pos = start + gow2018_data.INVENTORY_ENTRY_SIZE
    item_id = "0084906486DF5D22"
    raw[pos : pos + 8] = bytes.fromhex(item_id)
    raw[pos + 8 : pos + 12] = (1).to_bytes(4, "little")

    snapshot = read_inventory_rows(raw, 1, gow2018_data.get_items_by_id())
    staged = [dict(row) for row in snapshot.items]
    for row in staged:
        if row["id"] == item_id:
            row["qty"] = 4_294_967_295

    result = commit_inventory_rows(raw, 1, staged, snapshot.write_info, snapshot.free_positions)

    assert MAX_INVENTORY_QTY == 999_999_999
    assert int.from_bytes(result.raw[pos + 8 : pos + 12], "little") == 999_999_999

def test_inventory_commit_refuses_without_table_anchor_and_keeps_raw_unchanged() -> None:
    raw = _slot1_raw_with_room()
    before = bytes(raw)
    with pytest.raises(InventoryCommitError):
        commit_inventory_rows(raw, 1, [{"id": "FFFFFFFFFFFFFFFF", "qty": 1}], {}, [])
    assert bytes(raw) == before


def test_inventory_commit_refuses_when_no_free_entries_and_keeps_raw_unchanged() -> None:
    raw = _slot1_raw_with_valid_anchor()
    start, end = gow2018_data.inventory_region_for_slot(len(raw), 1)
    entry_size = gow2018_data.INVENTORY_ENTRY_SIZE

    pos = start + entry_size
    counter = 1
    while pos + entry_size <= end:
        item_id = f"{counter:016X}"[-16:]
        raw[pos : pos + 8] = bytes.fromhex(item_id)
        raw[pos + 8 : pos + 12] = (1).to_bytes(4, "little")
        pos += entry_size
        counter += 1

    before = bytes(raw)
    snapshot = read_inventory_rows(raw, 1, {})
    with pytest.raises(InventoryCommitError):
        commit_inventory_rows(
            raw,
            1,
            snapshot.items + [{"id": "FFFFFFFFFFFFFFFF", "qty": 1}],
            snapshot.write_info,
            snapshot.free_positions,
        )
    assert bytes(raw) == before


def test_file_context_refuses_to_save_without_loaded_save() -> None:
    ctx = FileContext()
    with pytest.raises(RuntimeError):
        ctx.save_to_disk(Path("memory.dat"))


def test_inventory_noop_commit_preserves_duplicate_rows_exactly() -> None:
    raw = _slot1_raw_with_valid_anchor()
    start, _ = gow2018_data.inventory_region_for_slot(len(raw), 1)
    item_id = "0084906486DF5D22"
    for idx, qty in enumerate((2, 3), start=1):
        pos = start + idx * gow2018_data.INVENTORY_ENTRY_SIZE
        raw[pos : pos + 8] = bytes.fromhex(item_id)
        raw[pos + 8 : pos + 12] = qty.to_bytes(4, "little")
        raw[pos + 12 : pos + 16] = idx.to_bytes(4, "little")

    snapshot = read_inventory_rows(raw, 1, gow2018_data.get_items_by_id())
    assert sum(1 for row in snapshot.items if row["id"] == item_id) == 2
    result = commit_inventory_rows(raw, 1, snapshot.items, snapshot.write_info, snapshot.free_positions)
    assert result.raw == bytes(raw)



def test_hacksilver_inventory_row_is_editable_but_not_deletable() -> None:
    raw = _slot1_raw_with_valid_anchor()
    start, _ = gow2018_data.inventory_region_for_slot(len(raw), 1)
    pos = start + gow2018_data.INVENTORY_ENTRY_SIZE
    raw[pos : pos + 8] = bytes.fromhex(HACKSILVER_ITEM_ID)
    raw[pos + 8 : pos + 12] = (123).to_bytes(4, "little")
    raw[pos + 12 : pos + 16] = b"HS!!"

    snapshot = read_inventory_rows(raw, 1, gow2018_data.get_items_by_id())
    hacksilver_rows = [row for row in snapshot.items if row["id"] == HACKSILVER_ITEM_ID]
    assert len(hacksilver_rows) == 1
    assert hacksilver_rows[0]["protected"] is False
    assert hacksilver_rows[0]["removable"] is False

    staged = [dict(row) for row in snapshot.items]
    for row in staged:
        if row["id"] == HACKSILVER_ITEM_ID:
            row["qty"] = 999_999_999
    result = commit_inventory_rows(raw, 1, staged, snapshot.write_info, snapshot.free_positions)
    assert int.from_bytes(result.raw[pos + 8 : pos + 12], "little") == 999_999_999
    assert result.raw[pos + 12 : pos + 16] == b"HS!!"

    staged_without_hacksilver = [row for row in snapshot.items if row["id"] != HACKSILVER_ITEM_ID]
    with pytest.raises(InventoryCommitError):
        commit_inventory_rows(raw, 1, staged_without_hacksilver, snapshot.write_info, snapshot.free_positions)

def test_inventory_commit_refuses_to_delete_protected_anchor() -> None:
    raw = _slot1_raw_with_valid_anchor()
    snapshot = read_inventory_rows(raw, 1, gow2018_data.get_items_by_id())
    staged_without_xp = [row for row in snapshot.items if row["id"] != gow2018_data.INVENTORY_TABLE_ANCHOR_ID]
    with pytest.raises(InventoryCommitError):
        commit_inventory_rows(raw, 1, staged_without_xp, snapshot.write_info, snapshot.free_positions)


def _write_slot_header(raw: bytearray, slot_index: int, timestamp: int, location: str) -> None:
    base = gow2018_data.resolve_slot_base_offset(slot_index)
    raw[base : base + 4] = int(timestamp).to_bytes(4, "little")
    encoded = location.encode("utf-8")[:180]
    raw[base + 0x10 : base + 0x10 + len(encoded)] = encoded
    raw[base + 0x10 + len(encoded)] = 0


def test_from_path_opens_most_recent_active_slot() -> None:
    raw_len = gow2018_data.resolve_slot_base_offset(3) + 0x200
    raw = bytearray(raw_len)
    _write_slot_header(raw, 1, 1_700_000_000, "Midgard - Old Manual Save")
    _write_slot_header(raw, 2, 1_700_000_500, "Midgard - New Autosave")

    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "memory.dat"
        path.write_bytes(raw)
        save = SaveFile.from_path(path)

    assert save.active_slot == 2
    assert save.summarize_slot(save.active_slot)["location"] == "Midgard - New Autosave"


def test_from_path_respects_explicit_active_slot_override() -> None:
    raw_len = gow2018_data.resolve_slot_base_offset(3) + 0x200
    raw = bytearray(raw_len)
    _write_slot_header(raw, 1, 1_700_000_000, "Midgard - Old Manual Save")
    _write_slot_header(raw, 2, 1_700_000_500, "Midgard - New Autosave")

    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "memory.dat"
        path.write_bytes(raw)
        save = SaveFile.from_path(path, active_slot=1)

    assert save.active_slot == 1


def test_most_recent_active_slot_ignores_empty_zero_timestamp_slots() -> None:
    raw_len = gow2018_data.resolve_slot_base_offset(4) + 0x200
    raw = bytearray(raw_len)
    _write_slot_header(raw, 1, 1_700_000_000, "Midgard - Real Save")
    # Slot 2/3 remain empty and should not win just because they exist.
    save = SaveFile(raw=raw)

    assert save.find_most_recent_active_slot() == 1


def test_inventory_commit_can_update_add_and_remove_editable_items() -> None:
    raw = _slot1_raw_with_valid_anchor()
    start, _ = gow2018_data.inventory_region_for_slot(len(raw), 1)
    entry_size = gow2018_data.INVENTORY_ENTRY_SIZE
    existing_pos = start + entry_size
    removable_id = "0084906486DF5D22"  # known editable armor row from bundled ItemIDS data
    added_id = "0538FA2C08F5C3E8"

    raw[existing_pos : existing_pos + 8] = bytes.fromhex(removable_id)
    raw[existing_pos + 8 : existing_pos + 12] = (7).to_bytes(4, "little")
    raw[existing_pos + 12 : existing_pos + 16] = b"KEEP"

    snapshot = read_inventory_rows(raw, 1, gow2018_data.get_items_by_id())

    # Update the known row first; the flag bytes must be preserved.
    staged_update = [dict(row) for row in snapshot.items]
    for row in staged_update:
        if row["id"] == removable_id:
            row["qty"] = 77
    updated = commit_inventory_rows(raw, 1, staged_update, snapshot.write_info, snapshot.free_positions)
    assert int.from_bytes(updated.raw[existing_pos + 8 : existing_pos + 12], "little") == 77
    assert updated.raw[existing_pos + 12 : existing_pos + 16] == b"KEEP"

    # Remove the editable row and add a new known row; the freed slot may be reused safely.
    snapshot2 = read_inventory_rows(updated.raw, 1, gow2018_data.get_items_by_id())
    staged_replace = [dict(row) for row in snapshot2.items if row["id"] != removable_id]
    staged_replace.append({"id": added_id, "name": "Reaver Tunic Lv3", "type": "Armor", "qty": 9})
    replaced = commit_inventory_rows(updated.raw, 1, staged_replace, snapshot2.write_info, snapshot2.free_positions)
    assert bytes.fromhex(removable_id) not in replaced.raw[start : start + entry_size * 4]
    assert bytes.fromhex(added_id) in replaced.raw[start : start + entry_size * 4]


def test_hacksilver_core_stat_resolves_dynamic_inventory_row() -> None:
    raw = _slot1_raw_with_valid_anchor()
    start, _ = gow2018_data.inventory_region_for_slot(len(raw), 1)
    legacy_pos = start + 3 * gow2018_data.INVENTORY_ENTRY_SIZE
    real_pos = start + 4 * gow2018_data.INVENTORY_ENTRY_SIZE
    # The old dashboard assumed row 3. This sample keeps row 3 occupied by a
    # different record and places Hacksilver at row 4, matching real saves where
    # the resource table row order shifts.
    raw[legacy_pos : legacy_pos + 8] = bytes.fromhex("74A0EA5CE2ECF857")
    raw[legacy_pos + 8 : legacy_pos + 12] = (1).to_bytes(4, "little")
    raw[real_pos : real_pos + 8] = bytes.fromhex(HACKSILVER_ITEM_ID)
    raw[real_pos + 8 : real_pos + 12] = (178_808).to_bytes(4, "little")
    raw[real_pos + 12 : real_pos + 16] = b"HS!!"

    save = SaveFile(raw=bytes(raw), active_slot=1)
    save._init_layout()
    save._load_core_stats_from_binary()
    assert save.hacksilver == 178_808

    save.hacksilver = 999_999_999
    save.commit_core_stats()
    data = bytes(save.raw)
    assert int.from_bytes(data[legacy_pos + 8 : legacy_pos + 12], "little") == 1
    assert int.from_bytes(data[real_pos + 8 : real_pos + 12], "little") == 999_999_999
    assert data[real_pos + 12 : real_pos + 16] == b"HS!!"


def test_to_bytes_does_not_normalize_untouched_core_bytes() -> None:
    raw = _slot1_raw_with_valid_anchor()
    base = gow2018_data.resolve_slot_base_offset(1)
    raw[base + 0x0010419 : base + 0x001041D] = (28).to_bytes(4, "little")
    save = SaveFile(raw=bytes(raw), active_slot=1)
    save._init_layout()
    save._load_core_stats_from_binary()
    assert save.to_bytes() == bytes(raw)


def test_xp_inventory_row_is_editable_but_not_deletable_and_updates_core_bytes() -> None:
    raw = _slot1_raw_with_valid_anchor()
    start, _ = gow2018_data.inventory_region_for_slot(len(raw), 1)

    snapshot = read_inventory_rows(raw, 1, gow2018_data.get_items_by_id())
    xp_rows = [row for row in snapshot.items if row["id"] == gow2018_data.INVENTORY_TABLE_ANCHOR_ID]
    assert len(xp_rows) == 1
    assert xp_rows[0]["protected"] is False
    assert xp_rows[0]["removable"] is False

    staged = [dict(row) for row in snapshot.items]
    for row in staged:
        if row["id"] == gow2018_data.INVENTORY_TABLE_ANCHOR_ID:
            row["qty"] = 999_999_999
    result = commit_inventory_rows(raw, 1, staged, snapshot.write_info, snapshot.free_positions)
    assert int.from_bytes(result.raw[start + 8 : start + 12], "little") == 999_999_999

    staged_without_xp = [row for row in snapshot.items if row["id"] != gow2018_data.INVENTORY_TABLE_ANCHOR_ID]
    with pytest.raises(InventoryCommitError):
        commit_inventory_rows(raw, 1, staged_without_xp, snapshot.write_info, snapshot.free_positions)


def test_dashboard_xp_commit_uses_same_inventory_anchor_quantity() -> None:
    raw = _slot1_raw_with_valid_anchor()
    start, _ = gow2018_data.inventory_region_for_slot(len(raw), 1)
    raw[start + 8 : start + 12] = (343).to_bytes(4, "little")

    save = SaveFile(raw=bytes(raw), active_slot=1)
    save._init_layout()
    save._load_core_stats_from_binary()
    assert save.kratos_xp == 343

    save.kratos_xp = 123_456_789
    save.commit_core_stats(fields={"kratos_xp"})
    data = bytes(save.raw)
    assert int.from_bytes(data[start + 8 : start + 12], "little") == 123_456_789
    assert data[start : start + 8] == bytes.fromhex(gow2018_data.INVENTORY_TABLE_ANCHOR_ID)


def test_incomplete_metadata_rows_get_names_but_stay_locked() -> None:
    raw = _slot1_raw_with_valid_anchor()
    start, _ = gow2018_data.inventory_region_for_slot(len(raw), 1)
    pos = start + gow2018_data.INVENTORY_ENTRY_SIZE
    system_id = "C65F861310000000"  # Present in ItemIDs as file=Axe, but has no friendly name/type.
    raw[pos : pos + 8] = bytes.fromhex(system_id)
    raw[pos + 8 : pos + 12] = (1).to_bytes(4, "little")

    snapshot = read_inventory_rows(raw, 1, gow2018_data.get_items_by_id())
    rows = [row for row in snapshot.items if row["id"] == system_id]
    assert len(rows) == 1
    assert rows[0]["name"] == "Axe"
    assert rows[0]["type"] == "Weapon / Upgrade"
    assert rows[0]["protected"] is True
    assert rows[0]["removable"] is False


def test_item_database_infers_readable_metadata_without_unlocking_risky_rows() -> None:
    items = gow2018_data.get_items_by_id()
    armor = items["FDA3E31201646AAF"]
    assert armor["name"] == "Plated Volunder Cuirass"
    assert armor["type"] == "Chest Armor"
    assert armor["metadata_source"] == "inferred"
    assert armor["safe_edit"] is False

    perk = items["088A3223FC045E9F"]
    assert perk["name"] == "Perk Flat On Kill Rage Reinforce1"
    assert perk["type"] == "Perk / Enchantment"
    assert perk["safe_edit"] is False


def test_item_database_known_resources_remain_safe_editable() -> None:
    items = gow2018_data.get_items_by_id()
    aegir = items["F54355FA3AB3C7FF"]
    assert aegir["name"] == "Aegir's Gold"
    assert aegir["type"] == "Resources"
    assert aegir["safe_edit"] is True


def test_inventory_reads_known_extended_rows_past_original_256_record_table() -> None:
    raw = _slot1_raw_with_valid_anchor()
    start, fixed_end = gow2018_data.inventory_region_for_slot(len(raw), 1)
    extra_id = "0084906486DF5D22"
    raw[fixed_end : fixed_end + 8] = bytes.fromhex(extra_id)
    raw[fixed_end + 8 : fixed_end + 12] = (77).to_bytes(4, "little")
    raw[fixed_end + 12 : fixed_end + 16] = (256).to_bytes(4, "little")

    snapshot = read_inventory_rows(raw, 1, gow2018_data.get_items_by_id())

    assert snapshot.end == fixed_end + gow2018_data.INVENTORY_ENTRY_SIZE
    assert any(row["id"] == extra_id and row["qty"] == 77 for row in snapshot.items)


def test_experimental_append_can_allocate_after_detected_table_when_full() -> None:
    raw = _slot1_raw_with_valid_anchor()
    start, fixed_end = gow2018_data.inventory_region_for_slot(len(raw), 1)
    entry_size = gow2018_data.INVENTORY_ENTRY_SIZE
    filler_id = "0084906486DF5D22"
    new_id = "0538FA2C08F5C3E8"

    # Fill every fixed row so the normal safe allocator has no free records.
    for i in range(1, gow2018_data.INVENTORY_ENTRY_COUNT):
        pos = start + i * entry_size
        raw[pos : pos + 8] = bytes.fromhex(filler_id)
        raw[pos + 8 : pos + 12] = (1).to_bytes(4, "little")
        raw[pos + 12 : pos + 16] = i.to_bytes(4, "little")

    snapshot = read_inventory_rows(raw, 1, gow2018_data.get_items_by_id())
    staged = [dict(row) for row in snapshot.items]
    staged.append({"id": new_id, "qty": 9, "offset": None})

    with pytest.raises(InventoryCommitError):
        commit_inventory_rows(raw, 1, staged, snapshot.write_info, snapshot.free_positions)

    result = commit_inventory_rows(
        raw,
        1,
        staged,
        snapshot.write_info,
        snapshot.free_positions,
        allow_overflow_append=True,
    )

    assert result.raw[fixed_end : fixed_end + 8] == bytes.fromhex(new_id)
    assert int.from_bytes(result.raw[fixed_end + 8 : fixed_end + 12], "little") == 9
    assert result.allocated_entries == 1
