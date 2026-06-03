from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Union

from app.core import gow2018_data

MAX_INVENTORY_QTY = 999_999_999
XP_ITEM_ID = gow2018_data.INVENTORY_TABLE_ANCHOR_ID
HACKSILVER_ITEM_ID = "9E5240D27406E85A"
CORE_QUANTITY_ITEM_IDS = {XP_ITEM_ID, HACKSILVER_ITEM_ID}
CORE_FIELD_BY_ITEM_ID = {
    XP_ITEM_ID: "kratos_xp",
    HACKSILVER_ITEM_ID: "hacksilver",
}

# Some saves continue the inventory/resource rows past the original 256-row
# community table. We still treat the first 256 rows as the safe fixed table,
# then only extend while rows have IDs present in the community item DB. This
# keeps random slot data after the table from being interpreted as inventory.
EXTRA_KNOWN_ROW_SCAN_LIMIT = 2048
DEFAULT_UNSAFE_APPEND_LIMIT = 4096

# Rows in this set cannot be edited from the inventory grid. XP Main used to
# live here because it is the resource-table anchor, but that made the UI look
# broken: XP is a normal quantity stored in the anchor row. It must stay
# non-deletable/non-duplicable, but the amount bytes are safe to edit. Unknown
# rows are still locked dynamically by _meta_for_item().
LOCKED_ITEM_IDS: set[str] = set()

# Structural/core economy records. They are safe quantity rows, but they must
# never be deleted or duplicated because other editor pages and game systems
# depend on them existing exactly once in the slot resource table.
NON_DELETABLE_ITEM_IDS = CORE_QUANTITY_ITEM_IDS

# Backward-compatible name used by older tests/tools. It now means
# edit-locked, not merely protected from deletion.
PROTECTED_ITEM_IDS = LOCKED_ITEM_IDS


class InventoryCommitError(ValueError):
    """Raised when an inventory edit cannot be safely committed."""


@dataclass(frozen=True)
class InventoryReadResult:
    items: List[Dict[str, Union[int, str, bool]]]
    write_info: Dict[str, List[int]]
    free_positions: List[int]
    start: int
    end: int
    anchor_valid: bool = True

    @property
    def region(self) -> tuple[int, int]:
        return (self.start, self.end)


@dataclass(frozen=True)
class InventoryCommitResult:
    raw: bytes
    written_items: int
    freed_entries: int
    allocated_entries: int


def _raw_bytes(raw: Union[bytes, bytearray]) -> bytes:
    if isinstance(raw, bytearray):
        return bytes(raw)
    if isinstance(raw, bytes):
        return raw
    raise TypeError("raw must be bytes or bytearray")


def _clamp_qty(value: Any) -> int:
    try:
        qty = int(value)
    except (TypeError, ValueError):
        qty = 0
    return max(0, min(qty, MAX_INVENTORY_QTY))


def _meta_for_item(item_id: str, items_by_id: Mapping[str, Mapping[str, Any]]) -> tuple[str, str, bool]:
    meta = items_by_id.get(item_id)
    if meta:
        name = str(meta.get("name") or meta.get("file") or "").strip() or "(Unknown/System)"
        type_ = str(meta.get("type") or "").strip() or "Technical / Unclassified"
        safe_edit = bool(meta.get("safe_edit", False))
    else:
        name = "(Unknown/System)"
        type_ = "Unknown"
        safe_edit = False

    protected = item_id in LOCKED_ITEM_IDS or not safe_edit
    return name or "(Unknown/System)", type_ or "Unknown", protected


def _deletion_allowed(item_id: str, items_by_id: Mapping[str, Mapping[str, Any]] | None = None) -> bool:
    item_id = gow2018_data.normalize_item_id(item_id)
    if not item_id or item_id in NON_DELETABLE_ITEM_IDS:
        return False
    if items_by_id is None:
        items_by_id = gow2018_data.get_items_by_id()
    meta = items_by_id.get(item_id)
    if not meta:
        return False
    return bool(meta.get("safe_edit", False))


