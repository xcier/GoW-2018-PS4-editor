# app/core/gow2018_data.py
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
import json

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent / "resources" / "database"

ITEMS_JSON = BASE_DIR / "gow2018_items.json"
SLOTS_JSON = BASE_DIR / "gow2018_slots.json"
CODES_JSON = BASE_DIR / "gow2018_codes.json"

# ---------------------------------------------------------------------------
# Internal caches
# ---------------------------------------------------------------------------

_items_cache: Optional[Dict[str, Any]] = None
_slots_cache: Optional[Dict[str, Any]] = None
_codes_cache: Optional[Dict[str, Any]] = None

def _load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Missing resource file: {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

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
    _ensure_items_loaded()
    return list(_items_cache["items"])  # type: ignore[index]

def get_items_by_id() -> Dict[str, Dict[str, Any]]:
    _ensure_items_loaded()
    return dict(_items_cache["by_id"])  # type: ignore[index]

def get_all_types() -> List[str]:
    _ensure_items_loaded()
    return sorted(_items_cache["by_type"].keys())  # type: ignore[index]

# ---------------------------------------------------------------------------
# Save slots API (from Save Slot Starting Points sheet)
# ---------------------------------------------------------------------------

def get_save_slots() -> List[Dict[str, Any]]:
    _ensure_slots_loaded()
    return list(_slots_cache["slots"])  # type: ignore[index]

def get_save_slot(slot_number: int) -> Optional[Dict[str, Any]]:
    for slot in get_save_slots():
        try:
            if int(slot.get("slot", -1)) == slot_number:
                return slot
        except Exception:
            continue
    return None

# ---------------------------------------------------------------------------
# Codes API (from Codes sheet)
# ---------------------------------------------------------------------------

def get_code_sections() -> List[Dict[str, Any]]:
    _ensure_codes_loaded()
    return list(_codes_cache["sections"])  # type: ignore[index]

def find_code_section(name_fragment: str) -> List[Dict[str, Any]]:
    frag = name_fragment.lower()
    return [s for s in get_code_sections() if frag in s.get("name", "").lower()]

# ---------------------------------------------------------------------------
# Slot base offset helpers
# ---------------------------------------------------------------------------

def parse_quick_pointer_to_address(quick_pointer: str) -> int:
    """
    Parse a Save Wizard Quick Mode pointer and return the 32-bit address
    stored in the second token (the pointer offset inside the save file).
    This is *not* the slot base offset — only useful if resolving pointer-based codes.
    """
    if not quick_pointer:
        raise ValueError("Empty quick_pointer")
    parts = str(quick_pointer).split()
    if len(parts) < 2:
        raise ValueError(f"Malformed quick_pointer: {quick_pointer!r}")
    return int(parts[1], 16)

def resolve_slot_base_offset(slot_number: int) -> int:
    """
    Return the file offset (in memory.dat) of the start of Slot N's data region.

    Uses only 'alt_pointer' (which should be in form "95000000 XXXXXXXX").

    If alt_pointer is missing or invalid, returns 0 (slot considered unmapped/unused).
    """
    slot = get_save_slot(slot_number)
    if not slot:
        return 0

    alt = slot.get("alt_pointer")
    if alt:
        parts = str(alt).split()
        if len(parts) >= 2:
            try:
                return int(parts[1], 16)
            except ValueError:
                pass

    return 0

# ---------------------------------------------------------------------------
# Inventory / slot-table constants (used by save_file.py)
# ---------------------------------------------------------------------------

# You should adjust these to match the actual save-format layout,
# if they differ from your original assumptions.
INVENTORY_TABLE_REL_OFFSET: int = 0x001041D0  # example offset — adjust if wrong
INVENTORY_ENTRY_COUNT: int = 256               # example count — adjust as appropriate

# ---------------------------------------------------------------------------
# Legacy / compatibility constant
# (some parts of save_file.py expect this; you can update with real data if you have it)
# ---------------------------------------------------------------------------

ARMOR_STAT_MARKERS: Dict[str, tuple[str, str]] = {
    "defense":  ("0B72D37F", "6DC3F0F0"),
    "vitality": ("CBC51FB7", "7C16F8F3"),
    "luck":     ("93E62C7A", "854C0000"),
    "strength": ("7A00D0F0", "1CCEAB3A"),
    "runic":    ("48B6FD1A", "C0CB4E01"),
    "cooldown": ("57B8D16A", "F17D1E01"),
}
