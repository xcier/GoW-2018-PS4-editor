# app/core/gow2018_data.py
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import re

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent / "resources" / "database"

ITEMS_JSON = BASE_DIR / "gow2018_items.json"
SLOTS_JSON = BASE_DIR / "gow2018_slots.json"
CODES_JSON = BASE_DIR / "gow2018_codes.json"

# ---------------------------------------------------------------------------
# Save-layout constants
# ---------------------------------------------------------------------------

# Inventory/resource entries are treated as fixed 16-byte records:
#   [0x00..0x07] item/resource id bytes
#   [0x08..0x0B] quantity, little-endian u32
#   [0x0C..0x0F] entry metadata/flags, preserved exactly
#
# Verified against a real decrypted memory.dat: the table begins at
# base + 0x1041D. This is 4 bytes after the difficulty value at
# base + 0x10419, so it is close to the core stat area but does not
# overlap it. Do not change this to 0x1041D0; that shifts writes into
# unrelated slot data and can corrupt saves.
INVENTORY_TABLE_REL_OFFSET: int = 0x001041D
INVENTORY_ENTRY_SIZE: int = 16
INVENTORY_ENTRY_COUNT: int = 256
INVENTORY_TABLE_ANCHOR_ID: str = "8A9A9B831CF67C9C"  # Xp Main

# Safety bound: inventory table must start after the core stat fields.
MIN_SAFE_INVENTORY_REL_OFFSET: int = 0x001041D

# ---------------------------------------------------------------------------
# Internal caches
# ---------------------------------------------------------------------------

_items_cache: Optional[Dict[str, Any]] = None
_items_by_id_cache: Optional[Dict[str, Dict[str, Any]]] = None
_all_items_cache: Optional[List[Dict[str, Any]]] = None
_slots_cache: Optional[Dict[str, Any]] = None
_codes_cache: Optional[Dict[str, Any]] = None

_HEX_16_RE = re.compile(r"^[0-9A-F]{16}$")


# ---------------------------------------------------------------------------
# Item database display/safety normalization
# ---------------------------------------------------------------------------

_EMPTY_TEXT_VALUES = {"", "nan", "none", "null", "?"}


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in _EMPTY_TEXT_VALUES else text


def _humanize_resource_file_name(value: Any) -> str:
    """Convert an internal resources.dcb name into a readable fallback label."""
    text = _clean_text(value)
    if not text:
        return ""
    text = re.sub(r"[_\-]+", " ", text)
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text)
    text = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    replacements = {
        "Kratos Armor": "Kratos armor",
        "Nif": "Niflheim",
        "Msp": "Muspelheim",
        "NGP": "NG+",
    }
    for old, new_text in replacements.items():
        text = text.replace(old, new_text)
    return text


def _infer_item_type(file_name: str, clean_name: str = "") -> str:
    """Infer a display category for spreadsheet rows with missing Type cells.

    The ItemIDs sheet has many useful IDs whose Clean Name and/or Type cells are
    blank. Earlier builds showed those as Unknown, which made the database look
    broken even though the internal resources.dcb file name was present. This
    inference is used for display and filtering only; rows inferred from missing
    sheet metadata stay locked unless the user enables Advanced Unlock.
    """
    f = file_name.lower()
    n = clean_name.lower()
    text = f"{f} {n}"

    if "kratosarmorchest" in f:
        return "Chest Armor"
    if "kratosarmorlegs" in f:
        return "Waist Armor"
    if "kratosarmorwrist" in f:
        return "Wrist Armor"
    if "kratosarmortrinket" in f or "talisman" in f:
        return "Talisman"
    if "kratosshield" in f:
        return "Shield"
    if "weaponcomponent" in f or "reinforcement" in f or f in {"axe", "blades"} or f.startswith("axe_") or f.startswith("blades_"):
        return "Weapon / Upgrade"
    if "runecreator" in f:
        return "Enchantments"
    if f.startswith("perk_") or "perk_" in f:
        return "Perk / Enchantment"
    if "economy" in f or "resource" in f or "loot" in f:
        return "Resources"
    if "bestiary" in f:
        return "Bestiary / Progression"
    if "tutorial" in f:
        return "Tutorial"
    if "bow_" in f or "arrow" in f or "sonperk" in f:
        return "Atreus"
    if any(key in text for key in ("lore", "tryptich", "losttoy", "norse", "cup", "brooch", "mask", "hilt")):
        return "Quest / Lore"
    if any(key in text for key in ("unlock", "tracker", "flag", "cipher", "fasttravel", "quest", "display")):
        return "Progression / Unlock"
    return "Technical / Unclassified"


