#!/usr/bin/env python3
"""Validate a decrypted GoW 2018 PS4 memory.dat against this editor's layout.

Usage:
    python tools/validate_memory_dat.py /path/to/memory.dat
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core import gow2018_data  # noqa: E402
from app.core.inventory_model import commit_inventory_rows, read_inventory_rows  # noqa: E402
from app.core.save_file import SaveFile  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate GoW 2018 memory.dat layout and safe no-op writes.")
    parser.add_argument("memory_dat", type=Path)
    args = parser.parse_args()

    path = args.memory_dat
    raw = path.read_bytes()
    print(f"File: {path}")
    print(f"Size: {len(raw):,} bytes")
    print(f"SHA256: {hashlib.sha256(raw).hexdigest()}")

    save = SaveFile.from_path(path)
    print(f"Detected newest active slot: {save.active_slot}")
    roundtrip = save.to_bytes()
    print(f"No-edit core roundtrip identical: {roundtrip == raw}")

    bad = 0
    for slot in range(1, 21):
        summary = save.summarize_slot(slot)
        start, end = gow2018_data.inventory_region_for_slot(len(raw), slot)
        anchor = gow2018_data.inventory_anchor_is_valid(raw, slot)
        snapshot = read_inventory_rows(raw, slot)
        noop_ok = "n/a"
        if anchor:
            try:
                result = commit_inventory_rows(raw, slot, snapshot.items, snapshot.write_info, snapshot.free_positions)
                noop_ok = str(result.raw == raw)
                if result.raw != raw:
                    bad += 1
            except Exception as exc:  # noqa: BLE001
                noop_ok = f"ERROR: {exc}"
                bad += 1

        if summary:
            loc = str(summary.get("location", ""))[:48]
            print(
                f"Slot {slot:02d}: base=0x{gow2018_data.resolve_slot_base_offset(slot):08X} "
                f"diff={summary.get('difficulty')} xp={summary.get('xp')} hs={summary.get('hacksilver')} "
                f"table=0x{start:08X}-0x{snapshot.end:08X} fixed_end=0x{end:08X} anchor={anchor} "
                f"rows={len(snapshot.items)} free={len(snapshot.free_positions)} noop={noop_ok} "
                f"loc={loc!r}"
            )
        else:
            print(f"Slot {slot:02d}: no summary")

    if bad:
        print(f"Validation failed: {bad} no-op inventory commits changed data or errored.")
        return 1
    print("Validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
