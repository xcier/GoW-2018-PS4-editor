# app/ui/main_window.py
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFileDialog,
    QMessageBox,
    QStatusBar,
    QMenuBar,
    QMenu,
    QStackedWidget,
    QPushButton,
    QButtonGroup,
    QLabel,
    QComboBox,
)

from app.core.file_context import FileContext
from app.core import gow2018_data

from app.ui.tabs.stats_tab import StatsTab
from app.ui.tabs.inventory_tab import InventoryTab
from app.ui.tabs.about_tab import AboutTab
from app.ui.tabs.settings_tab import SettingsTab


class MainWindow(QMainWindow):
    """
    Main application window.

    The Slot combo is populated from gow2018_slots.json, and when a save
    is loaded we decorate each entry with information pulled out of
    memory.dat (location text, last played time, XP, Hacksilver).

    After a save is loaded, slots are *sorted by last-played time* so
    the most recent save appears at the top of the list.
    """

    def __init__(self, file_ctx: FileContext, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("GoW 2018 Save Editor - ProtoBuffers")

        self.file_ctx = file_ctx

        # start in dark mode
        self._dark_mode = True

        self._init_menu()
        self._init_ui()
        self._init_status_bar()
        self._apply_theme()

    # ------------------------------------------------------------------
    # Menus
    # ------------------------------------------------------------------

    def _init_menu(self) -> None:
        bar = QMenuBar(self)

        file_menu = QMenu("&File", bar)

        act_open = file_menu.addAction("Open...")
        act_open.triggered.connect(self._open_file)

        act_save = file_menu.addAction("Save")
        act_save.triggered.connect(self._save)

        act_save_as = file_menu.addAction("Save As...")
        act_save_as.triggered.connect(self._save_as)

        file_menu.addSeparator()
        act_exit = file_menu.addAction("Exit")
        act_exit.triggered.connect(self.close)

        bar.addMenu(file_menu)
        self.setMenuBar(bar)

    # ------------------------------------------------------------------
    # Central UI
    # ------------------------------------------------------------------

    def _init_ui(self) -> None:
        central = QWidget(self)
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Top row: tab buttons + slot selector
        tabs_row = QHBoxLayout()
        tabs_row.setContentsMargins(6, 6, 6, 6)
        tabs_row.setSpacing(6)

        self.tab_buttons = QButtonGroup(self)
        self.tab_buttons.setExclusive(True)

        def make_tab_btn(label: str, idx: int) -> QPushButton:
            btn = QPushButton(label)
            btn.setCheckable(True)
            if idx == 0:
                btn.setChecked(True)
            self.tab_buttons.addButton(btn, idx)
            tabs_row.addWidget(btn)
            return btn

        make_tab_btn("Stats", 0)
        make_tab_btn("Inventory", 1)
        make_tab_btn("Settings", 2)
        make_tab_btn("About", 3)

        tabs_row.addStretch(1)

        # Slot selector area
        self.slot_label = QLabel("Slot:", self)
        self.slot_combo = QComboBox(self)
        self.slot_combo.setEnabled(False)
        self.slot_combo.setMinimumWidth(260)
        self.slot_combo.currentIndexChanged.connect(self._on_slot_changed)

        tabs_row.addWidget(self.slot_label)
        tabs_row.addWidget(self.slot_combo)

        root.addLayout(tabs_row)

        # Stacked tab pages
        self.stack = QStackedWidget(self)
        root.addWidget(self.stack)

        self.stats_tab = StatsTab(self.file_ctx, self)
        self.inventory_tab = InventoryTab(self.file_ctx, self)
        self.settings_tab = SettingsTab(self, self)
        self.about_tab = AboutTab(self)

        self.stack.addWidget(self.stats_tab)      # index 0
        self.stack.addWidget(self.inventory_tab)  # index 1
        self.stack.addWidget(self.settings_tab)   # index 2
        self.stack.addWidget(self.about_tab)      # index 3

        self.tab_buttons.idClicked.connect(self.stack.setCurrentIndex)

        # Populate the combo with bare slot numbers from the DB; once a save
        # is loaded we decorate them with location / time and sort them.
        self._populate_slot_combo()

    # ------------------------------------------------------------------
    # Slot handling
    # ------------------------------------------------------------------

    def _populate_slot_combo(self) -> None:
        """
        Fill the slot combo with the slot numbers we know about from
        gow2018_slots.json. This is static metadata, so we do it once
        at startup.
        """
        slots = gow2018_data.get_save_slots()

        self.slot_combo.blockSignals(True)
        self.slot_combo.clear()

        for slot in slots:
            try:
                num = int(slot.get("slot") or 0)
            except Exception:
                continue
            if num <= 0:
                continue

            # Initial label is just the slot index; once a save is loaded
            # we replace this with a richer summary string and reorder.
            label = f"{num}"
            self.slot_combo.addItem(label, num)

        self.slot_combo.blockSignals(False)

    def _sync_slot_combo_to_save(self) -> None:
        """
        Make sure the Slot combo reflects the active_slot in the current
        SaveFile (and enable/disable it accordingly).
        """
        save = self.file_ctx.save
        if save is None:
            self.slot_combo.blockSignals(True)
            self.slot_combo.setCurrentIndex(-1)
            self.slot_combo.setEnabled(False)
            self.slot_combo.blockSignals(False)
            return

        active = getattr(save, "active_slot", 1)
        idx = 0
        for i in range(self.slot_combo.count()):
            if self.slot_combo.itemData(i) == active:
                idx = i
                break

        self.slot_combo.blockSignals(True)
        self.slot_combo.setCurrentIndex(idx)
        self.slot_combo.setEnabled(True)
        self.slot_combo.blockSignals(False)

    def _refresh_slot_summaries(self) -> None:
        """
        Build human-readable labels and *reorder* combo items to include
        info pulled from the save file:

            "slot - location | last-played | XP X, HS Y"

        Slots are sorted by last-played timestamp (newest first). Slots
        with no valid timestamp (e.g. never-used / unmapped) sink to the
        bottom.
        """
        save = self.file_ctx.save
        if save is None or not hasattr(save, "summarize_slot"):
            return

        # Collect (slot_index, summary) for every item currently in the combo
        items = []
        for i in range(self.slot_combo.count()):
            slot_num = self.slot_combo.itemData(i)
            if slot_num is None:
                continue

            try:
                slot_index = int(slot_num)
            except Exception:
                continue

            summary = save.summarize_slot(slot_index)
            items.append((slot_index, summary))

        # Helper to get raw timestamp from a summary, treating missing/invalid
        # values as 0 so "never used" slots sink to the bottom.
        def ts_from_summary(summary):
            if not summary:
                return 0
            raw = summary.get("last_played_raw", 0)
            try:
                return int(raw)
            except Exception:
                return 0

        # Sort by last_played_raw descending (newest first).
        items.sort(key=lambda pair: ts_from_summary(pair[1]), reverse=True)

        # Remember which slot is currently active so we can re-select it
        # after rebuilding the combo box in the new order.
        save_active = getattr(save, "active_slot", None)

        self.slot_combo.blockSignals(True)
        self.slot_combo.clear()

        for slot_index, summary in items:
            if not summary:
                # Fallback: just the slot number for completely unknown slots
                label = str(slot_index)
            else:
                diff_name = summary.get("difficulty_name", "Story")
                xp = summary.get("xp", 0)
                hs = summary.get("hacksilver", 0)
                location = summary.get("location", "")
                last_played = summary.get("last_played", "")

                # Try to keep the label reasonably short but informative.
                # Example:
                #   "1 - Midgard - Wildwoods | 2018-04-24 04:10 | XP 17, HS 508"
                parts = [str(slot_index)]
                if location:
                    parts.append(location)
                if last_played:
                    parts.append(last_played)
                # Core stats tail
                parts.append(f"XP {xp}, HS {hs}")

                if len(parts) >= 2:
                    head = " - ".join(parts[:2])
                    tail = " | ".join(parts[2:])
                    label = f"{head} | {tail}" if tail else head
                else:
                    label = parts[0]

            self.slot_combo.addItem(label, slot_index)

        self.slot_combo.blockSignals(False)

        # Ensure the SaveFile.active_slot remains selected in the new order.
        if save_active is not None:
            self._sync_slot_combo_to_save()

    def refresh_slot_summary_labels(self) -> None:
        """Public hook (for tabs) to refresh Slot combo labels."""
        self._refresh_slot_summaries()

    def _on_slot_changed(self) -> None:
        """
        User changed the slot combo:

        - Switch the SaveFile.active_slot to the new one.
        - Ask tabs to refresh their view.
        """
        save = self.file_ctx.save
        if save is None:
            return

        data = self.slot_combo.currentData()
        if data is None:
            data = self.slot_combo.currentIndex() + 1

        try:
            new_slot = int(data)
        except Exception:
            new_slot = 1

        if hasattr(save, "set_active_slot"):
            save.set_active_slot(new_slot)

        # Ensure combo shows the actual active_slot (in case it was clamped)
        self._sync_slot_combo_to_save()

        # Refresh summaries (XP/HS/diff/location/time may differ per slot)
        self._refresh_slot_summaries()

        # Refresh tabs so they show values from the new slot
        self.stats_tab.refresh_from_context()
        self.inventory_tab.refresh_from_context()

        self._set_status(f"Switched to slot {new_slot}")

    # ------------------------------------------------------------------
    # Status bar
    # ------------------------------------------------------------------

    def _init_status_bar(self) -> None:
        status = QStatusBar(self)
        self.setStatusBar(status)
        self._set_status("Ready")

    def _set_status(self, text: str) -> None:
        if self.statusBar():
            self.statusBar().showMessage(text, 5000)

    # ------------------------------------------------------------------
    # Theme / dark mode
    # ------------------------------------------------------------------

    def dark_mode_enabled(self) -> bool:
        return self._dark_mode

    def set_dark_mode(self, enabled: bool) -> None:
        if self._dark_mode == enabled:
            return
        self._dark_mode = enabled
        self._apply_theme()

    def _apply_theme(self) -> None:
        app = QApplication.instance()
        if app is None:
            return

        if self._dark_mode:
            app.setStyleSheet(
                """
                QMainWindow, QWidget {
                    background-color: #2b2b2b;
                    color: #f0f0f0;
                }
                QMenuBar, QMenu {
                    background-color: #323232;
                    color: #f0f0f0;
                }
                QMenu::item:selected {
                    background-color: #444444;
                }
                QStatusBar {
                    background-color: #323232;
                    color: #f0f0f0;
                }
                QPushButton {
                    background-color: #3a3a3a;
                    border: 1px solid #555555;
                    padding: 4px 8px;
                }
                QPushButton:hover {
                    background-color: #4a4a4a;
                }
                QLineEdit, QComboBox, QSpinBox, QTextEdit, QPlainTextEdit {
                    background-color: #3a3a3a;
                    color: #f0f0f0;
                    border: 1px solid #555555;
                }
                QTableWidget, QTreeView, QTableView {
                    background-color: #323232;
                    color: #f0f0f0;
                    gridline-color: #555555;
                }
                QHeaderView::section {
                    background-color: #3a3a3a;
                    color: #f0f0f0;
                    border: 1px solid #555555;
                }
                QScrollBar:vertical, QScrollBar:horizontal {
                    background-color: #2b2b2b;
                }
                """
            )
        else:
            app.setStyleSheet("")

    # ------------------------------------------------------------------
    # File operations
    # ------------------------------------------------------------------

    def _open_file(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Open GoW 2018 Save",
            "",
            "GoW 2018 Save (*.dat);;All Files (*)",
        )
        if not path_str:
            return

        path = Path(path_str)
        try:
            self.file_ctx.load(path)
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to load save:\n{exc}")
            return

        # After a successful load, sync the slot combo to the save
        self._sync_slot_combo_to_save()
        # And decorate + reorder each slot with live info from the save
        self._refresh_slot_summaries()

        # Tabs know how to pull from FileContext
        self.stats_tab.refresh_from_context()
        self.inventory_tab.refresh_from_context()
        self._set_status(f"Loaded: {path.name}")

    def _save(self) -> None:
        """
        Save to the current path. Before writing to disk we push any
        tab edits (inventory, stats, etc.) back into the underlying
        FileContext/save data.
        """
        if self.file_ctx.path is None:
            return self._save_as()

        try:
            # --- commit tab changes into FileContext / save.raw ---
            self.inventory_tab.apply_to_save()
            # stats are committed per-edit via SaveFile.commit_core_stats()

            # now flush to disk
            self.file_ctx.save_to_disk()
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to save:\n{exc}")
            return

        self._set_status("Save successful")

    def _save_as(self) -> None:
        """
        Save to a new path. Same idea as _save(): push edits into
        the FileContext first, then write to the selected file path.
        """
        path_str, _ = QFileDialog.getSaveFileName(
            self,
            "Save GoW 2018 Save As",
            "",
            "GoW 2018 Save (*.dat);;All Files (*)",
        )
        if not path_str:
            return

        path = Path(path_str)

        try:
            # --- commit tab changes into FileContext / save.raw ---
            self.inventory_tab.apply_to_save()
            # stats are committed per-edit via SaveFile.commit_core_stats()

            # write to the chosen path
            self.file_ctx.save_to_disk(path)
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to save:\n{exc}")
            return

        self._set_status(f"Saved as: {path.name}")
