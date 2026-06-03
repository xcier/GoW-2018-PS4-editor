from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Union
import hashlib
import json
import struct

from app.core import gow2018_data
from app.core.save_file import SaveFile

MAGIC = b"GOW2018SLOTv1\n"
HEADER_LEN_STRUCT = "<I"
DEFAULT_EXTENSION = ".gow2018slot"


class SlotTransferError(ValueError):
    """Raised when a full-slot export/import is not safe to perform."""


@dataclass(frozen=True)
class SlotPackage:
    metadata: dict[str, Any]
    slot_bytes: bytes

    @property
    def display_label(self) -> str:
        label = str(self.metadata.get("display_label", "") or "").strip()
        if label:
            return label
        summary = self.metadata.get("summary", {})
        location = ""
        if isinstance(summary, dict):
            location = str(summary.get("location", "") or "").strip()
        src = self.source_slot
        return f"Slot {src}" + (f" — {location}" if location else "")

    @property
    def source_slot(self) -> int:
        try:
            return int(self.metadata.get("source_slot", 0) or 0)
        except Exception:
            return 0

    @property
    def block_size(self) -> int:
        return len(self.slot_bytes)

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.slot_bytes).hexdigest()


@dataclass(frozen=True)
class SlotTransferResult:
    target_slot: int
    start: int
    end: int
    bytes_replaced: int
    source_slot: Optional[int] = None
    source_path: Optional[str] = None

    @property
    def summary(self) -> str:
        src = f"slot {self.source_slot}" if self.source_slot else "slot package"
        return (
            f"Copied {self.bytes_replaced:,} bytes from {src} into target slot {self.target_slot} "
            f"at 0x{self.start:X}-0x{self.end:X}."
        )


def _raw_bytes(raw: Union[bytes, bytearray]) -> bytes:
    if isinstance(raw, bytearray):
        return bytes(raw)
    if isinstance(raw, bytes):
        return raw
    raise TypeError("raw must be bytes or bytearray")


def slot_range(raw: Union[bytes, bytearray], slot_index: int) -> tuple[int, int]:
    data = _raw_bytes(raw)
    start, end = gow2018_data.slot_range_for_slot(len(data), int(slot_index))
    if end <= start:
        raise SlotTransferError(f"Slot {slot_index} does not have a valid full-slot range in this file.")
    return start, end


def extract_slot_bytes(raw: Union[bytes, bytearray], slot_index: int, *, allow_empty: bool = False) -> bytes:
    """Return the complete physical slot block for slot_index."""
    data = _raw_bytes(raw)
    start, end = slot_range(data, slot_index)
    block = data[start:end]
    if not allow_empty and not slot_looks_used(data, slot_index):
        raise SlotTransferError(
            f"Slot {slot_index} does not look like an active/used slot. "
            "Enable empty-slot export only for research."
        )
    if not block or set(block) == {0}:
        raise SlotTransferError(f"Slot {slot_index} is all zeroes; refusing to export an empty slot.")
    return bytes(block)


def summarize_slot(raw: Union[bytes, bytearray], slot_index: int) -> dict[str, Any]:
    data = _raw_bytes(raw)
    save = SaveFile(raw=data, active_slot=int(slot_index))
    summary = save.summarize_slot(int(slot_index)) or {}
    summary["inventory_anchor_valid"] = bool(gow2018_data.inventory_anchor_is_valid(data, int(slot_index)))
    start, end = gow2018_data.slot_range_for_slot(len(data), int(slot_index))
    summary["slot_start"] = start
    summary["slot_end"] = end
    summary["slot_size"] = max(0, end - start)
    return summary


def slot_looks_used(raw: Union[bytes, bytearray], slot_index: int) -> bool:
    """Conservative check for whether a source slot is worth exporting."""
    summary = summarize_slot(raw, int(slot_index))
    ts_raw = int(summary.get("last_played_raw", 0) or 0)
    location = str(summary.get("location", "") or "").strip()
    xp = int(summary.get("xp", 0) or 0)
    hs = int(summary.get("hacksilver", 0) or 0)
    anchor = bool(summary.get("inventory_anchor_valid", False))

    plausible_timestamp = 946684800 <= ts_raw <= 4102444800
    return bool(plausible_timestamp and (location or xp or hs or anchor))