def normalize_items_database(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Return an item DB with display names/types and explicit edit safety.

    Existing generated JSON is accepted, so users do not have to rebuild the
    resources when upgrading. The original sheet cells are preserved as
    ``source_name`` and ``source_type``. ``safe_edit`` is True only when the
    spreadsheet had a real Clean Name and Type; inferred display metadata makes
    the UI readable but does not automatically unlock risky progression rows.
    """
    normalized_items: list[dict[str, Any]] = []
    seen: set[str] = set()

    for raw in payload.get("items", []):
        if not isinstance(raw, dict):
            continue
        item_id = normalize_item_id(raw.get("id"))
        if not item_id or item_id in seen:
            continue
        seen.add(item_id)

        source_name = _clean_text(raw.get("source_name", raw.get("name")))
        source_type = _clean_text(raw.get("source_type", raw.get("type")))
        file_name = _clean_text(raw.get("file"))
        slot_code = _clean_text(raw.get("slot_code"))

        inferred_name = source_name or _humanize_resource_file_name(file_name) or f"Unknown {item_id}"
        inferred_type = source_type or _infer_item_type(file_name, source_name)
        safe_edit = bool(source_name and source_type and source_type.lower() not in {"unknown", "?"})

        item = dict(raw)
        item.update(
            {
                "slot_code": slot_code or None,
                "id": item_id,
                "file": file_name or None,
                "source_name": source_name or None,
                "source_type": source_type or None,
                "name": inferred_name,
                "type": inferred_type,
                "metadata_source": "sheet" if safe_edit else "inferred",
                "safe_edit": bool(raw.get("safe_edit", safe_edit)) if safe_edit else False,
            }
        )
        normalized_items.append(item)

    by_id = {it["id"]: it for it in normalized_items}
    by_name: Dict[str, list[str]] = {}
    by_type: Dict[str, list[str]] = {}
    for it in normalized_items:
        name = _clean_text(it.get("name"))
        type_ = _clean_text(it.get("type")) or "Technical / Unclassified"
        if name:
            by_name.setdefault(name, []).append(it["id"])
        by_type.setdefault(type_, []).append(it["id"])

    return {"items": normalized_items, "by_id": by_id, "by_name": by_name, "by_type": by_type}


def _load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Missing resource file: {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _ensure_items_loaded() -> None:
    global _items_cache
    if _items_cache is None:
        _items_cache = normalize_items_database(_load_json(ITEMS_JSON))


def _ensure_slots_loaded() -> None:
    global _slots_cache
    if _slots_cache is None:
        _slots_cache = _load_json(SLOTS_JSON)


def _ensure_codes_loaded() -> None:
    global _codes_cache
    if _codes_cache is None:
        _codes_cache = _load_json(CODES_JSON)


# ---------------------------------------------------------------------------
# Item helpers
# ---------------------------------------------------------------------------


def normalize_item_id(value: Any) -> str:
    """Return a clean 16-character uppercase hex item ID or an empty string."""
    if value is None:
        return ""
    text = str(value).strip().replace(" ", "").upper()
    return text if _HEX_16_RE.fullmatch(text) else ""


def is_valid_item_id(value: Any) -> bool:
    return bool(normalize_item_id(value))


# ---------------------------------------------------------------------------
# Items API (from ItemIDs sheet)
# ---------------------------------------------------------------------------


def get_all_items() -> List[Dict[str, Any]]:
    """Return the item database rows.

    This is cached because the Inventory tab and save loader ask for it often.
    The database is static for the life of the app, so rebuilding the list on
    every save open just makes loading feel sluggish.
    """
    global _all_items_cache
    _ensure_items_loaded()
    if _all_items_cache is None:
        _all_items_cache = list(_items_cache["items"])  # type: ignore[index]
    return _all_items_cache


def get_items_by_id() -> Dict[str, Dict[str, Any]]:
    """Return normalized item metadata keyed by 16-character item ID.

    Older builds rebuilt this 1,600+ item dictionary every time a row was
    checked for delete/edit safety. Opening a save reads hundreds of rows
    across multiple slots, so that became the main load-time bottleneck.
    """
    global _items_by_id_cache
    _ensure_items_loaded()
    if _items_by_id_cache is None:
        raw = _items_cache["by_id"]  # type: ignore[index]
        _items_by_id_cache = {normalize_item_id(k): v for k, v in raw.items() if normalize_item_id(k)}
    return _items_by_id_cache


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
            if int(slot.get("slot", -1)) == int(slot_number):
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
    Parse a Save Wizard Quick Mode pointer and return the 32-bit address stored
    in the second token. This is useful for code generation, not direct writes.
    """
    if not quick_pointer:
        raise ValueError("Empty quick_pointer")
    parts = str(quick_pointer).split()
    if len(parts) < 2:
        raise ValueError(f"Malformed quick_pointer: {quick_pointer!r}")
    return int(parts[1], 16)


def _parse_alt_pointer(alt_pointer: Any) -> int:
    if not alt_pointer:
        return 0
    parts = str(alt_pointer).split()
    if len(parts) < 2 or parts[0].upper() != "95000000":
        return 0
    try:
        return int(parts[1], 16)
    except ValueError:
        return 0


def resolve_slot_base_offset(slot_number: int) -> int:
    """
    Return the file offset in memory.dat for physical save data block N.

    The spreadsheet's 'Alternative Slot format / Actual Data' column is the
    direct memory.dat base. It is safer than pointer-mode codes for this editor.
    """
    slot = get_save_slot(slot_number)
    if not slot:
        return 0
    return _parse_alt_pointer(slot.get("alt_pointer"))


def get_valid_slot_base_offsets() -> List[int]:
    bases = []
    for slot in get_save_slots():
        base = _parse_alt_pointer(slot.get("alt_pointer"))
        if base > 0:
            bases.append(base)
    return sorted(set(bases))


def get_next_slot_base_offset(slot_number: int) -> int:
    """Return the next physical slot base after slot_number, or 0 if unknown."""
    base = resolve_slot_base_offset(slot_number)
    if base <= 0:
        return 0
    for candidate in get_valid_slot_base_offsets():
        if candidate > base:
            return candidate
    return 0




def get_slot_block_size() -> int:
    """Return the fixed byte size of one physical save-slot block.

    The community slot table is evenly spaced. For a normal 20-slot
    memory.dat every block is 0x1998C8 bytes. Keeping this derived from
    the slot table makes transfer code fail loudly if the table changes.
    """
    bases = get_valid_slot_base_offsets()
    if len(bases) >= 2:
        deltas = [b - a for a, b in zip(bases, bases[1:]) if b > a]
        if deltas and all(delta == deltas[0] for delta in deltas):
            return int(deltas[0])
    return 0


def slot_range_for_slot(raw_len: int, slot_number: int) -> tuple[int, int]:
    """Return the full byte range for a physical save-slot block.

    This is intentionally broader than inventory_region_for_slot(): it covers
    the entire slot payload so a complete slot can be exported/replaced.
    """
    base = resolve_slot_base_offset(slot_number)
    if base <= 0 or base >= raw_len:
        return (0, 0)

    next_base = get_next_slot_base_offset(slot_number)
    if next_base <= 0:
        block_size = get_slot_block_size()
        if block_size <= 0:
            return (0, 0)
        end = base + block_size
    else:
        end = next_base

    if end <= base or end > raw_len:
        return (0, 0)
    return (base, end)


def slot_block_size_for_file(raw_len: int, slot_number: int) -> int:
    """Return slot block length for this file/slot, or 0 if invalid."""
    start, end = slot_range_for_slot(raw_len, slot_number)
    return max(0, end - start)


def inventory_region_for_slot(raw_len: int, slot_number: int) -> tuple[int, int]:
    """
    Return the expected inventory/resource table byte range for a slot,
    or (0, 0) if the range is out-of-bounds.

    This function checks address arithmetic only. Call
    inventory_anchor_is_valid(raw, slot_number) before enabling writes to
    make sure the active slot actually has a resource table at that range.
    """
    base = resolve_slot_base_offset(slot_number)
    if base <= 0 or base >= raw_len:
        return (0, 0)

    rel = INVENTORY_TABLE_REL_OFFSET
    if rel < MIN_SAFE_INVENTORY_REL_OFFSET:
        return (0, 0)

    start = base + rel
    end = start + (INVENTORY_ENTRY_COUNT * INVENTORY_ENTRY_SIZE)

    next_base = get_next_slot_base_offset(slot_number)
    if next_base > 0:
        end = min(end, next_base)

    if start < 0 or start >= raw_len or end <= start:
        return (0, 0)
    end = min(end, raw_len)

    if end - start < INVENTORY_ENTRY_SIZE:
        return (0, 0)
    return (start, end)


def inventory_anchor_is_valid(raw: bytes | bytearray, slot_number: int) -> bool:
    """Return True when the slot's resource table starts with the XP entry.

    Empty/unused slot blocks can have an in-range address but no real table.
    Writes to those blocks should stay disabled unless the anchor matches.
    """
    if not isinstance(raw, (bytes, bytearray)):
        return False
    start, end = inventory_region_for_slot(len(raw), slot_number)
    if end <= start or start + 8 > len(raw):
        return False
    return bytes(raw[start:start + 8]).hex().upper() == INVENTORY_TABLE_ANCHOR_ID


# ---------------------------------------------------------------------------
# Legacy / compatibility constant
# ---------------------------------------------------------------------------

ARMOR_STAT_MARKERS: Dict[str, tuple[str, str]] = {
    "defense":  ("0B72D37F", "6DC3F0F0"),
    "vitality": ("CBC51FB7", "7C16F8F3"),
    "luck":     ("93E62C7A", "854C0000"),
    "strength": ("7A00D0F0", "1CCEAB3A"),
    "runic":    ("48B6FD1A", "C0CB4E01"),
    "cooldown": ("57B8D16A", "F17D1E01"),
}
