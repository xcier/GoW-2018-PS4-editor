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
)

from app.core.file_context import FileContext
from app.ui.tabs.stats_tab import StatsTab
from app.ui.tabs.inventory_tab import InventoryTab
from app.ui.tabs.about_tab import AboutTab
from app.ui.tabs.settings_tab import SettingsTab


class MainWindow(QMainWindow):
    def __init__(self, file_ctx: FileContext, parent: Optional[Widget] = None) -> None:
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

        # top tab buttons
        tabs_row = QHBoxLayout()
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
        root.addLayout(tabs_row)

        # stacked pages
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
                    background-color: #3c3c3c;
                    color: #f0f0f0;
                    border: 1px solid #555555;
                    padding: 4px 8px;
                }
                QPushButton:checked {
                    background-color: #555555;
                }
                QPushButton:hover {
                    background-color: #505050;
                }
                QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
                    background-color: #3c3c3c;
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
            # reset to default
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
            # (future: self.stats_tab.apply_to_save() if you add it)

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
            # (future: self.stats_tab.apply_to_save() if needed)

            # write to the chosen path
            self.file_ctx.save_to_disk(path)
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to save:\n{exc}")
            return

        self._set_status(f"Saved as: {path.name}")