def build_package_metadata(
    raw: Union[bytes, bytearray],
    source_slot: int,
    slot_bytes: bytes,
    *,
    source_path: Optional[Path] = None,
    display_label: Optional[str] = None,
) -> dict[str, Any]:
    summary = summarize_slot(raw, source_slot)
    label = str(display_label or "").strip()
    if not label:
        location = str(summary.get("location", "") or "").strip()
        label = f"Slot {int(source_slot):02d}" + (f" — {location}" if location else "")
    return {
        "format": "GOW2018_SLOT_TRANSFER",
        "version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_path": str(source_path) if source_path is not None else "",
        "source_file_size": len(_raw_bytes(raw)),
        "source_slot": int(source_slot),
        "display_label": label,
        "block_size": len(slot_bytes),
        "slot_sha256": hashlib.sha256(slot_bytes).hexdigest(),
        "summary": summary,
    }


def write_slot_package(
    raw: Union[bytes, bytearray],
    source_slot: int,
    output_path: Path,
    *,
    source_path: Optional[Path] = None,
    allow_empty: bool = False,
    display_label: Optional[str] = None,
) -> SlotPackage:
    """Export one complete slot to a portable .gow2018slot package."""
    data = _raw_bytes(raw)
    slot_bytes = extract_slot_bytes(data, source_slot, allow_empty=allow_empty)
    metadata = build_package_metadata(data, source_slot, slot_bytes, source_path=source_path, display_label=display_label)
    header = json.dumps(metadata, indent=2, sort_keys=True).encode("utf-8")
    payload = MAGIC + struct.pack(HEADER_LEN_STRUCT, len(header)) + header + slot_bytes
    output_path.write_bytes(payload)
    return SlotPackage(metadata=metadata, slot_bytes=slot_bytes)


def write_slot_package_from_memory_dat(
    source_path: Path,
    source_slot: int,
    output_path: Path,
    *,
    allow_empty: bool = False,
    display_label: Optional[str] = None,
) -> SlotPackage:
    raw = source_path.read_bytes()
    return write_slot_package(
        raw,
        source_slot,
        output_path,
        source_path=source_path,
        allow_empty=allow_empty,
        display_label=display_label,
    )


