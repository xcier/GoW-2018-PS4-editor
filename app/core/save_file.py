# app/core/save_file.py
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, Union
import struct

from app.core import gow2018_data
from app.core.gow2018_layout import build_layout_for_slot, LayoutSpec, SlotField

Number = Union[int, float]


# Markers lifted from your Save Wizard cheats.
# Each stat appears as:
#   [marker1][marker2][float value][...]
#
# We overwrite the float value with 99.0f.
ARMOR_STAT_MARKERS = {
    "defense": ("0B72D37F", "6DC3F0F0"),
    "vitality": ("CBC51FB7", "7C16F8F3"),
    "luck": ("93E62C7A", "854C0000"),
    "strength": ("7A00D0F0", "1CCEAB3A"),
    "runic": ("48B6FD1A", "C0CB4E01"),
    "cooldown": ("57B8D16A", "F17D1E01"),
}


@dataclass
class SaveFile:
    """
    High-level view of a GoW 2018 save (single memory.dat).

    - active_slot: which slot we consider "main" for core stats
    - layout: offsets for:
        * difficulty  (0..3)
        * kratos_xp   (EconomyXP)
        * hacksilver
    - armor stat cheats: scan for hashed markers and overwrite the
      following float with 99.0.
    """

    raw: bytes = b""
    path: Optional[Path] = None

    active_slot: int = 1
    layout: Optional[LayoutSpec] = None

    difficulty: int = 0       # 0=Story,1=Balanced,2=Challenge,3=GoW
    kratos_xp: int = 0
    hacksilver: int = 0

    # inventory data placeholder
    inventory_items: Dict[str, int] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def from_path(cls, path: Path) -> "SaveFile":
        raw = path.read_bytes()
        save = cls(raw=raw, path=path)

        save._init_layout()
        save._load_core_stats_from_binary()
        save._load_inventory_from_binary()

        return save

    # ------------------------------------------------------------------
    # Layout helpers
    # ------------------------------------------------------------------

    def _init_layout(self) -> None:
        base_off = gow2018_data.resolve_slot_base_offset(self.active_slot)
        self.layout = build_layout_for_slot(self.active_slot, base_off)

    def _ensure_layout(self) -> None:
        if self.layout is None:
            self._init_layout()

    # ------------------------------------------------------------------
    # Primitive read / write
    # ------------------------------------------------------------------

    def _read_primitive(self, field: SlotField) -> Number:
        self._ensure_layout()
        assert self.layout is not None

        base = self.layout.base_offset
        start = base + field.offset
        buf = self.raw

        if start < 0 or start >= len(buf):
            return 0

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
            return 0

        chunk = buf[start:start + size]
        return struct.unpack(fmt, chunk)[0]

    def _write_primitive(self, field: SlotField, value: Number) -> None:
        self._ensure_layout()
        assert self.layout is not None

        base = self.layout.base_offset
        start = base + field.offset
        buf = bytearray(self.raw)

        fmt_map = {
            "u8": "<B",
            "u16": "<H",
            "u32": "<I",
            "s32": "<i",
            "f32": "<f",
        }
        fmt = fmt_map[field.type]
        size = struct.calcsize(fmt)
        if start < 0 or start + size > len(buf):
            return

        struct.pack_into(fmt, buf, start, value)
        self.raw = bytes(buf)

    def _get_field_def(self, name: str) -> Optional[SlotField]:
        self._ensure_layout()
        assert self.layout is not None
        return self.layout.fields.get(name)

    # ------------------------------------------------------------------
    # Core stats sync
    # ------------------------------------------------------------------

    def _load_core_stats_from_binary(self) -> None:
        """Read difficulty / XP / Hacksilver based on the slot layout."""
        diff_field = self._get_field_def("difficulty")
        xp_field = self._get_field_def("kratos_xp")
        hs_field = self._get_field_def("hacksilver")

        if diff_field:
            raw_val = int(self._read_primitive(diff_field))
            if 0 <= raw_val <= 3:
                self.difficulty = raw_val
            else:
                self.difficulty = 0

        if xp_field:
            self.kratos_xp = int(self._read_primitive(xp_field))

        if hs_field:
            self.hacksilver = int(self._read_primitive(hs_field))

    def _store_core_stats_to_binary(self) -> None:
        diff_field = self._get_field_def("difficulty")
        xp_field = self._get_field_def("kratos_xp")
        hs_field = self._get_field_def("hacksilver")

        if diff_field:
            v = int(self.difficulty)
            if v < 0:
                v = 0
            if v > 3:
                v = 3
            self._write_primitive(diff_field, v)

        if xp_field:
            self._write_primitive(xp_field, int(self.kratos_xp))

        if hs_field:
            self._write_primitive(hs_field, int(self.hacksilver))

    # ------------------------------------------------------------------
    # Inventory hooks (stub)
    # ------------------------------------------------------------------

    def _load_inventory_from_binary(self) -> None:
        self.inventory_items = {}

    def _store_inventory_to_binary(self) -> None:
        # TODO: hook InventoryTab writes back into raw bytes if needed.
        pass

    # ------------------------------------------------------------------
    # Armor stat "cheats" (use Skiller's markers)
    # ------------------------------------------------------------------

    def boost_armor_stat(self, key: str, value: float = 99.0) -> int:
        """
        Find all armor stat entries matching the given key
        ('defense', 'vitality', 'luck', 'strength', 'runic', 'cooldown')
        and set their value float to 'value'.

        Returns number of patches applied.
        """
        if key not in ARMOR_STAT_MARKERS:
            return 0

        marker1_hex, marker2_hex = ARMOR_STAT_MARKERS[key]
        m1 = bytes.fromhex(marker1_hex)
        m2 = bytes.fromhex(marker2_hex)

        buf = bytearray(self.raw)
        i = 0
        changed = 0
        val_bytes = struct.pack("<f", float(value))  # 99.0 -> 0000C642 (little endian)

        n = len(buf)
        while True:
            idx = buf.find(m1, i)
            if idx == -1 or idx + 12 > n:
                break
            # Expect [marker1][marker2][float]
            if buf[idx + 4:idx + 8] == m2:
                val_off = idx + 8
                if val_off + 4 <= n:
                    buf[val_off:val_off + 4] = val_bytes
                    changed += 1
            i = idx + 4

        if changed:
            self.raw = bytes(buf)

        return changed

    def boost_all_armor_stats(self, value: float = 99.0) -> Dict[str, int]:
        """
        Convenience: apply boost_armor_stat for all known stats.

        Returns dict: {stat_name: patches_applied}
        """
        result: Dict[str, int] = {}
        for key in ARMOR_STAT_MARKERS.keys():
            result[key] = self.boost_armor_stat(key, value=value)
        return result

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def to_bytes(self) -> bytes:
        """Sync logical fields + cheats back into raw bytes and return buffer."""
        self._store_core_stats_to_binary()
        self._store_inventory_to_binary()
        return self.raw

    def write_to_path(self, path: Optional[Path] = None) -> None:
        if path is None:
            if self.path is None:
                raise ValueError("No path specified for SaveFile.write_to_path()")
            path = self.path
        data = self.to_bytes()
        path.write_bytes(data)
        self.path = path
