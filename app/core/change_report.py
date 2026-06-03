from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from app.core import gow2018_data
from app.core.inventory_model import read_inventory_rows
from app.core.save_file import SaveFile


@dataclass(frozen=True)
class ByteRangeDiff:
    start: int
    end: int
    before_hex: str
    after_hex: str


@dataclass
class ChangeReport:
    lines: list[str] = field(default_factory=list)
    byte_ranges: list[ByteRangeDiff] = field(default_factory=list)
    omitted_byte_ranges: int = 0

    @property
    def has_changes(self) -> bool:
        return bool(self.lines or self.byte_ranges or self.omitted_byte_ranges)

    def to_text(self) -> str:
        if not self.has_changes:
            return "No byte changes detected."
        out: list[str] = []
        if self.lines:
            out.extend(self.lines)
        if self.byte_ranges:
            if out:
                out.append("")
            out.append("Raw byte ranges changed:")
            for diff in self.byte_ranges:
                out.append(
                    f"  0x{diff.start:08X}-0x{diff.end:08X}: "
                    f"{diff.before_hex}  →  {diff.after_hex}"
                )
            if self.omitted_byte_ranges:
                out.append(f"  … {self.omitted_byte_ranges} more changed range(s) not shown")
        return "\n".join(out)


def _as_bytes(data: bytes | bytearray | memoryview | None) -> bytes:
    if data is None:
        return b""
    return bytes(data)


def _fmt_int(value: object) -> str:
    try:
        return f"{int(value):,}"
    except Exception:
        return str(value)


def _safe_summary(raw: bytes, slot: int) -> Optional[dict]:
    try:
        return SaveFile(raw=raw).summarize_slot(slot)
    except Exception:
        return None


def _slot_is_active(summary: Optional[Mapping[str, object]]) -> bool:
    if not summary:
        return False
    try:
        if int(summary.get("last_played_raw", 0) or 0) > 0:
            return True
        if int(summary.get("xp", 0) or 0) > 0 or int(summary.get("hacksilver", 0) or 0) > 0:
            return True
    except Exception:
        pass
    return bool(str(summary.get("location", "") or "").strip())


def _row_label(row: Mapping[str, object]) -> str:
    name = str(row.get("name") or "").strip()
    item_id = str(row.get("id") or "").strip()
    type_text = str(row.get("type") or "").strip()
    if name:
        label = name
    elif item_id:
        label = f"Unknown {item_id}"
    else:
        label = "Unknown item"
    if type_text and type_text.lower() not in {"unknown", "?"}:
        label += f" ({type_text})"
    return label


def _inventory_rows_by_offset(raw: bytes, slot: int) -> Dict[int, Mapping[str, object]]:
    if not gow2018_data.inventory_anchor_is_valid(raw, slot):
        return {}
    snapshot = read_inventory_rows(raw, slot, gow2018_data.get_items_by_id())
    rows: Dict[int, Mapping[str, object]] = {}
    for row in snapshot.items:
        try:
            rows[int(row.get("offset", -1))] = row
        except Exception:
            continue
    return rows


def _short_hex(data: bytes, max_len: int = 12) -> str:
    if len(data) <= max_len:
        return data.hex(" ").upper()
    return data[:max_len].hex(" ").upper() + " …"


def _diff_byte_ranges(before: bytes, after: bytes, *, limit: int = 16) -> tuple[list[ByteRangeDiff], int]:
    max_len = max(len(before), len(after))
    ranges: list[tuple[int, int]] = []
    i = 0
    while i < max_len:
        b = before[i] if i < len(before) else None
        a = after[i] if i < len(after) else None
        if b == a:
            i += 1
            continue
        start = i
        i += 1
        while i < max_len:
            b = before[i] if i < len(before) else None
            a = after[i] if i < len(after) else None
            if b == a:
                break
            i += 1
        ranges.append((start, i))
    shown = []
    for start, end in ranges[:limit]:
        shown.append(
            ByteRangeDiff(
                start=start,
                end=end,
                before_hex=_short_hex(before[start:min(end, len(before))]),
                after_hex=_short_hex(after[start:min(end, len(after))]),
            )
        )
    return shown, max(0, len(ranges) - len(shown))


def build_change_report(
    before: bytes | bytearray | memoryview | None,
    after: bytes | bytearray | memoryview | None,
    *,
    active_slot: Optional[int] = None,
    max_slots: int = 20,
    max_inventory_lines: int = 24,
    max_byte_ranges: int = 16,
) -> ChangeReport:
    """Build a human-readable report of staged save changes."""
    before_b = _as_bytes(before)
    after_b = _as_bytes(after)
    report = ChangeReport()

    if before_b == after_b:
        return report

    if len(before_b) != len(after_b):
        report.lines.append(f"File size: {len(before_b):,} bytes → {len(after_b):,} bytes")

    # Core slot stat summary.
    for slot in range(1, max_slots + 1):
        old = _safe_summary(before_b, slot)
        new = _safe_summary(after_b, slot)
        if not _slot_is_active(old) and not _slot_is_active(new):
            continue
        changes: list[str] = []
        if old and new:
            for key, label in (("difficulty_name", "Difficulty"), ("xp", "Kratos XP"), ("hacksilver", "Hacksilver")):
                if old.get(key) != new.get(key):
                    old_v = old.get(key)
                    new_v = new.get(key)
                    if key in {"xp", "hacksilver"}:
                        old_v = _fmt_int(old_v)
                        new_v = _fmt_int(new_v)
                    changes.append(f"{label}: {old_v} → {new_v}")
            if changes:
                active = " active" if active_slot == slot else ""
                report.lines.append(f"Slot {slot}{active}: " + "; ".join(changes))
        elif old != new:
            report.lines.append(f"Slot {slot}: summary changed")

    # Inventory/resource changes are tracked by exact row offset so duplicates
    # and special records are preserved in the report just like the writer.
    inv_lines: list[str] = []
    for slot in range(1, max_slots + 1):
        before_rows = _inventory_rows_by_offset(before_b, slot)
        after_rows = _inventory_rows_by_offset(after_b, slot)
        if not before_rows and not after_rows:
            continue
        for offset in sorted(set(before_rows) | set(after_rows)):
            old = before_rows.get(offset)
            new = after_rows.get(offset)
            if old == new:
                continue
            prefix = f"Slot {slot} inventory @ 0x{offset:08X}: "
            if old is None and new is not None:
                inv_lines.append(prefix + f"added {_row_label(new)} ×{_fmt_int(new.get('qty', 0))}")
            elif old is not None and new is None:
                inv_lines.append(prefix + f"removed {_row_label(old)} ×{_fmt_int(old.get('qty', 0))}")
            elif old is not None and new is not None:
                if old.get("id") != new.get("id"):
                    inv_lines.append(prefix + f"{_row_label(old)} → {_row_label(new)}")
                elif old.get("qty") != new.get("qty"):
                    inv_lines.append(prefix + f"{_row_label(new)} quantity {_fmt_int(old.get('qty', 0))} → {_fmt_int(new.get('qty', 0))}")
                else:
                    inv_lines.append(prefix + "metadata changed")
    if inv_lines:
        report.lines.append("Inventory/resource changes:")
        report.lines.extend(f"  {line}" for line in inv_lines[:max_inventory_lines])
        if len(inv_lines) > max_inventory_lines:
            report.lines.append(f"  … {len(inv_lines) - max_inventory_lines} more inventory change(s) not shown")

    report.byte_ranges, report.omitted_byte_ranges = _diff_byte_ranges(before_b, after_b, limit=max_byte_ranges)
    return report
