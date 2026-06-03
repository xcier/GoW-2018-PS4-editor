# app/ui/tabs/hex_tab.py
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QAbstractSpinBox,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.core import gow2018_data
from app.core.file_context import FileContext
from app.core.hex_tools import (
    HexToolError,
    apply_byte_patch,
    ascii_to_bytes,
    clamp_window_offset,
    find_bytes,
    hexdump_window,
    parse_hex_bytes,
    parse_offset,
)


class HexEditorTab(QWidget):
    """Guarded raw byte viewer/editor for decrypted memory.dat files.

    The main editor owns safe, structured writes. This tab exists for research,
    verification, and exact byte patches; it is read-only until the user explicitly
    enables raw write mode.
    """

    def __init__(self, file_ctx: FileContext, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._file_ctx = file_ctx
        self._view_offset = 0
        self._highlight_offset: Optional[int] = None
        self._last_search_offset: Optional[int] = None
        self._build_ui()
        self.refresh_from_context()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(14)

        top = QFrame(self)
        top.setObjectName("Card")
        top_layout = QGridLayout(top)
        top_layout.setContentsMargins(16, 14, 16, 14)
        top_layout.setHorizontalSpacing(10)
        top_layout.setVerticalSpacing(10)

        title = QLabel("Raw Hex Viewer", top)
        title.setObjectName("SectionTitle")
        top_layout.addWidget(title, 0, 0, 1, 2)

        self.file_info_chip = QLabel("No save loaded", top)
        self.file_info_chip.setObjectName("Chip")
        top_layout.addWidget(self.file_info_chip, 0, 2, 1, 3)

        top_layout.addWidget(QLabel("Offset", top), 1, 0)
        self.offset_edit = QLineEdit(top)
        self.offset_edit.setPlaceholderText("0x00000000")
        self.offset_edit.returnPressed.connect(self._on_jump_clicked)
        top_layout.addWidget(self.offset_edit, 1, 1)

        self.btn_go = QPushButton("Jump", top)
        self.btn_go.setObjectName("PrimaryButton")
        self.btn_go.clicked.connect(self._on_jump_clicked)
        top_layout.addWidget(self.btn_go, 1, 2)

        top_layout.addWidget(QLabel("Window", top), 1, 3)
        self.length_box = QSpinBox(top)
        self.length_box.setRange(0x40, 0x10000)
        self.length_box.setValue(0x400)
        self.length_box.setSingleStep(0x100)
        self.length_box.setAccelerated(True)
        self.length_box.setSuffix(" bytes")
        self.length_box.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.UpDownArrows)
        self.length_box.valueChanged.connect(lambda _value: self._refresh_view())
        top_layout.addWidget(self.length_box, 1, 4)

        self.btn_copy = QPushButton("Copy View", top)
        self.btn_copy.clicked.connect(self._copy_current_view)
        top_layout.addWidget(self.btn_copy, 1, 5)

        self.range_label = QLabel("Open a decrypted memory.dat to inspect raw bytes.", top)
        self.range_label.setObjectName("MutedLabel")
        self.range_label.setWordWrap(True)
        top_layout.addWidget(self.range_label, 2, 0, 1, 6)

        root.addWidget(top)

        shortcuts = QFrame(self)
        shortcuts.setObjectName("Card")
        shortcut_layout = QHBoxLayout(shortcuts)
        shortcut_layout.setContentsMargins(16, 14, 16, 14)
        shortcut_layout.setSpacing(8)
        shortcut_layout.addWidget(QLabel("Known offsets", shortcuts))

        for label, key in (
            ("Active Slot Base", "slot"),
            ("Inventory Table", "inventory"),
            ("Difficulty", "difficulty"),
            ("Kratos XP", "kratos_xp"),
            ("Hacksilver", "hacksilver"),
        ):
            btn = QPushButton(label, shortcuts)
            btn.clicked.connect(lambda _checked=False, k=key: self._jump_known(k))
            shortcut_layout.addWidget(btn)
        shortcut_layout.addStretch(1)
        root.addWidget(shortcuts)

        search_card = QFrame(self)
        search_card.setObjectName("Card")
        search_layout = QHBoxLayout(search_card)
        search_layout.setContentsMargins(16, 14, 16, 14)
        search_layout.setSpacing(10)

        search_layout.addWidget(QLabel("Search", search_card))
        self.search_mode = QComboBox(search_card)
        self.search_mode.addItems(["Hex bytes", "ASCII text"])
        search_layout.addWidget(self.search_mode)

        self.search_edit = QLineEdit(search_card)
        self.search_edit.setPlaceholderText("DE AD BE EF or text...")
        self.search_edit.returnPressed.connect(self._search_next)
        search_layout.addWidget(self.search_edit, 1)

        self.btn_search = QPushButton("Find Next", search_card)
        self.btn_search.setObjectName("PrimaryButton")
        self.btn_search.clicked.connect(self._search_next)
        search_layout.addWidget(self.btn_search)

        self.search_status = QLabel("Search wraps once from the current view.", search_card)
        self.search_status.setObjectName("MutedLabel")
        search_layout.addWidget(self.search_status, 1)
        root.addWidget(search_card)

        self.hex_view = QPlainTextEdit(self)
        self.hex_view.setObjectName("HexView")
        self.hex_view.setReadOnly(True)
        self.hex_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.hex_view.setPlaceholderText("Open a decrypted memory.dat to view raw bytes.")
        root.addWidget(self.hex_view, 1)

        patch_card = QFrame(self)
        patch_card.setObjectName("Card")
        patch_layout = QGridLayout(patch_card)
        patch_layout.setContentsMargins(16, 14, 16, 14)
        patch_layout.setHorizontalSpacing(10)
        patch_layout.setVerticalSpacing(10)

        patch_title = QLabel("Raw Byte Patch", patch_card)
        patch_title.setObjectName("SectionTitle")
        patch_layout.addWidget(patch_title, 0, 0, 1, 2)

        self.write_enable_chk = QCheckBox("Enable raw patch mode", patch_card)
        self.write_enable_chk.toggled.connect(self._sync_patch_controls)
        patch_layout.addWidget(self.write_enable_chk, 0, 2, 1, 2)

        patch_layout.addWidget(QLabel("Offset", patch_card), 1, 0)
        self.patch_offset_edit = QLineEdit(patch_card)
        self.patch_offset_edit.setPlaceholderText("0x00000000")
        patch_layout.addWidget(self.patch_offset_edit, 1, 1)

        patch_layout.addWidget(QLabel("Bytes", patch_card), 1, 2)
        self.patch_bytes_edit = QLineEdit(patch_card)
        self.patch_bytes_edit.setPlaceholderText("Example: 01 00 00 00")
        patch_layout.addWidget(self.patch_bytes_edit, 1, 3, 1, 2)

        self.btn_patch = QPushButton("Stage Byte Patch", patch_card)
        self.btn_patch.setObjectName("DangerButton")
        self.btn_patch.clicked.connect(self._apply_byte_patch)
        patch_layout.addWidget(self.btn_patch, 1, 5)

        self.patch_status = QLabel(
            "Read-only by default. Raw patches are staged in memory and still require Save/Save As to write to disk.",
            patch_card,
        )
        self.patch_status.setObjectName("WarnChip")
        self.patch_status.setWordWrap(True)
        patch_layout.addWidget(self.patch_status, 2, 0, 1, 6)
        root.addWidget(patch_card)

    # ------------------------------------------------------------------
    # Context + helpers
    # ------------------------------------------------------------------

    def _raw(self) -> Optional[bytes | bytearray]:
        save = getattr(self._file_ctx, "save", None)
        raw = getattr(save, "raw", None)
        if isinstance(raw, (bytes, bytearray)):
            return raw
        return None

    def _set_controls_enabled(self, enabled: bool) -> None:
        for widget in (
            self.offset_edit,
            self.btn_go,
            self.length_box,
            self.btn_copy,
            self.search_mode,
            self.search_edit,
            self.btn_search,
            self.write_enable_chk,
        ):
            widget.setEnabled(enabled)
        self._sync_patch_controls()

    def _sync_patch_controls(self) -> None:
        enabled = self._raw() is not None and self.write_enable_chk.isChecked()
        self.patch_offset_edit.setEnabled(enabled)
        self.patch_bytes_edit.setEnabled(enabled)
        self.btn_patch.setEnabled(enabled)

    def refresh_from_context(self) -> None:
        raw = self._raw()
        if raw is None:
            self._view_offset = 0
            self._highlight_offset = None
            self._last_search_offset = None
            self.hex_view.clear()
            self.file_info_chip.setText("No save loaded")
            self.range_label.setText("Open a decrypted memory.dat to inspect raw bytes.")
            self._set_controls_enabled(False)
            return

        self._set_controls_enabled(True)
        file_size = len(raw)
        path = getattr(self._file_ctx, "path", None)
        name = path.name if path is not None else "memory.dat"
        active_slot = getattr(getattr(self._file_ctx, "save", None), "active_slot", 1)
        self.file_info_chip.setText(f"{name} · {file_size:,} bytes · slot {active_slot}")
        self._view_offset = clamp_window_offset(self._view_offset, file_size, self.length_box.value())
        self._refresh_view()

    def apply_to_save(self, force: bool = False) -> None:
        # Raw byte patches are applied immediately to save.raw and marked dirty.
        # This no-op keeps MainWindow's commit pipeline uniform across tabs.
        return

    # ------------------------------------------------------------------
    # Navigation + rendering
    # ------------------------------------------------------------------

    def _refresh_view(self) -> None:
        raw = self._raw()
        if raw is None:
            return
        file_size = len(raw)
        window_size = self.length_box.value()
        self._view_offset = clamp_window_offset(self._view_offset, file_size, window_size)
        end = min(file_size, self._view_offset + window_size)
        self.offset_edit.blockSignals(True)
        self.offset_edit.setText(f"0x{self._view_offset:08X}")
        self.offset_edit.blockSignals(False)
        self.hex_view.setPlainText(
            hexdump_window(
                raw,
                self._view_offset,
                window_size,
                highlight_offset=self._highlight_offset,
            )
        )
        self.range_label.setText(
            f"Viewing 0x{self._view_offset:08X}-0x{end:08X} of 0x{file_size:08X}. "
            "Use known-offset buttons for safer navigation."
        )

    def _jump_to_offset(self, offset: int, *, highlight: Optional[int] = None) -> None:
        raw = self._raw()
        if raw is None:
            return
        self._highlight_offset = offset if highlight is None else highlight
        self._view_offset = clamp_window_offset(offset, len(raw), self.length_box.value())
        self.patch_offset_edit.setText(f"0x{self._highlight_offset:08X}")
        self._refresh_view()

    def _on_jump_clicked(self) -> None:
        raw = self._raw()
        if raw is None:
            return
        try:
            offset = parse_offset(self.offset_edit.text(), len(raw))
        except HexToolError as exc:
            QMessageBox.warning(self, "Invalid offset", str(exc))
            return
        self._jump_to_offset(offset)

    def _jump_known(self, key: str) -> None:
        raw = self._raw()
        save = getattr(self._file_ctx, "save", None)
        if raw is None or save is None:
            return

        slot_index = int(getattr(save, "active_slot", 1) or 1)
        base = gow2018_data.resolve_slot_base_offset(slot_index)
        if base < 0 or base >= len(raw):
            QMessageBox.warning(self, "Offset unavailable", f"Slot {slot_index} base is outside this file.")
            return

        try:
            if key == "slot":
                offset = base
            elif key == "inventory":
                offset, _end = gow2018_data.inventory_region_for_slot(len(raw), slot_index)
            else:
                layout = getattr(save, "layout", None)
                if layout is None and hasattr(save, "_init_layout"):
                    save._init_layout()
                    layout = getattr(save, "layout", None)
                field = getattr(layout, "fields", {}).get(key) if layout is not None else None
                if field is None:
                    raise HexToolError(f"No known field offset for {key}.")
                offset = base + int(field.offset)
        except Exception as exc:
            QMessageBox.warning(self, "Offset unavailable", str(exc))
            return

        self._jump_to_offset(offset)
        self.search_status.setText(f"Jumped to {key.replace('_', ' ')} at 0x{offset:08X}.")

    def _copy_current_view(self) -> None:
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(self.hex_view.toPlainText())
            self.search_status.setText("Copied current hex window to clipboard.")

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def _search_bytes_from_ui(self) -> bytes:
        if self.search_mode.currentIndex() == 0:
            return parse_hex_bytes(self.search_edit.text())
        return ascii_to_bytes(self.search_edit.text())

    def _search_next(self) -> None:
        raw = self._raw()
        if raw is None:
            return
        try:
            needle = self._search_bytes_from_ui()
        except HexToolError as exc:
            QMessageBox.warning(self, "Invalid search", str(exc))
            return

        if self._last_search_offset is None:
            start = self._view_offset
        else:
            start = self._last_search_offset + 1
        pos = find_bytes(raw, needle, start=start, wrap=True)
        if pos is None:
            self.search_status.setText("No match found.")
            self._last_search_offset = None
            return

        self._last_search_offset = pos
        self._jump_to_offset(pos, highlight=pos)
        self.search_status.setText(f"Found {len(needle)} byte(s) at 0x{pos:08X}.")

    # ------------------------------------------------------------------
    # Raw patching
    # ------------------------------------------------------------------

    def _apply_byte_patch(self) -> None:
        raw = self._raw()
        save = getattr(self._file_ctx, "save", None)
        if raw is None or save is None:
            return
        if not self.write_enable_chk.isChecked():
            QMessageBox.information(self, "Raw patch mode disabled", "Enable raw patch mode before staging bytes.")
            return

        try:
            offset = parse_offset(self.patch_offset_edit.text(), len(raw))
            patch = parse_hex_bytes(self.patch_bytes_edit.text())
            end = offset + len(patch)
            if end > len(raw):
                raise HexToolError(f"Patch ends past EOF: 0x{end:X} > 0x{len(raw):X}.")
        except HexToolError as exc:
            QMessageBox.warning(self, "Invalid patch", str(exc))
            return

        old = bytes(raw[offset:end])
        message = (
            "Stage this raw byte patch into the in-memory save buffer?\n\n"
            f"Offset: 0x{offset:08X}\n"
            f"Old:    {old.hex(' ').upper()}\n"
            f"New:    {patch.hex(' ').upper()}\n\n"
            "This bypasses structured GoW validation. Save/Save As will still create a backup before disk write."
        )
        result = QMessageBox.warning(
            self,
            "Confirm raw byte patch",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if result != QMessageBox.StandardButton.Yes:
            return

        try:
            save.raw = apply_byte_patch(raw, offset, patch)
        except HexToolError as exc:
            QMessageBox.warning(self, "Patch failed", str(exc))
            return

        # Refresh parsed caches because raw edits may touch known fields.
        if hasattr(save, "_load_core_stats_from_binary"):
            save._load_core_stats_from_binary()
        if hasattr(save, "_load_inventory_from_binary"):
            save._load_inventory_from_binary()

        self._file_ctx.mark_dirty()
        self._jump_to_offset(offset, highlight=offset)
        self.patch_status.setText(
            f"Staged {len(patch)} byte(s) at 0x{offset:08X}. Press Save/Save As to write to disk."
        )
