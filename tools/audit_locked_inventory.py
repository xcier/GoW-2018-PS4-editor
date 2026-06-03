#!/usr/bin/env python3
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core import gow2018_data  # noqa: E402
from app.core.inventory_model import CORE_QUANTITY_ITEM_IDS, read_inventory_rows  # noqa: E402
from app.core.save_file import SaveFile  # noqa: E402


def audit(path: Path) -> str:
    save = SaveFile.from_path(path)
    snapshot = read_inventory_rows(save.raw, save.active_slot, gow2018_data.get_items_by_id())
    counts = Counter()
    samples: dict[str, list[str]] = {"core": [], "locked": [], "editable": []}

    for row in snapshot.items:
        item_id = str(row.get("id") or "")
        label = f"{row.get('name')} | {row.get('type')} | qty {int(row.get('qty', 0) or 0):,} | {item_id} | row {row.get('row')}"
        if item_id in CORE_QUANTITY_ITEM_IDS:
            counts["synced_core"] += 1
            if len(samples["core"]) < 8:
                samples["core"].append(label)
        elif row.get("protected"):
            counts["locked_system"] += 1
            if len(samples["locked"]) < 20:
                samples["locked"].append(label)
        else:
            counts["editable"] += 1
            if len(samples["editable"]) < 12:
                samples["editable"].append(label)

    lines = [
        f"File: {path}",
        f"Active slot: {save.active_slot}",
        f"XP: {save.kratos_xp:,}",
        f"Hacksilver: {save.hacksilver:,}",
        f"Inventory anchor valid: {snapshot.anchor_valid}",
        f"Rows: {len(snapshot.items):,}",
        f"Editable rows: {counts['editable']:,}",
        f"Synced core rows: {counts['synced_core']:,}",
        f"Locked system/unknown rows: {counts['locked_system']:,}",
        f"Free records: {len(snapshot.free_positions):,}",
        "",
        "Synced core rows (editable quantity, not removable):",
        *(f"  - {line}" for line in samples["core"]),
        "",
        "Editable examples:",
        *(f"  - {line}" for line in samples["editable"]),
        "",
        "Locked examples:",
        *(f"  - {line}" for line in samples["locked"]),
    ]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("Usage: audit_locked_inventory.py <memory.dat> [...]")
        return 2
    for arg in argv[1:]:
        print(audit(Path(arg)))
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