def read_inventory_rows(
    raw: Union[bytes, bytearray],
    slot_index: int,
    items_by_id: Mapping[str, Mapping[str, Any]] | None = None,
) -> InventoryReadResult:
    """Read every occupied resource/inventory record without mutating raw.

    The previous model aggregated duplicate item IDs. Real saves can contain
    duplicate/special records, so each row is now preserved by exact file offset.
    """
    data = _raw_bytes(raw)
    start, end = gow2018_data.inventory_region_for_slot(len(data), int(slot_index))
    if end <= start:
        return InventoryReadResult([], {}, [], start, end, False)

    anchor_valid = gow2018_data.inventory_anchor_is_valid(data, int(slot_index))
    if not anchor_valid:
        return InventoryReadResult([], {}, [], start, end, False)

    if items_by_id is None:
        items_by_id = gow2018_data.get_items_by_id()

    write_info: Dict[str, List[int]] = {}
    free_positions: List[int] = []
    items: List[Dict[str, Union[int, str, bool]]] = []

    entry_size = gow2018_data.INVENTORY_ENTRY_SIZE
    fixed_entries = gow2018_data.INVENTORY_ENTRY_COUNT
    slot_start, slot_end = gow2018_data.slot_range_for_slot(len(data), int(slot_index))
    if slot_end <= start:
        slot_end = end

    def add_entry(pos: int, row_number: int) -> None:
        entry = data[pos : pos + entry_size]
        id_bytes = entry[0:8]
        qty = int.from_bytes(entry[8:12], "little", signed=False)
        id_hex = id_bytes.hex().upper()

        # Treat zero-ID/zero-quantity records inside the fixed table as
        # available even if stale flag bytes are present; new-entry writes zero
        # the whole record first. Beyond the fixed table, a zero row means the
        # extension ended, not thousands of open records.
        if id_bytes == b"\x00" * 8 and qty == 0:
            free_positions.append(pos)
            return

        name, type_, protected = _meta_for_item(id_hex, items_by_id)
        write_info.setdefault(id_hex, []).append(pos)
        items.append(
            {
                "id": id_hex,
                "name": name,
                "type": type_,
                "qty": qty,
                "offset": pos,
                "row": row_number,
                "protected": protected,
                "removable": _deletion_allowed(id_hex, items_by_id),
            }
        )

    # First pass: the fixed table is part of the known safe model, including
    # unknown/progression rows that the database cannot name yet.
    row_count = 0
    pos = start
    fixed_end = min(end, start + fixed_entries * entry_size, slot_end)
    while pos + entry_size <= fixed_end and row_count < fixed_entries:
        add_entry(pos, row_count)
        pos += entry_size
        row_count += 1

    logical_end = max(fixed_end, pos)

    # Second pass: some saves continue with extra known DB-backed rows after
    # the first 256 entries. Only include rows whose IDs are in the database;
    # stop at the first zero row or unknown/random-looking record.
    extra_scanned = 0
    while pos + entry_size <= slot_end and extra_scanned < EXTRA_KNOWN_ROW_SCAN_LIMIT:
        entry = data[pos : pos + entry_size]
        if entry == b"\x00" * entry_size:
            break
        id_hex = entry[0:8].hex().upper()
        if id_hex not in items_by_id:
            break
        add_entry(pos, row_count)
        pos += entry_size
        row_count += 1
        extra_scanned += 1
        logical_end = pos

    items.sort(key=lambda r: (bool(r.get("protected", False)), str(r["name"]).lower(), int(r["offset"])))
    return InventoryReadResult(items, write_info, free_positions, start, logical_end, anchor_valid)




def read_item_quantity(
    raw: Union[bytes, bytearray],
    slot_index: int,
    item_id: str,
) -> int | None:
    """Return the first matching inventory quantity for item_id in a slot.

    This intentionally performs a tiny direct table scan instead of building
    the full inventory model. Save loading calls this for each slot to locate
    Hacksilver, and the full model does name/type lookup, deletion checks, and
    sorting that are unnecessary for one quantity.
    """
    wanted = gow2018_data.normalize_item_id(item_id)
    if not wanted:
        return None
    data = _raw_bytes(raw)
    start, end = gow2018_data.inventory_region_for_slot(len(data), int(slot_index))
    if end <= start or not gow2018_data.inventory_anchor_is_valid(data, int(slot_index)):
        return None

    wanted_bytes = bytes.fromhex(wanted)
    entry_size = gow2018_data.INVENTORY_ENTRY_SIZE
    max_entries = gow2018_data.INVENTORY_ENTRY_COUNT
    row_count = 0
    pos = start
    while pos + entry_size <= end and row_count < max_entries:
        if data[pos : pos + 8] == wanted_bytes:
            return int.from_bytes(data[pos + 8 : pos + 12], "little", signed=False)
        pos += entry_size
        row_count += 1
    return None


