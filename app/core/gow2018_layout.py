# app/core/gow2018_layout.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Literal

PrimitiveType = Literal["u8", "u16", "u32", "s32", "f32"]


@dataclass(frozen=True)
class SlotField:
    """
    Describes a single field relative to the start of a save slot
    (the 'Alternative Slot format "Actual Data"' base offset).
    """
    name: str
    offset: int          # offset RELATIVE to slot base
    type: PrimitiveType
    description: str = ""


@dataclass(frozen=True)
class LayoutSpec:
    """High-level description of one logical slot."""
    slot_index: int
    base_offset: int
    fields: Dict[str, SlotField]


def default_fields_for_slot(slot_index: int) -> Dict[str, SlotField]:
    """
    Definition for important fields in a slot.

    Offsets here are RELATIVE to the slot base offset returned by
    gow2018_data.resolve_slot_base_offset(slot_index), which uses the
    "Alternative Slot format \"Actual Data\"" (alt_pointer) from your
    Save Wizard sheet.

    From analyzing memory.dat using those pointers, for each slot:

      base = alt_pointer (e.g. 0x00001040 for Slot 1)

      - Difficulty marker 5F2243C6 appears at base + 0x0010409.
        The difficulty value itself is at (marker + 0x10), giving:

            difficulty offset = base + 0x0010419

      - EconomyXP ID (8A9A9B831CF67C9C) is at base + 0x001045D.
        The XP amount directly follows at:

            xp offset = base + 0x0010425

      - Hacksilver ID (9E5240D27406E85A) is nearby, with the amount at:

            hacksilver offset = base + 0x0010455
    """
    return {
        "difficulty": SlotField(
            name="difficulty",
            offset=0x0010419,
            type="u32",
            description=(
                "Game difficulty: 0 = Story, 1 = Balanced, "
                "2 = Challenge, 3 = God of War"
            ),
        ),
        "kratos_xp": SlotField(
            name="kratos_xp",
            offset=0x0010425,
            type="u32",
            description="Total XP (EconomyXP amount)",
        ),
        "hacksilver": SlotField(
            name="hacksilver",
            offset=0x0010455,
            type="u32",
            description="Hacksilver currency amount",
        ),
    }


def build_layout_for_slot(slot_index: int, base_offset: int) -> LayoutSpec:
    """Construct a LayoutSpec for the given slot index & base file offset."""
    return LayoutSpec(
        slot_index=slot_index,
        base_offset=base_offset,
        fields=default_fields_for_slot(slot_index),
    )
