# app/core/save_file.py
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, Union
import struct
import datetime

from app.core import gow2018_data
from app.core.gow2018_layout import build_layout_for_slot, LayoutSpec, SlotField

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

# Relative offset from a slot's base pointer to the inventory table.
INVENTORY_TABLE_REL_OFFSET: int = gow2018_data.INVENTORY_TABLE_REL_OFFSET

# How many entries we expect in the inventory table for each slot.
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

    raw: bytes = b""
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
    def from_path(cls, path: Path, active_slot: int = 1) -> "SaveFile":
        raw = path.read_bytes()
        save = cls(raw=raw, path=path)

        save.active_slot = active_slot
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

        struct.pack_into(fmt, buf, start, value)

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

        try:
            self.kratos_xp = int(self._read_primitive(xp_field))
        except Exception:
            self.kratos_xp = 0

        try:
            self.hacksilver = int(self._read_primitive(hs_field))
        except Exception:
            self.hacksilver = 0

    def _store_core_stats_to_binary(self) -> None:
        """
        Write the current in-memory core stats for the active slot back
        into the raw buffer.
        """
        self._ensure_layout()
        if self.layout is None:
            return

        diff_field = self._get_field_def("difficulty")
        xp_field = self._get_field_def("kratos_xp")
        hs_field = self._get_field_def("hacksilver")

        # difficulty is always clamped into [0,3]
        if diff_field is not None:
            v = int(self.difficulty)
            if v < 0:
                v = 0
            if v > 3:
                v = 3
            self._write_primitive(diff_field, v)

        if xp_field is not None:
            self._write_primitive(xp_field, int(self.kratos_xp))

        if hs_field is not None:
            self._write_primitive(hs_field, int(self.hacksilver))

    def commit_core_stats(self) -> None:
        """
        Called by the Stats tab whenever the user edits difficulty/XP/HS.
        """
        self._store_core_stats_to_binary()

    # ------------------------------------------------------------------
    # Slot selection + summary
    # ------------------------------------------------------------------

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
        xp = read_field("kratos_xp")
        hs = read_field("hacksilver")

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
        """
        Return (start, end) of the inventory table for the active slot.
        """
        base_off = gow2018_data.resolve_slot_base_offset(self.active_slot)
        if base_off <= 0:
            return (0, 0)

        start = base_off + INVENTORY_TABLE_REL_OFFSET
        # Rough upper bound: fixed number of entries * 16 bytes per entry
        end = start + INVENTORY_ENTRY_COUNT * 16
        if end > len(self.raw):
            end = len(self.raw)
        return (start, end)

    def _load_inventory_from_binary(self) -> None:
        """
        Populate self.inventory_items from the raw buffer for the
        current active slot.
        """
        start, end = self._inventory_region()
        if end <= start:
            self.inventory_items = {}
            return

        buf = self.raw
        items: Dict[int, Dict[str, Union[int, str]]] = {}

        row = 0
        pos = start
        while pos + 16 <= end:
            entry = buf[pos : pos + 16]

            item_id = struct.unpack_from("<Q", entry, 0)[0]      # 8 bytes
            qty = struct.unpack_from("<I", entry, 8)[0]          # 4 bytes

            # Last 4 bytes are usually zero; we keep them as-is when writing.

            if item_id != 0 or qty != 0:
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

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_bytes(self) -> bytes:
        """Sync logical fields back into raw bytes and return buffer."""
        # Core stats for the active slot
        self._store_core_stats_to_binary()

        # InventoryTab currently writes directly into save.raw; if we ever
        # add a "global" inventory view, we'd push edits here.

        # Normalize to immutable bytes in case other code used a bytearray.
        if isinstance(self.raw, bytearray):
            return bytes(self.raw)
        return self.raw

    def write_to_path(self, path: Optional[Path] = None) -> None:
        if path is None:
            if self.path is None:
                raise ValueError("No path specified for SaveFile.write_to_path()")
            path = self.path
        data = self.to_bytes()
        path.write_bytes(data)
        self.path = path
