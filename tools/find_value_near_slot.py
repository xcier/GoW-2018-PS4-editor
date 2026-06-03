from __future__ import annotations

"""Search for integer/float values near a GoW 2018 slot base.

Example:
    python tools/find_value_near_slot.py path/to/memory.dat --slot 7 --u32 178808
    python tools/find_value_near_slot.py path/to/memory.dat --slot 7 --f32 99.0 --radius 0x8000
"""

import argparse
import json
import struct
from pathlib import Path

DEFAULT_SLOTS_JSON = Path(__file__).resolve().parents[1] / "app" / "resources" / "database" / "gow2018_slots.json"


def parse_int(value: str) -> int:
    return int(value, 0)


def load_slot_base(slots_json: Path, slot_index: int) -> int:
    with slots_json.open("r", encoding="utf-8") as f:
        slots = json.load(f)["slots"]
    for slot in slots:
        if slot.get("slot") == slot_index:
            alt = slot.get("alt_pointer")
            if not alt:
                raise SystemExit(f"No alt_pointer for slot {slot_index}")
            parts = str(alt).split()
            if len(parts) < 2:
                raise SystemExit(f"Bad alt_pointer for slot {slot_index}: {alt}")
            return int(parts[1], 16)
    raise SystemExit(f"Slot {slot_index} not found in {slots_json}")


def scan_for_pattern(buf: bytes, base: int, pattern: bytes, radius: int) -> list[int]:
    window_start = max(0, base - radius)
    window_end = min(len(buf), base + radius)
    window = buf[window_start:window_end]
    hits: list[int] = []
    idx = window.find(pattern)
    while idx != -1:
        hits.append(window_start + idx)
        idx = window.find(pattern, idx + 1)
    return hits


def main() -> None:
    parser = argparse.ArgumentParser(description="Search for u32/f32 values near a GoW 2018 slot base.")
    parser.add_argument("save", type=Path, help="Path to decrypted memory.dat")
    parser.add_argument("--slot", type=int, required=True, help="Physical slot number to scan")
    parser.add_argument("--u32", type=parse_int, help="Unsigned 32-bit integer to search for, decimal or 0x hex")
    parser.add_argument("--f32", type=float, help="32-bit float value to search for")
    parser.add_argument("--radius", type=parse_int, default=0x8000, help="Bytes to scan before/after slot base")
    parser.add_argument("--slots-json", type=Path, default=DEFAULT_SLOTS_JSON, help="Path to gow2018_slots.json")
    args = parser.parse_args()

    if args.u32 is None and args.f32 is None:
        raise SystemExit("Provide --u32 and/or --f32.")

    data = args.save.read_bytes()
    base = load_slot_base(args.slots_json, args.slot)
    print(f"Slot {args.slot} base offset: 0x{base:08X}")

    searches: list[tuple[str, bytes]] = []
    if args.u32 is not None:
        searches.append((f"u32 {args.u32}", struct.pack("<I", args.u32 & 0xFFFFFFFF)))
    if args.f32 is not None:
        searches.append((f"f32 {args.f32}", struct.pack("<f", float(args.f32))))

    for label, pattern in searches:
        print(f"\nSearching for {label} ({pattern.hex()})...")
        hits = scan_for_pattern(data, base, pattern, args.radius)
        if not hits:
            print("  no matches")
            continue
        for off in hits:
            rel = off - base
            sign = "-" if rel < 0 else "+"
            print(f"  hit at file 0x{off:08X} (slot base {sign}0x{abs(rel):X})")


if __name__ == "__main__":
    main()