def read_slot_package(path: Path) -> SlotPackage:
    payload = path.read_bytes()
    if not payload.startswith(MAGIC):
        raise SlotTransferError("Not a GoW 2018 slot package.")
    offset = len(MAGIC)
    if len(payload) < offset + struct.calcsize(HEADER_LEN_STRUCT):
        raise SlotTransferError("Slot package is truncated before its header length.")
    header_len = struct.unpack_from(HEADER_LEN_STRUCT, payload, offset)[0]
    offset += struct.calcsize(HEADER_LEN_STRUCT)
    header_end = offset + header_len
    if header_len <= 0 or header_end > len(payload):
        raise SlotTransferError("Slot package has an invalid header length.")
    try:
        metadata = json.loads(payload[offset:header_end].decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise SlotTransferError(f"Slot package header is not valid JSON: {exc}") from exc
    slot_bytes = payload[header_end:]
    expected_size = int(metadata.get("block_size", 0) or 0)
    expected_hash = str(metadata.get("slot_sha256", "") or "")
    if expected_size and expected_size != len(slot_bytes):
        raise SlotTransferError(
            f"Slot package block size mismatch: header says {expected_size}, file has {len(slot_bytes)}."
        )
    actual_hash = hashlib.sha256(slot_bytes).hexdigest()
    if expected_hash and expected_hash.lower() != actual_hash.lower():
        raise SlotTransferError("Slot package SHA256 mismatch; the package may be damaged.")
    if not slot_bytes:
        raise SlotTransferError("Slot package contains no slot data.")
    return SlotPackage(metadata=metadata, slot_bytes=slot_bytes)


def write_slot_package_payload(package: SlotPackage, output_path: Path) -> None:
    """Write a SlotPackage object back to disk.

    This preserves the slot payload exactly and rewrites only the JSON header.
    It is used for package display labels, not for editing save-slot bytes.
    """
    header = json.dumps(package.metadata, indent=2, sort_keys=True).encode("utf-8")
    payload = MAGIC + struct.pack(HEADER_LEN_STRUCT, len(header)) + header + package.slot_bytes
    Path(output_path).write_bytes(payload)


def update_slot_package_label(path: Path, label: str) -> SlotPackage:
    """Update a .gow2018slot display label while preserving slot bytes."""
    clean = str(label or "").strip()
    if not clean:
        raise SlotTransferError("Slot package label cannot be empty.")
    package = read_slot_package(Path(path))
    metadata = dict(package.metadata)
    metadata["display_label"] = clean
    updated = SlotPackage(metadata=metadata, slot_bytes=package.slot_bytes)
    write_slot_package_payload(updated, Path(path))
    return updated


def replace_slot_bytes(
    target_raw: Union[bytes, bytearray],
    target_slot: int,
    slot_bytes: bytes,
    *,
    source_slot: Optional[int] = None,
    source_path: Optional[str] = None,
) -> tuple[bytes, SlotTransferResult]:
    """Return target_raw with one complete slot block replaced."""
    data = _raw_bytes(target_raw)
    start, end = slot_range(data, target_slot)
    expected_len = end - start
    if len(slot_bytes) != expected_len:
        raise SlotTransferError(
            f"Slot block size mismatch. Target slot {target_slot} expects {expected_len:,} bytes, "
            f"but source block has {len(slot_bytes):,} bytes."
        )
    if not slot_bytes or set(slot_bytes) == {0}:
        raise SlotTransferError("Refusing to import an all-zero slot block.")

    buf = bytearray(data)
    buf[start:end] = slot_bytes
    result = SlotTransferResult(
        target_slot=int(target_slot),
        start=start,
        end=end,
        bytes_replaced=expected_len,
        source_slot=source_slot,
        source_path=source_path,
    )
    return bytes(buf), result


def import_slot_package_into_bytes(
    target_raw: Union[bytes, bytearray],
    package: SlotPackage,
    target_slot: int,
) -> tuple[bytes, SlotTransferResult]:
    source_path = str(package.metadata.get("source_path", "") or "")
    source_slot = package.source_slot or None
    return replace_slot_bytes(
        target_raw,
        target_slot,
        package.slot_bytes,
        source_slot=source_slot,
        source_path=source_path or None,
    )


def import_slot_package_file_into_bytes(
    target_raw: Union[bytes, bytearray],
    package_path: Path,
    target_slot: int,
) -> tuple[bytes, SlotTransferResult]:
    package = read_slot_package(package_path)
    return import_slot_package_into_bytes(target_raw, package, target_slot)


def copy_slot_between_bytes(
    source_raw: Union[bytes, bytearray],
    source_slot: int,
    target_raw: Union[bytes, bytearray],
    target_slot: int,
    *,
    source_path: Optional[Path] = None,
) -> tuple[bytes, SlotTransferResult]:
    source_data = _raw_bytes(source_raw)
    block = extract_slot_bytes(source_data, source_slot)
    return replace_slot_bytes(
        target_raw,
        target_slot,
        block,
        source_slot=int(source_slot),
        source_path=str(source_path) if source_path is not None else None,
    )


def copy_slot_from_memory_dat_into_bytes(
    source_path: Path,
    source_slot: int,
    target_raw: Union[bytes, bytearray],
    target_slot: int,
) -> tuple[bytes, SlotTransferResult]:
    return copy_slot_between_bytes(
        source_path.read_bytes(),
        source_slot,
        target_raw,
        target_slot,
        source_path=source_path,
    )
