# app/core/save_file.py
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, Optional, Union
import struct
import datetime

from app.core import gow2018_data
from app.core.gow2018_layout import build_layout_for_slot, LayoutSpec, SlotField
from app.core.atomic_write import atomic_write_bytes
from app.core.inventory_model import HACKSILVER_ITEM_ID, XP_ITEM_ID, read_item_quantity, write_item_quantity

Number = Union[int, float]


# Markers lifted from Skiller's Save Wizard codes.
# They look like:
#
#   Skiller#4741   Defense - (Pick only the one/s your Armor has)
#       You need to Stack them with ...
#
# In JSON form (simplified):
#
#   {
#       "DEFENCE_1": ["5DB74F7B", "CF35641B"],
#       "RUNIC_1":   ["...", "..."],
#       ...
#   }
#
# We use these to find the actual float stat value in the save and then
# either read or overwrite it.
ARMOR_STAT_MARKERS: Dict[str, tuple[str, str]] = gow2018_data.ARMOR_STAT_MARKERS

# Inventory table layout shared with the UI.
INVENTORY_TABLE_REL_OFFSET: int = gow2018_data.INVENTORY_TABLE_REL_OFFSET
INVENTORY_ENTRY_SIZE: int = gow2018_data.INVENTORY_ENTRY_SIZE
INVENTORY_ENTRY_COUNT: int = gow2018_data.INVENTORY_ENTRY_COUNT


