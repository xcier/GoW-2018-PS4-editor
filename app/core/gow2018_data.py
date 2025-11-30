# app/core/gow2018_data.py
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
import json

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

# app/core/gow2018_data.py -> app/core -> app -> resources/database
BASE_DIR = Path(__file__).resolve().parent.parent / "resources" / "database"

ITEMS_JSON = BASE_DIR / "gow2018_items.json"
SLOTS_JSON = BASE_DIR / "gow2018_slots.json"
CODES_JSON = BASE_DIR / "gow2018_codes.json"


def _load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Missing resource file: {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


_items_cache: Optional[Dict[str, Any]] = None
_slots_cache: Optional[Dict[str, Any]] = None
_codes_cache: Optional[Dict[str, Any]] = None


def _ensure_items_loaded() -> None:
    global _items_cache
    if _items_cache is None:
        _items_cache = _load_json(ITEMS_JSON)


def _ensure_slots_loaded() -> None:
    global _slots_cache
    if _slots_cache is None:
        _slots_cache = _load_json(SLOTS_JSON)


def _ensure_codes_loaded() -> None:
    global _codes_cache
    if _codes_cache is None:
        _codes_cache = _load_json(CODES_JSON)


# ---------------------------------------------------------------------------
# Items API (from ItemIDs sheet)
# ---------------------------------------------------------------------------

def get_all_items() -> List[Dict[str, Any]]:
    """
    Return a flat list of all item dicts.

    Each item dict looks like (from your JSON):
        {
            "slot_code": "0190",
            "id": "0084906486DF5D22",
            "file": "...",
            "name": "Reaver Belt Lv3",
            "type": "Armor"
        }
    """
    _ensure_items_loaded()
    return list(_items_cache["items"])  # type: ignore[index]


def get_items_by_id() -> Dict[str, Dict[str, Any]]:
    """
    Return a mapping from ID -> item dict.

    IDs are uppercase hex strings in the JSON.
    """
    _ensure_items_loaded()
    return dict(_items_cache["by_id"])  # type: ignore[index]


def get_all_types() -> List[str]:
    """Return all distinct Type values (Armor, Resources, etc.)."""
    _ensure_items_loaded()
    return sorted(_items_cache["by_type"].keys())  # type: ignore[index]


# ---------------------------------------------------------------------------
# Save slots API (from Save Slot Starting Points sheet)
# ---------------------------------------------------------------------------

def get_save_slots() -> List[Dict[str, Any]]:
    """
    Return a list of slot descriptors.

    JSON structure (from your CSV) is:
        {
          "slots": [
            {
              "slot": 1,
              "quick_pointer": "90000000 00000200",
              "alt_pointer":   "95000000 00001040"
            },
            ...
          ]
        }
    """
    _ensure_slots_loaded()
    return list(_slots_cache["slots"])  # type: ignore[index]


def get_save_slot(slot_number: int) -> Optional[Dict[str, Any]]:
    """Return the dict for Slot N, or None if not present."""
    for slot in get_save_slots():
        if slot.get("slot") == slot_number:
            return slot
    return None


# ---------------------------------------------------------------------------
# Codes API (from Codes sheet)
# ---------------------------------------------------------------------------

def get_code_sections() -> List[Dict[str, Any]]:
    """
    Return list of code sections from gow2018_codes.json.
    """
    _ensure_codes_loaded()
    return list(_codes_cache["sections"])  # type: ignore[index]


def find_code_section(name_fragment: str) -> List[Dict[str, Any]]:
    """Case-insensitive fuzzy find on section.name."""
    frag = name_fragment.lower()
    return [s for s in get_code_sections() if frag in s.get("name", "").lower()]


# ---------------------------------------------------------------------------
# Slot base offset helpers
# ---------------------------------------------------------------------------

def parse_quick_pointer_to_address(quick_pointer: str) -> int:
    """
    Parse the SW Quick Mode pointer and return the 32-bit address.

    Example: "90000000 00000200" -> 0x90000000 (first token).
    We mostly use alt_pointer for file offsets; this is a fallback.
    """
    if not quick_pointer:
        raise ValueError("Empty quick_pointer")
    first_token = str(quick_pointer).split()[0]
    return int(first_token, 16)


def resolve_slot_base_offset(slot_number: int) -> int:
    """
    Return the *file offset* of the start of Slot N's data region.

    We prefer the 'alt_pointer' (from your sheet's
    “Alternative Slot format \"Actual Data\"”), which looks like:

        "95000000 00001040"

    We treat the second token ("00001040") as the file offset in memory.dat.
    If that’s missing, we fall back to the second token of quick_pointer.
    """
    slot = get_save_slot(slot_number)
    if not slot:
        return 0

    # 1) Prefer alt_pointer, e.g. "95000000 00001040"
    alt = slot.get("alt_pointer")
    if alt:
        try:
            parts = str(alt).split()
            if len(parts) >= 2:
                return int(parts[1], 16)
        except Exception:
            pass

    # 2) Fallback: quick_pointer second token, e.g. "90000000 00000200"
    quick = slot.get("quick_pointer")
    if quick:
        try:
            parts = str(quick).split()
            if len(parts) >= 2:
                return int(parts[1], 16)
        except Exception:
            pass

    # 3) Last resort: nothing
    return 0