def write_item_quantity(
    raw: Union[bytes, bytearray],
    slot_index: int,
    item_id: str,
    qty: int,
) -> InventoryCommitResult | None:
    """Update an existing inventory quantity by item ID.

    Returns None if the table is unavailable or the item is not present. The
    writer never allocates a new core resource row here; it only updates the
    existing row found by ID and preserves the record's metadata bytes.
    """
    wanted = gow2018_data.normalize_item_id(item_id)
    if not wanted:
        return None
    snapshot = read_inventory_rows(raw, slot_index, gow2018_data.get_items_by_id())
    if not snapshot.anchor_valid:
        return None
    staged = [dict(row) for row in snapshot.items]
    found = False
    for row in staged:
        if gow2018_data.normalize_item_id(row.get("id")) == wanted:
            row["qty"] = _clamp_qty(qty)
            found = True
            break
    if not found:
        return None
    return commit_inventory_rows(raw, slot_index, staged, snapshot.write_info, snapshot.free_positions)

def commit_inventory_rows(
    raw: Union[bytes, bytearray],
    slot_index: int,
    items_in_save: Sequence[Mapping[str, Any]],
    item_write_info: Mapping[str, Sequence[int]],
    free_entry_positions: Iterable[int],
    *,
    allow_overflow_append: bool = False,
    overflow_append_limit: int = DEFAULT_UNSAFE_APPEND_LIMIT,
) -> InventoryCommitResult:
    """Safely commit a row-preserving inventory model back into raw bytes.

    The function performs a full preflight before mutating a copy of the save:
    invalid IDs, invalid anchors, unsafe deletions, invalid offsets, or
    insufficient free entries raise an error and leave the caller's raw object
    untouched.
    """
    data = _raw_bytes(raw)
    start, fixed_end = gow2018_data.inventory_region_for_slot(len(data), int(slot_index))
    if fixed_end <= start:
        raise InventoryCommitError("Inventory region is not valid; refusing to write to avoid corruption.")
    if not gow2018_data.inventory_anchor_is_valid(data, int(slot_index)):
        raise InventoryCommitError(
            "Inventory table anchor was not found at the expected offset; "
            "refusing to write to avoid corrupting the slot."
        )

    entry_size = gow2018_data.INVENTORY_ENTRY_SIZE
    _slot_start, slot_end = gow2018_data.slot_range_for_slot(len(data), int(slot_index))
    if slot_end <= fixed_end:
        slot_end = fixed_end

    def aligned_inventory_pos(pos: int) -> bool:
        return start <= pos and pos + entry_size <= slot_end and ((pos - start) % entry_size == 0)

    # Existing rows can legally live past the historical 256-row table on some
    # saves. Build the write bound from every known row/free offset first, then
    # use that as the experimental append point if the user explicitly enables
    # unsafe append mode.
    known_end = fixed_end
    candidate_positions: list[int] = []
    for positions in item_write_info.values():
        for pos_raw in positions:
            try:
                candidate_positions.append(int(pos_raw))
            except (TypeError, ValueError):
                pass
    for pos_raw in free_entry_positions:
        try:
            candidate_positions.append(int(pos_raw))
        except (TypeError, ValueError):
            pass
    for row in items_in_save:
        offset_value = row.get("offset")
        if offset_value not in (None, ""):
            try:
                candidate_positions.append(int(offset_value))
            except (TypeError, ValueError):
                pass
    for pos in candidate_positions:
        if aligned_inventory_pos(pos):
            known_end = max(known_end, pos + entry_size)

    def valid_pos(pos: int) -> bool:
        return aligned_inventory_pos(pos) and pos + entry_size <= max(known_end, fixed_end)

    original_positions_by_id: Dict[str, List[int]] = {}
    original_id_by_position: Dict[int, str] = {}
    for item_id_raw, positions in item_write_info.items():
        item_id = gow2018_data.normalize_item_id(item_id_raw)
        if not item_id:
            continue
        clean_positions = []
        for pos_raw in positions:
            pos = int(pos_raw)
            if valid_pos(pos):
                clean_positions.append(pos)
                original_id_by_position[pos] = item_id
        if clean_positions:
            original_positions_by_id[item_id] = clean_positions

    occupied_positions = set(original_id_by_position)
    free_pool = sorted(set(int(p) for p in free_entry_positions if valid_pos(int(p))) - occupied_positions)

    staged_existing: Dict[int, tuple[str, int]] = {}
    staged_new: List[tuple[str, int]] = []
    invalid_ids: List[str] = []
    invalid_offsets: List[str] = []

    for row in items_in_save:
        item_id = gow2018_data.normalize_item_id(row.get("id"))
        raw_qty = row.get("qty", 0)
        if not item_id:
            invalid_ids.append(str(row.get("id", "<blank>")))
            continue

        offset_value = row.get("offset")
        if offset_value is None or offset_value == "":
            staged_new.append((item_id, _clamp_qty(raw_qty)))
            continue

        try:
            pos = int(offset_value)
        except (TypeError, ValueError):
            invalid_offsets.append(str(offset_value))
            continue
        if not valid_pos(pos):
            invalid_offsets.append(str(offset_value))
            continue
        if pos in staged_existing:
            invalid_offsets.append(f"duplicate offset 0x{pos:X}")
            continue

        original_id = original_id_by_position.get(pos)
        original_qty = int.from_bytes(data[pos + 8 : pos + 12], "little", signed=False)
        try:
            requested_qty = int(raw_qty)
        except (TypeError, ValueError):
            requested_qty = 0

        # Existing saves may already contain high uint32 quantities from older
        # builds or external editors. A no-op commit must preserve those bytes;
        # the new nine-digit cap applies only when a row is actually edited or
        # newly allocated.
        if original_id == item_id and requested_qty == original_qty:
            qty = original_qty
        else:
            qty = _clamp_qty(raw_qty)
        staged_existing[pos] = (item_id, qty)

    if invalid_ids:
        shown = ", ".join(invalid_ids[:8])
        more = "..." if len(invalid_ids) > 8 else ""
        raise InventoryCommitError(f"Inventory contains invalid item IDs: {shown}{more}")
    if invalid_offsets:
        shown = ", ".join(invalid_offsets[:8])
        more = "..." if len(invalid_offsets) > 8 else ""
        raise InventoryCommitError(f"Inventory contains invalid row offsets: {shown}{more}")

    retained_positions = set(staged_existing)
    positions_freed_by_delete = sorted(occupied_positions - retained_positions)

    unsafe_deletes = []
    for pos in positions_freed_by_delete:
        item_id = original_id_by_position.get(pos, "")
        if not _deletion_allowed(item_id):
            unsafe_deletes.append(f"{item_id or '<unknown>'} @ 0x{pos:X}")
    if unsafe_deletes:
        shown = ", ".join(unsafe_deletes[:6])
        more = "..." if len(unsafe_deletes) > 6 else ""
        raise InventoryCommitError(
            "Refusing to delete protected/unknown system records. Remove only known editable items. "
            f"Blocked: {shown}{more}"
        )

    available_slots = len(free_pool) + len(positions_freed_by_delete)
    needed_slots = len(staged_new)
    if needed_slots > available_slots:
        if not allow_overflow_append:
            raise InventoryCommitError(
                "Not enough free inventory entries for the staged add operation. "
                f"Needed {needed_slots}, available {available_slots}."
            )
        missing = needed_slots - available_slots
        if missing > int(overflow_append_limit):
            raise InventoryCommitError(
                "Experimental append would add too many rows at once. "
                f"Needed {missing}, limit {int(overflow_append_limit)}."
            )
        append_start = max(known_end, fixed_end)
        appended_positions: list[int] = []
        for i in range(missing):
            pos = append_start + (i * entry_size)
            if not aligned_inventory_pos(pos):
                raise InventoryCommitError(
                    "Experimental append would leave the physical slot block; refusing to write."
                )
            appended_positions.append(pos)
        free_pool.extend(appended_positions)
        known_end = max(known_end, append_start + missing * entry_size)

    buf = bytearray(data)
    freed_entries = 0
    allocated_entries = 0

    # Clear records for deleted, allowed items first; those offsets can be reused.
    for pos in positions_freed_by_delete:
        buf[pos : pos + entry_size] = b"\x00" * entry_size
        free_pool.append(pos)
        freed_entries += 1

    free_pool = sorted(set(free_pool) - retained_positions)

    for pos, (item_id, qty) in staged_existing.items():
        id_bytes = bytes.fromhex(item_id)
        # Preserve the last 4 bytes for existing records.
        buf[pos : pos + 8] = id_bytes
        buf[pos + 8 : pos + 12] = int(qty).to_bytes(4, "little")

    for item_id, qty in staged_new:
        pos = free_pool.pop(0)
        id_bytes = bytes.fromhex(item_id)
        # New records must not inherit stale unknown/flag bytes.
        buf[pos : pos + entry_size] = b"\x00" * entry_size
        buf[pos : pos + 8] = id_bytes
        buf[pos + 8 : pos + 12] = int(qty).to_bytes(4, "little")
        allocated_entries += 1

    return InventoryCommitResult(
        raw=bytes(buf),
        written_items=len(staged_existing) + len(staged_new),
        freed_entries=freed_entries,
        allocated_entries=allocated_entries,
    )