@dataclass
class SaveFile:
    """
    Thin wrapper around the raw PS4/PC save buffer.

    Responsibilities:
      - keep track of the active slot (1..N)
      - expose core stats for that slot (difficulty, XP, hacksilver)
      - expose inventory items for that slot (via helper methods)
      - know how to load/store these values from/to self.raw
      - boost_armor_* helpers that work across the whole file

    Core stat offsets come from gow2018_layout, which uses
    gow2018_slots.json to resolve per-slot base pointers.
    """

    raw: Union[bytes, bytearray] = b""
    path: Optional[Path] = None

    # slot/layout info
    active_slot: int = 1
    layout: Optional[LayoutSpec] = None

    # simple core stats for the active slot
    difficulty: int = 0       # 0=Story,1=Balanced,2=Challenge,3=GOW
    kratos_xp: int = 0
    hacksilver: int = 0

    # inventory cache for the active slot (keyed by row index)
    inventory_items: Dict[int, Dict[str, Union[int, str]]] = field(
        default_factory=dict
    )

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def from_path(cls, path: Path, active_slot: Optional[int] = None) -> "SaveFile":
        raw = path.read_bytes()
        save = cls(raw=raw, path=path)

        if active_slot is None:
            active_slot = save.find_most_recent_active_slot()

        save.active_slot = int(active_slot)
        save._init_layout()
        save._load_core_stats_from_binary()
        save._load_inventory_from_binary()

        return save

    # ------------------------------------------------------------------
    # Layout helpers
    # ------------------------------------------------------------------

    def _init_layout(self) -> None:
        """
        Resolve a base offset for the current active slot and build
        a LayoutSpec describing core stat offsets.
        """
        base_off = gow2018_data.resolve_slot_base_offset(self.active_slot)
        if base_off <= 0 or base_off >= len(self.raw):
            # leave layout as None; callers should handle this gracefully
            self.layout = None
            return

        self.layout = build_layout_for_slot(self.active_slot, base_off)

    def _ensure_layout(self) -> None:
        if self.layout is None:
            self._init_layout()

    def _get_field_def(self, name: str) -> Optional[SlotField]:
        self._ensure_layout()
        if self.layout is None:
            return None
        return self.layout.fields.get(name)

    def _read_primitive(self, field: SlotField) -> Number:
        """
        Read a primitive value (int/float) from the raw buffer using the
        field's type and offset.
        """
        buf = self.raw
        start = self.layout.base_offset + field.offset
        if start < 0 or start >= len(buf):
            raise ValueError(f"Field {field.name} out of range")

        fmt_map = {
            "u8": "<B",
            "u16": "<H",
            "u32": "<I",
            "s32": "<i",
            "f32": "<f",
        }
        fmt = fmt_map[field.type]
        size = struct.calcsize(fmt)
        if start + size > len(buf):
            raise ValueError(f"Field {field.name} out of range")

        return struct.unpack_from(fmt, buf, start)[0]

    @staticmethod
    def _coerce_primitive_value(field: SlotField, value: Number) -> Number:
        """Clamp/cast values before struct.pack_into to avoid partial writes."""
        if field.type == "f32":
            return float(value)

        ivalue = int(value)
        if field.type == "u8":
            return max(0, min(ivalue, 0xFF))
        if field.type == "u16":
            return max(0, min(ivalue, 0xFFFF))
        if field.type == "u32":
            return max(0, min(ivalue, 0xFFFFFFFF))
        if field.type == "s32":
            return max(-0x80000000, min(ivalue, 0x7FFFFFFF))
        return ivalue

    def _write_primitive(self, field: SlotField, value: Number) -> None:
        """
        Write a primitive value (int/float) into the raw buffer using the
        field's type and offset.
        """
        if isinstance(self.raw, bytes):
            # convert to mutable buffer if necessary
            self.raw = bytearray(self.raw)

        buf = self.raw
        start = self.layout.base_offset + field.offset
        if start < 0 or start >= len(buf):
            raise ValueError(f"Field {field.name} out of range")

        fmt_map = {
            "u8": "<B",
            "u16": "<H",
            "u32": "<I",
            "s32": "<i",
            "f32": "<f",
        }
        fmt = fmt_map[field.type]
        size = struct.calcsize(fmt)
        if start + size > len(buf):
            raise ValueError(f"Field {field.name} out of range")

        struct.pack_into(fmt, buf, start, self._coerce_primitive_value(field, value))

    # ------------------------------------------------------------------
    # Dynamic inventory-backed core resources
    # ------------------------------------------------------------------

    def _read_inventory_quantity_by_id(self, item_id: str) -> Optional[int]:
        """Read a resource quantity by item ID in the active slot table.

        Real saves do not always keep core resources on the same row. Hacksilver
        in particular can be row 3 in one save and row 4 in another, so the
        dashboard must resolve it by item ID instead of a fixed relative offset.
        """
        try:
            return read_item_quantity(self.raw, int(self.active_slot), item_id)
        except Exception:
            return None

    def _write_inventory_quantity_by_id(self, item_id: str, value: int) -> bool:
        """Write a resource quantity by item ID if that row exists."""
        try:
            result = write_item_quantity(self.raw, int(self.active_slot), item_id, int(value))
        except Exception:
            return False
        if result is None:
            return False
        self.raw = result.raw
        return True

    # ------------------------------------------------------------------
    # Core stats
    # ------------------------------------------------------------------

    def _load_core_stats_from_binary(self) -> None:
        """
        Populate difficulty / kratos_xp / hacksilver for the current
        active slot by reading from raw.
        """
        self._ensure_layout()
        if self.layout is None:
            # nothing we can do; leave defaults
            self.difficulty = 0
            self.kratos_xp = 0
            self.hacksilver = 0
            return

        diff_field = self._get_field_def("difficulty")
        xp_field = self._get_field_def("kratos_xp")
        hs_field = self._get_field_def("hacksilver")

        try:
            self.difficulty = int(self._read_primitive(diff_field))
        except Exception:
            self.difficulty = 0

        # XP is the first inventory/resource row and doubles as the validated
        # table anchor. Resolve it by item ID first so Dashboard and Inventory
        # always describe the same quantity bytes. Fall back to the legacy
        # primitive field for synthetic/minimal buffers that do not include a
        # validated inventory table.
        xp_value = self._read_inventory_quantity_by_id(XP_ITEM_ID)
        if xp_value is not None:
            self.kratos_xp = int(xp_value)
        else:
            try:
                self.kratos_xp = int(self._read_primitive(xp_field))
            except Exception:
                self.kratos_xp = 0

        # Hacksilver is stored as an inventory/resource row, and real saves
        # can place that row at different indices. Prefer the dynamic item-ID
        # lookup and fall back to the legacy fixed field only if the table is
        # unavailable.
        hs_value = self._read_inventory_quantity_by_id(HACKSILVER_ITEM_ID)
        if hs_value is not None:
            self.hacksilver = int(hs_value)
        else:
            try:
                self.hacksilver = int(self._read_primitive(hs_field))
            except Exception:
                self.hacksilver = 0

    def _store_core_stats_to_binary(self, fields: Optional[Iterable[str]] = None) -> None:
        """
        Write selected in-memory core stats for the active slot back into raw.

        ``fields`` is intentionally supported so editing Hacksilver or XP does
        not also normalize an untouched difficulty byte from a save variant the
        editor does not fully understand yet.
        """
        self._ensure_layout()
        if self.layout is None:
            return

        selected = set(fields) if fields is not None else {"difficulty", "kratos_xp", "hacksilver"}

        diff_field = self._get_field_def("difficulty")
        xp_field = self._get_field_def("kratos_xp")
        hs_field = self._get_field_def("hacksilver")

        # difficulty is always clamped into [0,3] when explicitly edited.
        if "difficulty" in selected and diff_field is not None:
            v = int(self.difficulty)
            if v < 0:
                v = 0
            if v > 3:
                v = 3
            self._write_primitive(diff_field, v)

        if "kratos_xp" in selected:
            xp_written = self._write_inventory_quantity_by_id(XP_ITEM_ID, int(self.kratos_xp))
            if not xp_written and xp_field is not None:
                self._write_primitive(xp_field, int(self.kratos_xp))

        # Prefer the resource-table row so Dashboard Hacksilver stays in sync
        # even when the row moves inside the table. Fall back to the legacy
        # fixed field for synthetic/minimal buffers with no validated table.
        if "hacksilver" in selected:
            hs_written = self._write_inventory_quantity_by_id(HACKSILVER_ITEM_ID, int(self.hacksilver))
            if not hs_written and hs_field is not None:
                self._write_primitive(hs_field, int(self.hacksilver))

    def commit_core_stats(self, fields: Optional[Iterable[str]] = None) -> None:
        """
        Called by the Stats tab whenever the user edits difficulty/XP/HS.
        """
        self._store_core_stats_to_binary(fields=fields)

    # ------------------------------------------------------------------
    # Slot selection + summary
    # ------------------------------------------------------------------

    @staticmethod
    def _coerce_summary_int(summary: Dict[str, Union[int, str]], key: str) -> int:
        try:
            return int(summary.get(key, 0))
        except (TypeError, ValueError):
            return 0

    def _slot_summary_looks_active(self, slot_index: int, summary: Optional[Dict[str, Union[int, str]]]) -> bool:
        """Return True when a slot summary appears to describe a real used slot.

        Empty save blocks in GoW 2018 commonly read as timestamp 0, empty
        location, and zeroed stats. We require a plausible timestamp plus at
        least one real-data signal so auto-selection does not jump to blank or
        malformed slot blocks.
        """
        if not summary:
            return False

        ts_raw = self._coerce_summary_int(summary, "last_played_raw")
        # 2000-01-01 through 2100-01-01 keeps obviously empty/corrupt values
        # from winning auto-selection while accepting normal PS4 save dates.
        if not (946684800 <= ts_raw <= 4102444800):
            return False

        location = str(summary.get("location", "")).strip()
        xp = self._coerce_summary_int(summary, "xp")
        hacksilver = self._coerce_summary_int(summary, "hacksilver")
        has_inventory_anchor = gow2018_data.inventory_anchor_is_valid(self.raw, slot_index)

        return bool(location or xp or hacksilver or has_inventory_anchor)

    def find_most_recent_active_slot(self) -> int:
        """Return the newest used save slot based on each slot timestamp.

        The community slot table stores every physical slot base, but many
        saves contain blank unused slot blocks. This helper ignores those and
        chooses the valid used slot with the highest last-played timestamp.
        """
        slots = gow2018_data.get_save_slots()
        valid_slots = sorted(
            int(s["slot"])
            for s in slots
            if isinstance(s.get("slot"), int) and int(s["slot"]) > 0
        )
        if not valid_slots:
            return 1

        best_slot = valid_slots[0]
        best_timestamp = -1
        for slot_index in valid_slots:
            summary = self.summarize_slot(slot_index)
            if not self._slot_summary_looks_active(slot_index, summary):
                continue
            timestamp = self._coerce_summary_int(summary, "last_played_raw")
            if timestamp > best_timestamp or (timestamp == best_timestamp and slot_index > best_slot):
                best_slot = slot_index
                best_timestamp = timestamp

        return best_slot

    def set_active_slot(self, slot_index: int) -> None:
        """
        Change which slot subsequent operations refer to, clamped to the
        actual slot numbers defined in gow2018_slots.json.
        """
        slots = gow2018_data.get_save_slots()

        if not slots:
            # Fallback if metadata is missing
            slot_index = 1
        else:
            # Collect all positive integer slot numbers from the JSON
            valid = sorted(
                s["slot"]
                for s in slots
                if isinstance(s.get("slot"), int) and s["slot"] > 0
            )
            if not valid:
                slot_index = 1
            else:
                min_slot = valid[0]
                max_slot = valid[-1]

                if slot_index < min_slot:
                    slot_index = min_slot
                if slot_index > max_slot:
                    slot_index = max_slot

        self.active_slot = slot_index
        # Force layout rebuild on next access and refresh core stats
        self.layout = None
        self._load_core_stats_from_binary()
        self._load_inventory_from_binary()

    def summarize_slot(self, slot_index: int) -> Optional[Dict[str, Union[int, str]]]:
        """
        Quick summary for Slot N, read directly from raw bytes without
        mutating active_slot/layout.

        Returns a dict like:
            {
              "slot": N,
              "difficulty": 0..3,
              "difficulty_name": "...",
              "xp": 123,
              "hacksilver": 456,
              "location": "...",
              "last_played_raw": 1764638325,
              "last_played": "2025-12-02 01:18",
            }
        """
        base_off = gow2018_data.resolve_slot_base_offset(slot_index)
        if base_off <= 0 or base_off + 0x20 > len(self.raw):
            return None

        buf = self.raw

        # 1) Last played timestamp (first 4 bytes at base offset).
        # The save stores this as a little-endian Unix epoch; we convert it
        # to *local* time so it matches what the console UI shows.
        ts_raw = struct.unpack_from("<I", buf, base_off)[0]
        dt_str = ""
        try:
            dt = datetime.datetime.fromtimestamp(ts_raw)
            dt_str = dt.strftime("%Y-%m-%d %H:%M")
        except (OverflowError, OSError, ValueError):
            ts_raw = 0
            dt_str = ""

        # 2) Location / objective string at base + 0x10, null-terminated UTF-8
        loc_start = base_off + 0x10
        loc_end = loc_start
        max_len = 200
        while (
            loc_end < len(buf)
            and buf[loc_end] != 0
            and (loc_end - loc_start) < max_len
        ):
            loc_end += 1
        loc_bytes = buf[loc_start:loc_end]
        try:
            location = loc_bytes.decode("utf-8", "replace")
        except Exception:
            location = ""

        # 3) Core stats using a temporary layout
        layout = build_layout_for_slot(slot_index, base_off)

        def read_field(name: str) -> Optional[int]:
            field = layout.fields.get(name)
            if not field:
                return None

            start = layout.base_offset + field.offset
            if start < 0 or start >= len(buf):
                return None

            fmt_map = {
                "u8": "<B",
                "u16": "<H",
                "u32": "<I",
                "s32": "<i",
                "f32": "<f",
            }
            fmt = fmt_map.get(field.type)
            if fmt is None:
                return None

            size = struct.calcsize(fmt)
            if start + size > len(buf):
                return None

            value = struct.unpack_from(fmt, buf, start)[0]
            return int(value)

        diff = read_field("difficulty")
        # XP and Hacksilver are inventory-backed quantities. XP is the table
        # anchor row; Hacksilver may move between resource rows. Resolve both
        # by item ID so the header, Slot Manager, Dashboard, and Inventory stay
        # in sync.
        xp_dynamic = read_item_quantity(buf, slot_index, XP_ITEM_ID)
        xp = xp_dynamic if xp_dynamic is not None else read_field("kratos_xp")
        hs_dynamic = read_item_quantity(buf, slot_index, HACKSILVER_ITEM_ID)
        hs = hs_dynamic if hs_dynamic is not None else read_field("hacksilver")

        if diff is None or not (0 <= diff <= 3):
            diff = 0
        if xp is None:
            xp = 0
        if hs is None:
            hs = 0

        diff_names = {
            0: "Story",
            1: "Balanced",
            2: "Challenge",
            3: "God of War",
        }
        diff_name = diff_names.get(diff, "Story")

        return {
            "slot": int(slot_index),
            "difficulty": int(diff),
            "difficulty_name": diff_name,
            "xp": int(xp),
            "hacksilver": int(hs),
            "location": location,
            "last_played_raw": int(ts_raw),
            "last_played": dt_str,
        }

    # ------------------------------------------------------------------
    # Inventory
    # ------------------------------------------------------------------

    def _inventory_region(self) -> tuple[int, int]:
        """Return (start, end) of the active slot inventory table."""
        return gow2018_data.inventory_region_for_slot(len(self.raw), self.active_slot)

    def _load_inventory_from_binary(self) -> None:
        """
        Populate self.inventory_items from the raw buffer for the
        current active slot.
        """
        start, end = self._inventory_region()
        if end <= start or not gow2018_data.inventory_anchor_is_valid(self.raw, self.active_slot):
            self.inventory_items = {}
            return

        buf = self.raw
        items: Dict[int, Dict[str, Union[int, str]]] = {}

        row = 0
        pos = start
        while pos + 16 <= end:
            entry = buf[pos : pos + 16]

            item_id = entry[0:8].hex().upper()                  # 8 bytes
            qty = struct.unpack_from("<I", entry, 8)[0]          # 4 bytes

            # Last 4 bytes are usually flags/unknown; do not modify here.

            if item_id != "0000000000000000" or qty != 0:
                items[row] = {
                    "row": row,
                    "item_id": item_id,
                    "quantity": qty,
                    "offset": pos,
                }

            row += 1
            pos += 16

        self.inventory_items = items

    def _store_inventory_to_binary(self) -> None:
        # InventoryTab currently writes directly into save.raw; we keep
        # this method for future expansion.
        pass

    # ------------------------------------------------------------------
    # Armor stat helpers (Skiller markers)
    # ------------------------------------------------------------------

    def get_armor_stat_values(self, key: str) -> list[float]:
        """
        Scan the whole save for a given armor stat marker pair and return
        the float values found (as Python floats).

        This is a read-only version of boost_armor_stat() and is used by
        the Stats tab to display your *actual* armor stats.
        """
        if key not in ARMOR_STAT_MARKERS:
            return []

        marker1_hex, marker2_hex = ARMOR_STAT_MARKERS[key]
        m1 = bytes.fromhex(marker1_hex)
        m2 = bytes.fromhex(marker2_hex)

        buf = self.raw
        i = 0
        n = len(buf)
        values: list[float] = []

        while True:
            idx = buf.find(m1, i)
            if idx == -1 or idx + 12 > n:
                break

            # Expect [marker1][marker2][float]
            if buf[idx + 4 : idx + 8] == m2:
                float_pos = idx + 8
                if float_pos + 4 <= n:
                    val = struct.unpack_from("<f", buf, float_pos)[0]
                    values.append(val)

            i = idx + 4

        return values

    def boost_armor_stat(self, key: str, new_value: float) -> int:
        """
        Overwrite all occurrences of a given armor stat marker pair with
        new_value. Returns the number of writes performed.
        """
        if key not in ARMOR_STAT_MARKERS:
            return 0

        marker1_hex, marker2_hex = ARMOR_STAT_MARKERS[key]
        m1 = bytes.fromhex(marker1_hex)
        m2 = bytes.fromhex(marker2_hex)

        if isinstance(self.raw, bytes):
            self.raw = bytearray(self.raw)

        buf = self.raw
        i = 0
        n = len(buf)
        count = 0

        while True:
            idx = buf.find(m1, i)
            if idx == -1 or idx + 12 > n:
                break

            if buf[idx + 4 : idx + 8] == m2:
                float_pos = idx + 8
                if float_pos + 4 <= n:
                    struct.pack_into("<f", buf, float_pos, float(new_value))
                    count += 1

            i = idx + 4

        return count

    def boost_all_armor_stats(self, new_value: float) -> Dict[str, int]:
        """Overwrite every known armor stat marker pair with ``new_value``.

        Returns a per-stat patch count so the UI can report exactly what was
        changed and avoid marking the save dirty when no markers were found.
        """
        result: Dict[str, int] = {}
        for key in ARMOR_STAT_MARKERS.keys():
            result[key] = self.boost_armor_stat(key, new_value)
        return result

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_bytes(self) -> bytes:
        """Return the current raw buffer without implicit rewrites.

        UI tabs commit explicit edits into ``self.raw`` as the user stages them.
        Returning bytes here must be a no-op because some real saves contain
        values our current layout only partially understands; a simple Save or
        Save Preview should never normalize untouched bytes.
        """
        if isinstance(self.raw, bytearray):
            return bytes(self.raw)
        return self.raw

    def write_to_path(self, path: Optional[Path] = None) -> None:
        """
        Atomically write the edited save.

        If the target already exists, a timestamped .bak copy is created before
        replacement. This prevents a failed write from leaving a half-written
        memory.dat and gives the user an immediate rollback file.
        """
        if path is None:
            if self.path is None:
                raise ValueError("No path specified for SaveFile.write_to_path()")
            path = self.path

        path = Path(path)
        data = self.to_bytes()
        atomic_write_bytes(path, data, create_backup=True)
        self.path = path
