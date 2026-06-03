from __future__ import annotations

import pytest

from app.core.hex_tools import (
    HexToolError,
    apply_byte_patch,
    clamp_window_offset,
    find_bytes,
    hexdump_window,
    parse_hex_bytes,
    parse_offset,
)


def test_parse_offset_accepts_hex_and_decimal() -> None:
    assert parse_offset("0x10", 0x20) == 0x10
    assert parse_offset("10", 0x20) == 10
    assert parse_offset("1A", 0x20) == 0x1A


@pytest.mark.parametrize("text", ["DE AD BE EF", "0xDE, 0xAD, 0xBE, 0xEF", "DE:AD-BE_EF", "DEADBEEF"])
def test_parse_hex_bytes_accepts_common_formats(text: str) -> None:
    assert parse_hex_bytes(text) == bytes.fromhex("DEADBEEF")


def test_parse_hex_bytes_rejects_odd_or_non_hex_input() -> None:
    with pytest.raises(HexToolError):
        parse_hex_bytes("ABC")
    with pytest.raises(HexToolError):
        parse_hex_bytes("GG")


def test_find_bytes_wraps_once() -> None:
    data = bytes.fromhex("00 11 22 33 44 55 66")
    assert find_bytes(data, bytes.fromhex("44 55"), start=0) == 4
    assert find_bytes(data, bytes.fromhex("11 22"), start=5, wrap=True) == 1
    assert find_bytes(data, bytes.fromhex("AA"), start=0) is None


def test_hexdump_window_includes_offset_hex_and_ascii() -> None:
    dump = hexdump_window(b"ABCDEFGHabcdefgh", 0, 16)
    assert "00000000" in dump
    assert "41 42 43 44" in dump
    assert "|ABCDEFGHabcdefgh|" in dump


def test_apply_byte_patch_returns_copy_and_checks_bounds() -> None:
    original = bytearray(b"012345")
    patched = apply_byte_patch(original, 2, b"AB")
    assert patched == bytearray(b"01AB45")
    assert original == bytearray(b"012345")
    with pytest.raises(HexToolError):
        apply_byte_patch(original, 5, b"XYZ")


def test_clamp_window_offset_aligns_to_hex_rows() -> None:
    assert clamp_window_offset(0x23, 0x1000, 0x100) == 0x20
    assert clamp_window_offset(0xFFFF, 0x1000, 0x100) == 0xF00
