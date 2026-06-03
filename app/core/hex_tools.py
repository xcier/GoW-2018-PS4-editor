from __future__ import annotations

import re
from typing import Optional, Sequence, Union

BytesLike = Union[bytes, bytearray, memoryview]


class HexToolError(ValueError):
    """Raised when a raw hex-editor operation cannot be completed safely."""


def parse_offset(text: str, file_size: Optional[int] = None, *, allow_end: bool = False) -> int:
    """Parse a decimal or hex offset and validate it against an optional file size."""
    raw = (text or "").strip().replace("_", "")
    if not raw:
        raise HexToolError("Offset is empty.")

    try:
        if raw.lower().startswith("0x"):
            offset = int(raw, 16)
        elif any(ch in raw.lower() for ch in "abcdef"):
            offset = int(raw, 16)
        else:
            offset = int(raw, 10)
    except ValueError as exc:
        raise HexToolError(f"Invalid offset: {text!r}") from exc

    if offset < 0:
        raise HexToolError("Offset cannot be negative.")

    if file_size is not None:
        limit = int(file_size)
        if allow_end:
            if offset > limit:
                raise HexToolError(f"Offset 0x{offset:X} is past EOF 0x{limit:X}.")
        elif offset >= limit:
            raise HexToolError(f"Offset 0x{offset:X} is outside the file, size 0x{limit:X}.")

    return offset


def parse_hex_bytes(text: str) -> bytes:
    """Parse user-entered hex bytes.

    Accepts common forms such as ``DE AD BE EF``, ``0xDE,0xAD``,
    ``DEADBEEF``, and mixed whitespace / comma / colon / dash separators.
    """
    raw = (text or "").strip()
    if not raw:
        raise HexToolError("Byte patch/search value is empty.")

    cleaned = raw.replace("0x", "").replace("0X", "")
    cleaned = re.sub(r"[\s,;:_\-]+", "", cleaned)
    if not cleaned:
        raise HexToolError("Byte patch/search value is empty.")
    if len(cleaned) % 2:
        raise HexToolError("Hex byte input must contain an even number of digits.")
    if not re.fullmatch(r"[0-9a-fA-F]+", cleaned):
        raise HexToolError("Hex byte input contains non-hex characters.")

    try:
        return bytes.fromhex(cleaned)
    except ValueError as exc:
        raise HexToolError("Could not parse hex byte input.") from exc


def ascii_to_bytes(text: str) -> bytes:
    if text == "":
        raise HexToolError("ASCII search text is empty.")
    return text.encode("utf-8")


def clamp_window_offset(offset: int, file_size: int, window_size: int, *, align: int = 16) -> int:
    """Clamp a window start to a valid, optionally aligned file offset."""
    file_size = max(0, int(file_size))
    window_size = max(1, int(window_size))
    offset = max(0, int(offset))
    if file_size <= 0:
        return 0
    max_start = max(0, file_size - min(window_size, file_size))
    offset = min(offset, max_start)
    if align > 1:
        offset -= offset % align
    return max(0, offset)


def find_bytes(data: BytesLike, needle: bytes, *, start: int = 0, wrap: bool = True) -> Optional[int]:
    """Find bytes from ``start``; optionally wrap once to the beginning."""
    haystack = bytes(data)
    if not needle:
        raise HexToolError("Search value is empty.")
    if not haystack:
        return None

    start = max(0, min(int(start), len(haystack)))
    pos = haystack.find(needle, start)
    if pos != -1:
        return pos
    if wrap and start > 0:
        pos = haystack.find(needle, 0, start)
        if pos != -1:
            return pos
    return None


def hexdump_window(
    data: BytesLike,
    offset: int = 0,
    length: int = 0x400,
    *,
    bytes_per_line: int = 16,
    highlight_offset: Optional[int] = None,
) -> str:
    """Return a classic offset / hex / ASCII view for a byte window."""
    buf = bytes(data)
    if not buf:
        return "<no save loaded>"

    bytes_per_line = max(4, min(int(bytes_per_line), 32))
    length = max(1, int(length))
    offset = clamp_window_offset(int(offset), len(buf), length, align=bytes_per_line)
    end = min(len(buf), offset + length)
    width = max(8, len(f"{len(buf):X}"))

    lines: list[str] = []
    for line_start in range(offset, end, bytes_per_line):
        chunk = buf[line_start : min(line_start + bytes_per_line, end)]
        hex_left = " ".join(f"{b:02X}" for b in chunk[:8])
        hex_right = " ".join(f"{b:02X}" for b in chunk[8:])
        if hex_right:
            hex_part = f"{hex_left:<23}  {hex_right:<23}"
        else:
            hex_part = f"{hex_left:<23}  {'':<23}"
        ascii_part = "".join(chr(b) if 32 <= b <= 126 else "." for b in chunk)
        marker = ">" if highlight_offset is not None and line_start <= highlight_offset < line_start + bytes_per_line else " "
        lines.append(f"{marker}{line_start:0{width}X}  {hex_part}  |{ascii_part:<{bytes_per_line}}|")
    return "\n".join(lines)


def apply_byte_patch(data: BytesLike, offset: int, patch: Sequence[int]) -> bytearray:
    """Return a patched copy of ``data`` after strict bounds checks."""
    buf = bytearray(data)
    patch_bytes = bytes(patch)
    if not patch_bytes:
        raise HexToolError("Patch is empty.")
    offset = parse_offset(hex(int(offset)), len(buf), allow_end=False)
    end = offset + len(patch_bytes)
    if end > len(buf):
        raise HexToolError(
            f"Patch 0x{offset:X}-0x{end:X} exceeds file size 0x{len(buf):X}."
        )
    buf[offset:end] = patch_bytes
    return buf
