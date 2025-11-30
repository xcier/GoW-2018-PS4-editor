from __future__ import annotations
from pathlib import Path
import struct
import json

# ---------------------------------------------------------------------
# CONFIG – EDIT THESE BEFORE RUNNING
# ---------------------------------------------------------------------

# Decrypted save file
SAVE_PATH = Path(r"E:\repos\GoW 2018\memory.dat")

# Slot layout JSON (from your SW sheet -> gow2018_slots.json)
SLOTS_JSON = Path(r"E:\repos\GoW 2018\app\resources\database\gow2018_slots.json")

# Which slot you want to scan (1–11 in your sheet)
SLOT_INDEX = 1

# Value you are hunting for (int or float depending on what you’re looking for)
#   Example 1: if your Hacksilver is 123456, set TARGET_VALUE_INT = 123456
#   Example 2: if a stat is 99.0f, leave TARGET_VALUE_INT=None and
#              set TARGET_VALUE_FLOAT = 99.0
TARGET_VALUE_INT: int | None = None
TARGET_VALUE_FLOAT: float | None = None  # e.g. 99.0

# How far around the slot base to scan
SEARCH_RADIUS = 0x8000   # 32 KB either side


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def load_slot_base(slot_index: int) -> int:
    with SLOTS_JSON.open("r", encoding="utf-8") as f:
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
    raise SystemExit(f"Slot {slot_index} not found in gow2018_slots.json")


def scan_for_pattern(buf: bytes, base: int, pattern: bytes) -> None:
    window_start = max(0, base - SEARCH_RADIUS)
    window_end = min(len(buf), base + SEARCH_RADIUS)
    window = buf[window_start:window_end]

    idx = window.find(pattern)
    hits = 0
    while idx != -1:
        file_off = window_start + idx
        rel = file_off - base
        print(f"  hit at file 0x{file_off:08X} (rel 0x{rel:08X})")
        hits += 1
        idx = window.find(pattern, idx + 1)

    if hits == 0:
        print("  no matches in this window")


def main() -> None:
    if TARGET_VALUE_INT is None and TARGET_VALUE_FLOAT is None:
        raise SystemExit("Set TARGET_VALUE_INT or TARGET_VALUE_FLOAT at the top of the file.")

    data = SAVE_PATH.read_bytes()
    base = load_slot_base(SLOT_INDEX)
    print(f"Slot {SLOT_INDEX} base offset: 0x{base:08X}")

    # u32 search
    if TARGET_VALUE_INT is not None:
        pat = struct.pack("<I", TARGET_VALUE_INT & 0xFFFFFFFF)
        print(f"\nSearching for u32 {TARGET_VALUE_INT} (pattern {pat.hex()})...")
        scan_for_pattern(data, base, pat)

    # float search
    if TARGET_VALUE_FLOAT is not None:
        pat = struct.pack("<f", float(TARGET_VALUE_FLOAT))
        print(f"\nSearching for f32 {TARGET_VALUE_FLOAT} (pattern {pat.hex()})...")
        scan_for_pattern(data, base, pat)


if __name__ == "__main__":
    main()
