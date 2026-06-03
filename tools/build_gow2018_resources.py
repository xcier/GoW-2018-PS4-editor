from __future__ import annotations

"""Utility script to convert Save Wizard CSVs into JSON resources."""

from pathlib import Path
from typing import Dict, Any

import json
import sys
import math
import re

import pandas as pd



ROOT = Path(__file__).resolve().parent.parent  # project root
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.gow2018_data import normalize_items_database
RAW_DIR = ROOT / "data" / "raw"
OUT_DIR = ROOT / "app" / "resources" / "database"

ITEMS_CSV = RAW_DIR / "SW - God Of War _ IDs - ItemIDS.csv"
SLOTS_CSV = RAW_DIR / "SW - God Of War _ IDs - Save Slot Starting Points.csv"
CODES_CSV = RAW_DIR / "SW - God Of War _ IDs - Codes.csv"


def build_items(df: pd.DataFrame) -> Dict[str, Any]:
    items = []
    col_slot = "Slot"
    col_id = "IDs"
    col_file = "resources.dcb (File Name)"
    col_name = "Clean Name"
    col_type = "Type"

    for _, row in df.iterrows():
        slot_raw = str(row[col_slot]).strip() if col_slot in df.columns and not pd.isna(row[col_slot]) else None
        item = {
            "slot_code": slot_raw,
            "id": str(row[col_id]).strip() if not pd.isna(row[col_id]) else None,
            "file": str(row[col_file]).strip() if col_file in df.columns and not pd.isna(row[col_file]) else None,
            "name": str(row[col_name]).strip() if not pd.isna(row[col_name]) else None,
            "type": str(row[col_type]).strip() if not pd.isna(row[col_type]) else None,
        }
        items.append(item)

    by_id = {it["id"]: it for it in items if it.get("id")}
    by_name: Dict[str, list[str]] = {}
    for it in items:
        nm = it.get("name")
        if not nm:
            continue
        by_name.setdefault(nm, []).append(it["id"])

    by_type: Dict[str, list[str]] = {}
    for it in items:
        tp = it.get("type")
        iid = it.get("id")
        if not tp or not iid:
            continue
        by_type.setdefault(tp, []).append(iid)

    return normalize_items_database({
        "items": items,
        "by_id": by_id,
        "by_name": by_name,
        "by_type": by_type,
    })


def _cell_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if math.isnan(value):  # type: ignore[arg-type]
            return ""
    except Exception:
        pass
    return str(value).strip()


def build_slots(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Build physical save-data slots from every 95000000 actual-data pointer.

    The spreadsheet has a quick-mode column and an "Alternative Slot format
    Actual Data" column. Older builds attached only some 95000000 rows to the
    visible slot labels, skipping every other actual-data base and causing the
    editor to write to the wrong save block. For direct memory.dat editing, the
    correct source of truth is the ordered list of 95000000 bases.
    """
    col0 = "Set Starting Points for Game Slot GOW"
    col2 = 'Alternative Slot format "Actual Data" not always in correct order '

    slots = []
    physical_index = 1

    for idx, row in df.iterrows():
        alt = _cell_text(row[col2]) if col2 in df.columns else ""
        if not alt.startswith("95000000"):
            continue

        quick = _cell_text(row[col0]) if col0 in df.columns else ""
        if not quick.startswith("90000000"):
            quick = None

        slots.append(
            {
                "slot": physical_index,
                "quick_pointer": quick,
                "alt_pointer": alt,
                "source_row": int(idx) + 2,  # +2 accounts for CSV header + 1-based sheet rows
            }
        )
        physical_index += 1

    return {"slots": slots}


def looks_like_code(s: str) -> bool:
    if not s or not isinstance(s, str):
        return False
    s = s.strip()
    if " " not in s:
        return False
    head = s.split()[0]
    return bool(re.fullmatch(r"[0-9A-F]{8}", head))


def build_codes(df: pd.DataFrame) -> Dict[str, Any]:
    col0 = "Jimmy the Burger Wizard"
    col1 = "Change Difficulty"
    col3 = "Unnamed: 3"
    col4 = "Unnamed: 4"

    sections = []
    current = {"name": "Change Difficulty", "author": None, "lines": []}
    sections.append(current)

    for idx, row in df.iterrows():
        a = row[col0] if col0 in df.columns else None
        b = row[col1] if col1 in df.columns else None
        d = row[col3] if col3 in df.columns else None
        e = row[col4] if col4 in df.columns else None

        a = None if (isinstance(a, float) and math.isnan(a)) else a
        b = None if (isinstance(b, float) and math.isnan(b)) else b
        d = None if (isinstance(d, float) and math.isnan(d)) else d
        e = None if (isinstance(e, float) and math.isnan(e)) else e

        if idx <= 4:
            if b and looks_like_code(str(b)):
                current["lines"].append({"code": str(b), "note": d})
            continue

        if a == "Skiller#4741" and b and not looks_like_code(str(b)):
            current = {"name": str(b), "author": "Skiller#4741", "lines": []}
            sections.append(current)
            continue

        if b and looks_like_code(str(b)):
            current["lines"].append({"code": str(b), "note": d})

        if e and looks_like_code(str(e)):
            current["lines"].append({"code": str(e), "note": d})

    return {"sections": sections}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    items_df = pd.read_csv(ITEMS_CSV)
    slots_df = pd.read_csv(SLOTS_CSV)
    codes_df = pd.read_csv(CODES_CSV)

    items_json = build_items(items_df)
    slots_json = build_slots(slots_df)
    codes_json = build_codes(codes_df)

    (OUT_DIR / "gow2018_items.json").write_text(
        json.dumps(items_json, indent=2), encoding="utf-8"
    )
    (OUT_DIR / "gow2018_slots.json").write_text(
        json.dumps(slots_json, indent=2), encoding="utf-8"
    )
    (OUT_DIR / "gow2018_codes.json").write_text(
        json.dumps(codes_json, indent=2), encoding="utf-8"
    )

    print("Wrote:")
    print(" -", OUT_DIR / "gow2018_items.json")
    print(" -", OUT_DIR / "gow2018_slots.json")
    print(" -", OUT_DIR / "gow2018_codes.json")


if __name__ == "__main__":
    main()
