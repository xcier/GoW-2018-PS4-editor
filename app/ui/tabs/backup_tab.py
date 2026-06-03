from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
    QMessageBox,
    QComboBox,
    QFileDialog,
    QInputDialog,
)

from app.core import gow2018_data
from app.core.file_context import FileContext
from app.core.save_file import SaveFile
from app.core.slot_backup_manager import (
    SlotBackupInfo,
    clone_slot_within_bytes,
    copy_slot_to_memory_dat,
    create_slot_backup,
    import_slot_backup_into_bytes,
    list_slot_backups_for_save,
    slot_backup_dir_for_save,
    write_slot_backup_to_memory_dat,
)
from app.core.slot_transfer import (
    DEFAULT_EXTENSION,
    copy_slot_from_memory_dat_into_bytes,
    import_slot_package_file_into_bytes,
    summarize_slot,
    update_slot_package_label,
    write_slot_package_from_memory_dat,
)


class BackupManagerTab(QWidget):
    """Create, restore, and move full physical slot backup packages."""

    def __init__(
        self,
        file_ctx: FileContext,
        on_restored: Optional[Callable[[], None]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.file_ctx = file_ctx
        self.on_restored = on_restored
        self.source_path: Optional[Path] = None
        self.source_save: Optional[SaveFile] = None
        self._backups: list[SlotBackupInfo] = []
        self._build_ui()
        self.refresh_from_context()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(14)

        hero = QFrame(self)
        hero.setObjectName("Card")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(16, 14, 16, 14)
        hero_layout.setSpacing(12)

        text_col = QVBoxLayout()
        title = QLabel("Slot Tools", hero)
        title.setObjectName("SectionTitle")
        subtitle = QLabel(
            "Back up, label, restore, copy, import, and transfer complete physical save slots from one consolidated workspace.",
            hero,
        )
        subtitle.setObjectName("MutedLabel")
        subtitle.setWordWrap(True)
        text_col.addWidget(title)
        text_col.addWidget(subtitle)
        hero_layout.addLayout(text_col, 1)

        self.count_chip = QLabel("0 slot backups", hero)
        self.count_chip.setObjectName("Chip")
        hero_layout.addWidget(self.count_chip)
        root.addWidget(hero)

        backup_card = QFrame(self)
        backup_card.setObjectName("Card")
        backup_layout = QVBoxLayout(backup_card)
        backup_layout.setContentsMargins(14, 12, 14, 12)
        backup_layout.setSpacing(10)

        backup_header = QHBoxLayout()
        backup_title = QLabel("Loaded save actions", backup_card)
        backup_title.setObjectName("SectionTitle")
        backup_header.addWidget(backup_title)
        backup_header.addStretch(1)
        backup_layout.addLayout(backup_header)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.source_slot_combo = QComboBox(backup_card)
        self.source_slot_combo.setMinimumWidth(380)
        self.target_slot_combo = QComboBox(backup_card)
        self.target_slot_combo.setMinimumWidth(320)

        self.btn_create_slot_backup = QPushButton("Backup Source", backup_card)
        self.btn_create_slot_backup.setObjectName("PrimaryButton")
        self.btn_create_slot_backup.clicked.connect(self._create_selected_slot_backup)
        self.btn_clone_same_save = QPushButton("Copy Within Save", backup_card)
        self.btn_clone_same_save.setObjectName("DangerButton")
        self.btn_clone_same_save.clicked.connect(self._clone_loaded_slot_to_loaded_slot)
        self.btn_copy_to_other_save = QPushButton("Copy Loaded → Other Save…", backup_card)
        self.btn_copy_to_other_save.clicked.connect(self._copy_loaded_slot_to_other_save)

        actions.addWidget(QLabel("Source", backup_card))
        actions.addWidget(self.source_slot_combo, 1)
        actions.addWidget(QLabel("Target", backup_card))
        actions.addWidget(self.target_slot_combo, 1)
        actions.addWidget(self.btn_create_slot_backup)
        actions.addWidget(self.btn_clone_same_save)
        actions.addWidget(self.btn_copy_to_other_save)
        backup_layout.addLayout(actions)
        root.addWidget(backup_card)

        source_card = QFrame(self)
        source_card.setObjectName("Card")
        source_layout = QVBoxLayout(source_card)
        source_layout.setContentsMargins(14, 12, 14, 12)
        source_layout.setSpacing(10)

        source_header = QHBoxLayout()
        source_title = QLabel("Other save → loaded save", source_card)
        source_title.setObjectName("SectionTitle")
        self.external_source_chip = QLabel("No source save selected", source_card)
        self.external_source_chip.setObjectName("Chip")
        self.btn_open_external_source = QPushButton("Open Source Save", source_card)
        self.btn_open_external_source.setObjectName("PrimaryButton")
        self.btn_open_external_source.clicked.connect(self._open_external_source_file)
        source_header.addWidget(source_title)
        source_header.addWidget(self.external_source_chip, 1)
        source_header.addWidget(self.btn_open_external_source)
        source_layout.addLayout(source_header)

        source_actions = QHBoxLayout()
        source_actions.setSpacing(8)
        self.external_source_slot_combo = QComboBox(source_card)
        self.external_source_slot_combo.setMinimumWidth(420)
        self.external_target_slot_combo = QComboBox(source_card)
        self.external_target_slot_combo.setMinimumWidth(380)
        self.btn_copy_external_to_loaded = QPushButton("Copy Other Save Slot → Loaded Slot", source_card)
        self.btn_copy_external_to_loaded.setObjectName("DangerButton")
        self.btn_copy_external_to_loaded.clicked.connect(self._copy_external_source_into_loaded)
        self.btn_export_external_source = QPushButton("Export Source Package", source_card)
        self.btn_export_external_source.clicked.connect(self._export_external_source_slot)
        source_actions.addWidget(QLabel("Other save slot", source_card))
        source_actions.addWidget(self.external_source_slot_combo, 1)
        source_actions.addWidget(QLabel("Loaded target slot", source_card))
        source_actions.addWidget(self.external_target_slot_combo, 1)
        source_actions.addWidget(self.btn_copy_external_to_loaded)
        source_actions.addWidget(self.btn_export_external_source)
        source_layout.addLayout(source_actions)

        root.addWidget(source_card)

        table_card = QFrame(self)
        table_card.setObjectName("Card")
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(14, 12, 14, 12)
        table_layout.setSpacing(10)

        table_actions = QHBoxLayout()
        table_title = QLabel("Saved slot packages", table_card)
        table_title.setObjectName("SectionTitle")
        self.btn_refresh = QPushButton("Refresh", table_card)
        self.btn_refresh.clicked.connect(self.refresh_from_context)
        self.btn_open_folder = QPushButton("Open Slot Backup Folder", table_card)
        self.btn_open_folder.clicked.connect(self._open_backup_folder)
        self.btn_restore_into_loaded = QPushButton("Restore Selected → Loaded", table_card)
        self.btn_restore_into_loaded.setObjectName("DangerButton")
        self.btn_restore_into_loaded.clicked.connect(self._restore_backup_into_loaded_save)
        self.btn_restore_into_other = QPushButton("Restore Selected → Other Save…", table_card)
        self.btn_restore_into_other.clicked.connect(self._restore_backup_into_other_save)
        self.btn_import_package_to_loaded = QPushButton("Import Package → Loaded", table_card)
        self.btn_import_package_to_loaded.clicked.connect(self._import_package_into_loaded_save)
        self.btn_rename_package = QPushButton("Rename Package", table_card)
        self.btn_rename_package.clicked.connect(self._rename_selected_package)
        table_actions.addWidget(table_title)
        table_actions.addStretch(1)
        table_actions.addWidget(self.btn_refresh)
        table_actions.addWidget(self.btn_open_folder)
        table_actions.addWidget(self.btn_restore_into_loaded)
        table_actions.addWidget(self.btn_restore_into_other)
        table_actions.addWidget(self.btn_import_package_to_loaded)
        table_actions.addWidget(self.btn_rename_package)
        table_layout.addLayout(table_actions)

        self.table = QTableWidget(table_card)
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels(["Created", "Label", "Original Slot", "Location", "XP", "Hacksilver", "Size", "File"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.setWordWrap(False)
        self.table.itemSelectionChanged.connect(self._update_buttons)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)
        table_layout.addWidget(self.table, 1)
        root.addWidget(table_card, 1)

        self.status_label = QLabel("Open a save to create slot backups.", self)
        self.status_label.setObjectName("Chip")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

    # ------------------------------------------------------------------
    # Refresh / selection helpers
    # ------------------------------------------------------------------

    def refresh_from_context(self) -> None:
        self._refresh_slot_combos()
        self._refresh_external_source_slots()
        self._refresh_backup_table()
        self._update_buttons()

    def _slot_label(self, slot_index: int, summary: dict) -> str:
        location = str(summary.get("location", "") or "").strip()
        last_played = str(summary.get("last_played", "") or "").strip()
        difficulty = str(summary.get("difficulty_name", "") or "").strip()
        xp = int(summary.get("xp", 0) or 0)
        hs = int(summary.get("hacksilver", 0) or 0)
        title = f"Slot {slot_index}"
        if location:
            title += f" — {location}"
        bits = [b for b in [last_played, difficulty] if b]
        bits.append(f"XP {xp:,}")
        bits.append(f"HS {hs:,}")
        return f"{title}  ·  {' | '.join(bits)}"

    def _refresh_slot_combos(self) -> None:
        save = self.file_ctx.save
        active = int(getattr(save, "active_slot", 1) or 1) if save is not None else 1

        slot_combos = [self.source_slot_combo, self.target_slot_combo]
        if hasattr(self, "external_target_slot_combo"):
            slot_combos.append(self.external_target_slot_combo)
        for combo in slot_combos:
            combo.blockSignals(True)
            combo.clear()

        for slot in gow2018_data.get_save_slots():
            try:
                slot_index = int(slot.get("slot") or 0)
            except Exception:
                continue
            if slot_index <= 0:
                continue
            label = f"Slot {slot_index}"
            if save is not None:
                try:
                    label = self._slot_label(slot_index, summarize_slot(self.file_ctx.current_bytes(), slot_index))
                except Exception:
                    label = f"Slot {slot_index}"
            self.source_slot_combo.addItem(label, slot_index)
            self.target_slot_combo.addItem(label, slot_index)
            if hasattr(self, "external_target_slot_combo"):
                self.external_target_slot_combo.addItem(label, slot_index)

        for combo in slot_combos:
            combo.blockSignals(False)
            for i in range(combo.count()):
                if combo.itemData(i) == active:
                    combo.setCurrentIndex(i)
                    break

    def _refresh_backup_table(self) -> None:
        self._backups = list_slot_backups_for_save(self.file_ctx.path)
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self._backups))
        for r, info in enumerate(self._backups):
            values = [
                info.created_label,
                info.display_label,
                str(info.source_slot or "?"),
                info.location_label,
                info.xp_label,
                info.hacksilver_label,
                info.size_label,
                info.path.name,
            ]
            for c, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
                item.setData(Qt.ItemDataRole.UserRole, str(info.path))
                if c in {2, 4, 5, 6}:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(r, c, item)
        self.table.setSortingEnabled(True)
        if self._backups:
            self.table.selectRow(0)
        self.count_chip.setText(f"{len(self._backups):,} slot backup(s)")
        folder = slot_backup_dir_for_save(self.file_ctx.path)
        if self.file_ctx.path is None:
            self.status_label.setText("No save loaded.")
        elif folder is None:
            self.status_label.setText("No slot backup folder available.")
        else:
            self.status_label.setText(f"Slot backups are stored in {folder}")

    def _selected_source_slot(self) -> Optional[int]:
        return self._combo_slot(self.source_slot_combo)

    def _selected_target_slot(self) -> Optional[int]:
        return self._combo_slot(self.target_slot_combo)

    def _combo_slot(self, combo: QComboBox) -> Optional[int]:
        data = combo.currentData()
        if data is None:
            return None
        try:
            return int(data)
        except Exception:
            return None

    def _selected_external_source_slot(self) -> Optional[int]:
        return self._combo_slot(self.external_source_slot_combo)

    def _selected_external_target_slot(self) -> Optional[int]:
        return self._combo_slot(self.external_target_slot_combo)

    def _slot_looks_used_label(self, summary: dict) -> bool:
        ts = int(summary.get("last_played_raw", 0) or 0)
        location = str(summary.get("location", "") or "").strip()
        xp = int(summary.get("xp", 0) or 0)
        hs = int(summary.get("hacksilver", 0) or 0)
        anchor = bool(summary.get("inventory_anchor_valid", False))
        return bool(946684800 <= ts <= 4102444800 and (location or xp or hs or anchor))

    def _refresh_external_source_slots(self) -> None:
        if not hasattr(self, "external_source_slot_combo"):
            return
        self.external_source_slot_combo.blockSignals(True)
        self.external_source_slot_combo.clear()
        if self.source_save is not None:
            for slot in gow2018_data.get_save_slots():
                try:
                    slot_index = int(slot.get("slot") or 0)
                except Exception:
                    continue
                if slot_index <= 0:
                    continue
                try:
                    summary = summarize_slot(self.source_save.raw, slot_index)
                except Exception:
                    continue
                if not self._slot_looks_used_label(summary):
                    continue
                self.external_source_slot_combo.addItem(self._slot_label(slot_index, summary), slot_index)
        self.external_source_slot_combo.blockSignals(False)

    def _selected_backup_path(self) -> Optional[Path]:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if item is None:
            return None
        data = item.data(Qt.ItemDataRole.UserRole)
        return Path(str(data)) if data else None

    def _default_label_for_slot(self, slot_index: int, raw: bytes | bytearray) -> str:
        try:
            summary = summarize_slot(raw, int(slot_index))
        except Exception:
            summary = {}
        location = str(summary.get("location", "") or "").strip()
        last_played = str(summary.get("last_played", "") or "").strip()
        parts = [f"Slot {int(slot_index):02d}"]
        if location:
            parts.append(location)
        if last_played:
            parts.append(last_played)
        return " - ".join(parts)

    def _ask_package_label(self, slot_index: int, raw: bytes | bytearray) -> Optional[str]:
        default = self._default_label_for_slot(slot_index, raw)
        label, ok = QInputDialog.getText(
            self,
            "Label slot package",
            "Package label for this slot backup/export. This labels the .gow2018slot file only; the actual save-menu slot is controlled by the target slot number.",
            text=default,
        )
        if not ok:
            return None
        clean = str(label or "").strip()
        return clean or default

    def _open_backup_folder(self) -> None:
        folder = slot_backup_dir_for_save(self.file_ctx.path)
        if folder is None:
            return
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    # ------------------------------------------------------------------
    # Slot backup actions
    # ------------------------------------------------------------------

    def _open_external_source_file(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Open source GoW 2018 memory.dat",
            "",
            "GoW 2018 Save (*.dat);;All Files (*)",
        )
        if not path_str:
            return
        path = Path(path_str)
        try:
            save = SaveFile.from_path(path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Source load failed", f"Could not load source save:\n{exc}")
            return
        self.source_path = path
        self.source_save = save
        self.external_source_chip.setText(path.name)
        self.external_source_chip.setObjectName("GoodChip")
        self.external_source_chip.style().unpolish(self.external_source_chip)
        self.external_source_chip.style().polish(self.external_source_chip)
        self._refresh_external_source_slots()
        self._update_buttons()
        self.status_label.setText(f"Loaded source {path.name}. Choose a source slot and target slot.")

    def _copy_external_source_into_loaded(self) -> None:
        if self.file_ctx.save is None:
            QMessageBox.information(self, "No target loaded", "Open the target memory.dat first.")
            return
        if self.source_path is None:
            QMessageBox.information(self, "No source loaded", "Open a source memory.dat first.")
            return
        source_slot = self._selected_external_source_slot()
        target_slot = self._selected_external_target_slot()
        if source_slot is None or target_slot is None:
            QMessageBox.information(self, "Missing slot", "Select both source and target slots.")
            return
        if self.file_ctx.path is not None and self.source_path.resolve() == self.file_ctx.path.resolve():
            QMessageBox.information(self, "Use loaded-save copy", "That source is already loaded. Use Copy Within Save instead.")
            return
        if not self._confirm_slot_replace(
            "Copy source slot into loaded save?",
            f"{self.source_path.name} slot {source_slot}",
            f"Loaded save slot {target_slot}",
        ):
            return
        try:
            new_raw, result = copy_slot_from_memory_dat_into_bytes(
                self.source_path,
                source_slot,
                self.file_ctx.current_bytes(),
                target_slot,
            )
            self._apply_new_raw_to_loaded_save(new_raw, target_slot, result.summary)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Slot transfer failed", f"Could not copy source slot into loaded save:\n{exc}")

    def _export_external_source_slot(self) -> None:
        if self.source_path is None:
            QMessageBox.information(self, "No source loaded", "Open a source memory.dat first.")
            return
        source_slot = self._selected_external_source_slot()
        if source_slot is None:
            QMessageBox.information(self, "No source slot", "Select a used source slot first.")
            return
        default_name = f"{self.source_path.stem}.slot{source_slot}{DEFAULT_EXTENSION}"
        out_str, _ = QFileDialog.getSaveFileName(
            self,
            "Export source slot package",
            str(self.source_path.with_name(default_name)),
            "GoW Slot Package (*.gow2018slot);;All Files (*)",
        )
        if not out_str:
            return
        label = self._ask_package_label(source_slot, self.source_path.read_bytes())
        if label is None:
            return
        try:
            package = write_slot_package_from_memory_dat(self.source_path, source_slot, Path(out_str), display_label=label)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Export failed", f"Could not export slot package:\n{exc}")
            return
        self.status_label.setText(
            f"Exported {self.source_path.name} slot {source_slot} as '{package.display_label}' ({Path(out_str).name}, {package.block_size:,} bytes)."
        )

    def _create_selected_slot_backup(self) -> None:
        save = self.file_ctx.save
        path = self.file_ctx.path
        source_slot = self._selected_source_slot()
        if save is None or path is None or source_slot is None:
            QMessageBox.information(self, "No save loaded", "Open a memory.dat and select a source slot first.")
            return
        label = self._ask_package_label(source_slot, self.file_ctx.current_bytes())
        if label is None:
            return
        try:
            info = create_slot_backup(self.file_ctx.current_bytes(), path, source_slot, display_label=label)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Slot backup failed", f"Could not create slot backup:\n{exc}")
            return
        self.refresh_from_context()
        self.status_label.setText(f"Backed up slot {source_slot} as '{info.display_label}' to {info.path.name}.")

    def _confirm_slot_replace(self, title: str, source_text: str, target_text: str, *, writes_disk: bool = False) -> bool:
        disk_note = "\n\nThis writes the target file immediately and creates a rollback .bak first." if writes_disk else "\n\nThis is staged in memory. Use Save/Save As to write it with change review."
        result = QMessageBox.warning(
            self,
            title,
            f"This replaces the entire target slot block.\n\nSource: {source_text}\nTarget: {target_text}{disk_note}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return result == QMessageBox.StandardButton.Yes

    def _apply_new_raw_to_loaded_save(self, new_raw: bytes, target_slot: int, summary: str) -> None:
        save = self.file_ctx.save
        if save is None:
            raise RuntimeError("No loaded save to update.")
        save.raw = new_raw
        save.set_active_slot(int(target_slot))
        self.file_ctx.mark_dirty()
        self.refresh_from_context()
        if self.on_restored is not None:
            self.on_restored()
        self.status_label.setText(summary)

    def _clone_loaded_slot_to_loaded_slot(self) -> None:
        if self.file_ctx.save is None:
            QMessageBox.information(self, "No save loaded", "Open a memory.dat first.")
            return
        source_slot = self._selected_source_slot()
        target_slot = self._selected_target_slot()
        if source_slot is None or target_slot is None:
            QMessageBox.information(self, "Missing slot", "Select both source and target slots.")
            return
        if source_slot == target_slot:
            QMessageBox.information(self, "Same slot", "Choose a different target slot.")
            return
        if not self._confirm_slot_replace(
            "Copy slot inside loaded save?",
            f"Loaded save slot {source_slot}",
            f"Loaded save slot {target_slot}",
        ):
            return
        try:
            new_raw, result = clone_slot_within_bytes(
                self.file_ctx.current_bytes(),
                source_slot,
                target_slot,
                source_path=self.file_ctx.path,
            )
            self._apply_new_raw_to_loaded_save(new_raw, target_slot, result.summary)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Slot copy failed", f"Could not copy slot:\n{exc}")

    def _rename_selected_package(self) -> None:
        backup = self._selected_backup_path()
        if backup is None:
            QMessageBox.information(self, "No slot package", "Select a saved slot package first.")
            return
        current = ""
        try:
            for info in self._backups:
                if info.path == backup:
                    current = info.display_label
                    break
        except Exception:
            current = backup.stem
        label, ok = QInputDialog.getText(
            self,
            "Rename slot package",
            "Package label. This does not edit save bytes; it only changes the .gow2018slot metadata shown in this table.",
            text=current or backup.stem,
        )
        if not ok:
            return
        clean = str(label or "").strip()
        if not clean:
            QMessageBox.information(self, "Empty label", "Enter a label before saving.")
            return
        try:
            update_slot_package_label(backup, clean)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Rename failed", f"Could not rename slot package:\n{exc}")
            return
        self.refresh_from_context()
        self.status_label.setText(f"Renamed package to '{clean}'.")

    def _restore_backup_into_loaded_save(self) -> None:
        if self.file_ctx.save is None:
            QMessageBox.information(self, "No save loaded", "Open the target memory.dat first.")
            return
        backup = self._selected_backup_path()
        target_slot = self._selected_target_slot()
        if backup is None or target_slot is None:
            QMessageBox.information(self, "Missing selection", "Select a slot backup and a target slot.")
            return
        if not self._confirm_slot_replace(
            "Restore slot backup?",
            backup.name,
            f"Loaded save slot {target_slot}",
        ):
            return
        try:
            new_raw, result = import_slot_backup_into_bytes(self.file_ctx.current_bytes(), backup, target_slot)
            self._apply_new_raw_to_loaded_save(new_raw, target_slot, result.summary)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Restore failed", f"Could not restore slot backup:\n{exc}")

    def _choose_other_save_and_slot(self, title: str) -> tuple[Optional[Path], Optional[int]]:
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            title,
            "",
            "GoW 2018 Save (*.dat);;All Files (*)",
        )
        if not path_str:
            return None, None
        default_slot = self._selected_target_slot() or 1
        max_slot = max(1, len(gow2018_data.get_save_slots()))
        slot, ok = QInputDialog.getInt(
            self,
            "Target slot in other save",
            "Choose the physical slot number to replace in the selected target memory.dat.",
            int(default_slot),
            1,
            max_slot,
            1,
        )
        if not ok:
            return Path(path_str), None
        return Path(path_str), int(slot)

    def _import_package_into_loaded_save(self) -> None:
        if self.file_ctx.save is None:
            QMessageBox.information(self, "No save loaded", "Open the target memory.dat first.")
            return
        target_slot = self._selected_target_slot()
        if target_slot is None:
            QMessageBox.information(self, "No target slot", "Select a target slot first.")
            return
        pkg_str, _ = QFileDialog.getOpenFileName(
            self,
            "Import GoW 2018 slot package",
            "",
            "GoW Slot Package (*.gow2018slot);;All Files (*)",
        )
        if not pkg_str:
            return
        package_path = Path(pkg_str)
        if not self._confirm_slot_replace(
            "Import slot package into loaded save?",
            package_path.name,
            f"Loaded save slot {target_slot}",
        ):
            return
        try:
            new_raw, result = import_slot_package_file_into_bytes(
                self.file_ctx.current_bytes(),
                package_path,
                target_slot,
            )
            self._apply_new_raw_to_loaded_save(new_raw, target_slot, result.summary)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Import failed", f"Could not import slot package:\n{exc}")

    def _restore_backup_into_other_save(self) -> None:
        backup = self._selected_backup_path()
        if backup is None:
            QMessageBox.information(self, "No slot backup", "Select a slot backup first.")
            return
        target_path, target_slot = self._choose_other_save_and_slot("Choose target memory.dat")
        if target_path is None or target_slot is None:
            return
        if not self._confirm_slot_replace(
            "Restore backup into another save?",
            backup.name,
            f"{target_path.name} slot {target_slot}",
            writes_disk=True,
        ):
            return
        try:
            rollback = write_slot_backup_to_memory_dat(backup, target_path, target_slot)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "External restore failed", f"Could not write slot backup to target save:\n{exc}")
            return
        self.status_label.setText(
            f"Wrote {backup.name} into {target_path.name} slot {target_slot}. Rollback backup: {rollback.name}"
        )

    def _copy_loaded_slot_to_other_save(self) -> None:
        save = self.file_ctx.save
        source_slot = self._selected_source_slot()
        if save is None or source_slot is None:
            QMessageBox.information(self, "No save loaded", "Open a source memory.dat and select a source slot first.")
            return
        target_path, target_slot = self._choose_other_save_and_slot("Choose target memory.dat")
        if target_path is None or target_slot is None:
            return
        if self.file_ctx.path is not None and Path(target_path).resolve() == Path(self.file_ctx.path).resolve():
            QMessageBox.information(self, "Use loaded-save copy", "That target is already loaded. Use Copy To Slot instead.")
            return
        if not self._confirm_slot_replace(
            "Copy loaded slot into another save?",
            f"Loaded save slot {source_slot}",
            f"{target_path.name} slot {target_slot}",
            writes_disk=True,
        ):
            return
        try:
            rollback = copy_slot_to_memory_dat(
                self.file_ctx.current_bytes(),
                source_slot,
                target_path,
                target_slot,
                source_path=self.file_ctx.path,
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "External slot copy failed", f"Could not write slot to target save:\n{exc}")
            return
        self.status_label.setText(
            f"Copied loaded slot {source_slot} into {target_path.name} slot {target_slot}. Rollback backup: {rollback.name}"
        )

    def _update_buttons(self) -> None:
        has_save = self.file_ctx.save is not None and self.file_ctx.path is not None
        has_backup = self._selected_backup_path() is not None
        has_slots = self.source_slot_combo.count() > 0 and self.target_slot_combo.count() > 0
        self.source_slot_combo.setEnabled(has_save)
        self.target_slot_combo.setEnabled(has_save)
        self.btn_create_slot_backup.setEnabled(has_save and has_slots)
        self.btn_clone_same_save.setEnabled(has_save and has_slots)
        self.btn_copy_to_other_save.setEnabled(has_save and has_slots)
        self.btn_open_folder.setEnabled(self.file_ctx.path is not None)
        has_external_source = self.source_path is not None and self.external_source_slot_combo.count() > 0
        self.external_source_slot_combo.setEnabled(has_external_source)
        self.btn_copy_external_to_loaded.setEnabled(has_save and has_external_source and has_slots)
        self.btn_export_external_source.setEnabled(has_external_source)
        if hasattr(self, "external_target_slot_combo"):
            self.external_target_slot_combo.setEnabled(has_save)
        self.btn_restore_into_loaded.setEnabled(has_save and has_backup)
        self.btn_restore_into_other.setEnabled(has_backup)
        self.btn_import_package_to_loaded.setEnabled(has_save and has_slots)
        self.btn_rename_package.setEnabled(has_backup)
