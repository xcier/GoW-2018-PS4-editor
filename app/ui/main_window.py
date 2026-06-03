# app/ui/main_window.py
from __future__ import annotations

from pathlib import Path
from typing import Optional
import json

from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QAction, QKeySequence
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
    QFrame,
    QSizePolicy,
)

from app import __about__
from app.core.file_context import FileContext
from app.core import gow2018_data

from app.ui.tabs.stats_tab import StatsTab
from app.ui.tabs.slot_manager_tab import SlotManagerTab
from app.ui.tabs.inventory_tab import InventoryTab
from app.ui.tabs.backup_tab import BackupManagerTab
from app.ui.tabs.hex_tab import HexEditorTab
from app.ui.tabs.about_tab import AboutTab
from app.ui.tabs.settings_tab import SettingsTab
from app.ui.theme import (
    DEFAULT_THEME,
    apply_app_theme,
    is_dark_theme,
    theme_display_name,
    theme_names,
)


class MainWindow(QMainWindow):
    """Main application shell with a modern side rail and safe save workflow."""

    PAGE_META = {
        0: ("Dashboard", "Edit active-slot XP, hacksilver, difficulty, and armor stat helpers."),
        1: ("Slot Manager", "Review all 20 physical save slots and open the exact one you want."),
        2: ("Inventory", "Validated item/resource table editor for the active save slot."),
        3: ("Slot Tools", "Back up, restore, copy, import, and transfer complete physical save slots."),
        4: ("Hex Editor", "Guarded raw byte viewer with offset jumps, search, and explicit patch staging."),
        5: ("Settings", "Appearance, safety defaults, and editor preferences."),
        6: ("About", "Credits, data sources, and save-safety notes."),
    }

    def __init__(self, file_ctx: FileContext, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(__about__.__display_name__)
        self.setMinimumSize(1240, 760)
        self.resize(1280, 800)

        self.file_ctx = file_ctx
        self._settings = QSettings(__about__.__organization__, __about__.__app_name__)
        self._theme_name = self._load_theme_name()
        self._recent_files = self._load_recent_files()
        self._stale_pages: set[int] = set()

        self._init_menu()
        self._init_ui()
        self.file_ctx.on_dirty_changed = lambda _dirty: self._update_title()
        self._init_status_bar()
        self._apply_theme()
        self._restore_window_settings()
        self._update_title()

    # ------------------------------------------------------------------
    # Menus
    # ------------------------------------------------------------------

    def _init_menu(self) -> None:
        bar = QMenuBar(self)

        file_menu = QMenu("&File", bar)

        self.act_open = QAction("Open...", self)
        self.act_open.setShortcut(QKeySequence.StandardKey.Open)
        self.act_open.triggered.connect(self._open_file)
        file_menu.addAction(self.act_open)

        self.act_save = QAction("Save", self)
        self.act_save.setShortcut(QKeySequence.StandardKey.Save)
        self.act_save.triggered.connect(self._save)
        file_menu.addAction(self.act_save)

        self.act_save_as = QAction("Save As...", self)
        self.act_save_as.setShortcut(QKeySequence.StandardKey.SaveAs)
        self.act_save_as.triggered.connect(self._save_as)
        file_menu.addAction(self.act_save_as)

        file_menu.addSeparator()
        self.recent_menu = QMenu("Open Recent", file_menu)
        self._recent_actions: list[QAction] = []
        for _ in range(8):
            action = QAction("", self)
            action.setVisible(False)
            action.triggered.connect(lambda _checked=False, a=action: self._open_recent_file(Path(a.data())))
            self._recent_actions.append(action)
            self.recent_menu.addAction(action)
        self.recent_menu.addSeparator()
        self.act_clear_recent = QAction("Clear Recent Saves", self)
        self.act_clear_recent.triggered.connect(self._clear_recent_files)
        self.recent_menu.addAction(self.act_clear_recent)
        file_menu.addMenu(self.recent_menu)
        self._refresh_recent_menu()

        file_menu.addSeparator()
        act_exit = QAction("Exit", self)
        act_exit.triggered.connect(self.close)
        file_menu.addAction(act_exit)

        view_menu = QMenu("&View", bar)
        self.act_next_theme = QAction("Next Theme", self)
        self.act_next_theme.setShortcut("Ctrl+T")
        self.act_next_theme.triggered.connect(self.cycle_theme)
        view_menu.addAction(self.act_next_theme)

        self.act_toggle_theme = QAction("Toggle Dark / Light", self)
        self.act_toggle_theme.setShortcut("Ctrl+D")
        self.act_toggle_theme.triggered.connect(lambda: self.set_dark_mode(not self.dark_mode_enabled()))
        view_menu.addAction(self.act_toggle_theme)

        bar.addMenu(file_menu)
        bar.addMenu(view_menu)
        self.setMenuBar(bar)

    # ------------------------------------------------------------------
    # Central UI
    # ------------------------------------------------------------------

    def _init_ui(self) -> None:
        central = QWidget(self)
        central.setObjectName("AppRoot")
        self.setCentralWidget(central)

        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        sidebar = QFrame(self)
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(284)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(20, 22, 20, 20)
        side_layout.setSpacing(14)

        brand = QFrame(sidebar)
        brand.setObjectName("BrandCard")
        brand_layout = QHBoxLayout(brand)
        brand_layout.setContentsMargins(14, 14, 14, 14)
        brand_layout.setSpacing(12)

        badge = QLabel("Ω", brand)
        badge.setObjectName("BrandBadge")
        badge.setFixedSize(52, 52)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_layout.addWidget(badge)

        brand_text = QVBoxLayout()
        brand_text.setSpacing(2)
        title = QLabel("GoW Save Lab", brand)
        title.setObjectName("AppTitle")
        subtitle = QLabel("2018 PS4 memory.dat", brand)
        subtitle.setObjectName("AppSubtitle")
        subtitle.setWordWrap(True)
        brand_text.addWidget(title)
        brand_text.addWidget(subtitle)
        brand_layout.addLayout(brand_text, 1)
        side_layout.addWidget(brand)

        self.tab_buttons = QButtonGroup(self)
        self.tab_buttons.setExclusive(True)

        def add_nav(label: str, idx: int) -> QPushButton:
            btn = QPushButton(label, sidebar)
            btn.setObjectName("NavButton")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumHeight(48)
            if idx == 0:
                btn.setChecked(True)
            self.tab_buttons.addButton(btn, idx)
            side_layout.addWidget(btn)
            return btn

        add_nav("▣  Dashboard", 0)
        add_nav("▤  Slot Manager", 1)
        add_nav("◈  Inventory", 2)
        add_nav("⇄  Slot Tools", 3)
        add_nav("⌘  Hex Editor", 4)
        add_nav("⚙  Settings", 5)
        add_nav("ⓘ  About", 6)

        side_layout.addStretch(1)

        footer = QFrame(sidebar)
        footer.setObjectName("SidebarFooter")
        footer_layout = QVBoxLayout(footer)
        footer_layout.setContentsMargins(14, 14, 14, 14)
        footer_layout.setSpacing(10)

        footer_title = QLabel("Save State", footer)
        footer_title.setObjectName("TinyLabel")
        footer_layout.addWidget(footer_title)

        self.file_chip = QLabel("No save loaded", footer)
        self.file_chip.setObjectName("Chip")
        self.file_chip.setWordWrap(True)
        footer_layout.addWidget(self.file_chip)

        self.dirty_chip = QLabel("Clean", footer)
        self.dirty_chip.setObjectName("GoodChip")
        footer_layout.addWidget(self.dirty_chip)

        self.btn_open_sidebar = QPushButton("Open Save", footer)
        self.btn_open_sidebar.setObjectName("PrimaryButton")
        self.btn_open_sidebar.clicked.connect(self._open_file)
        footer_layout.addWidget(self.btn_open_sidebar)

        footer_actions = QHBoxLayout()
        footer_actions.setSpacing(8)
        self.btn_save_sidebar = QPushButton("Save", footer)
        self.btn_save_sidebar.clicked.connect(self._save)
        self.btn_save_as_sidebar = QPushButton("Save As", footer)
        self.btn_save_as_sidebar.setObjectName("SubtleButton")
        self.btn_save_as_sidebar.clicked.connect(self._save_as)
        footer_actions.addWidget(self.btn_save_sidebar)
        footer_actions.addWidget(self.btn_save_as_sidebar)
        footer_layout.addLayout(footer_actions)

        side_layout.addWidget(footer)
        root.addWidget(sidebar)

        content = QWidget(self)
        content.setObjectName("ContentPane")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 20, 24, 20)
        content_layout.setSpacing(18)
        root.addWidget(content, 1)

        header = QFrame(content)
        header.setObjectName("Header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(22, 18, 22, 18)
        header_layout.setSpacing(18)

        header_text = QVBoxLayout()
        header_text.setSpacing(3)
        self.page_eyebrow = QLabel("SAFE EDITING WORKSPACE", header)
        self.page_eyebrow.setObjectName("PageEyebrow")
        self.page_title = QLabel("Dashboard", header)
        self.page_title.setObjectName("PageTitle")
        self.page_subtitle = QLabel(self.PAGE_META[0][1], header)
        self.page_subtitle.setObjectName("PageSubtitle")
        self.page_subtitle.setWordWrap(True)
        header_text.addWidget(self.page_eyebrow)
        header_text.addWidget(self.page_title)
        header_text.addWidget(self.page_subtitle)
        header_layout.addLayout(header_text, 1)

        slot_area = QVBoxLayout()
        slot_area.setSpacing(6)
        slot_header = QHBoxLayout()
        self.slot_label = QLabel("Active Slot", header)
        self.slot_label.setObjectName("TinyLabel")
        self.slot_badge = QLabel("Auto", header)
        self.slot_badge.setObjectName("GoodChip")
        slot_header.addWidget(self.slot_label)
        slot_header.addStretch(1)
        slot_header.addWidget(self.slot_badge)
        self.slot_combo = QComboBox(header)
        self.slot_combo.setEnabled(False)
        self.slot_combo.setMinimumWidth(430)
        self.slot_combo.currentIndexChanged.connect(self._on_slot_changed)
        self.slot_summary = QLabel("Open a save to inspect slots.", header)
        self.slot_summary.setObjectName("MutedLabel")
        self.slot_summary.setWordWrap(True)
        slot_area.addLayout(slot_header)
        slot_area.addWidget(self.slot_combo)
        slot_area.addWidget(self.slot_summary)
        header_layout.addLayout(slot_area)

        content_layout.addWidget(header)

        self.stack = QStackedWidget(content)
        self.stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.stack.currentChanged.connect(self._on_stack_page_changed)
        content_layout.addWidget(self.stack, 1)

        self.stats_tab = StatsTab(self.file_ctx, self, on_core_stats_changed=self._on_core_stats_changed)
        self.slot_manager_tab = SlotManagerTab(self.file_ctx, on_open_slot=self.select_slot, parent=self)
        self.inventory_tab = InventoryTab(self.file_ctx, self, on_core_quantity_changed=self._on_inventory_core_quantity_changed)
        self.backup_tab = BackupManagerTab(self.file_ctx, on_restored=self._on_backup_restored, parent=self)
        self.hex_tab = HexEditorTab(self.file_ctx, self)
        self.settings_tab = SettingsTab(self, self)
        self.about_tab = AboutTab(self)

        self.stack.addWidget(self.stats_tab)
        self.stack.addWidget(self.slot_manager_tab)
        self.stack.addWidget(self.inventory_tab)
        self.stack.addWidget(self.backup_tab)
        self.stack.addWidget(self.hex_tab)
        self.stack.addWidget(self.settings_tab)
        self.stack.addWidget(self.about_tab)

        self.tab_buttons.idClicked.connect(self._set_page)
        self._populate_slot_combo()
        self._sync_slot_summary_header()

    def _set_page(self, idx: int) -> None:
        btn = self.tab_buttons.button(int(idx)) if hasattr(self, "tab_buttons") else None
        if btn is not None and not btn.isChecked():
            btn.setChecked(True)
        self.stack.setCurrentIndex(idx)
        title, subtitle = self.PAGE_META.get(idx, ("GoW Editor", ""))
        self.page_title.setText(title)
        self.page_subtitle.setText(subtitle)
        self._refresh_current_page_if_stale()

    def _on_stack_page_changed(self, idx: int) -> None:
        title, subtitle = self.PAGE_META.get(idx, ("GoW Editor", ""))
        self.page_title.setText(title)
        self.page_subtitle.setText(subtitle)
        self._refresh_current_page_if_stale()

    def _mark_pages_stale(self, exclude: set[int] | None = None) -> None:
        exclude = set(exclude or set())
        self._stale_pages = set(self.PAGE_META) - exclude

    def _refresh_page(self, idx: int) -> None:
        if self.file_ctx.save is None:
            return
        page_refreshers = {
            0: self.stats_tab.refresh_from_context,
            1: self.slot_manager_tab.refresh_from_context,
            2: self.inventory_tab.refresh_from_context,
            3: self.backup_tab.refresh_from_context,
            4: self.hex_tab.refresh_from_context,
        }
        refresher = page_refreshers.get(int(idx))
        if refresher is not None:
            refresher()
        self._stale_pages.discard(int(idx))

    def _refresh_current_page_if_stale(self) -> None:
        idx = int(self.stack.currentIndex()) if hasattr(self, "stack") else 0
        if idx in getattr(self, "_stale_pages", set()):
            self._refresh_page(idx)

    def _refresh_loaded_save_views(self) -> None:
        # Opening/switching saves used to eagerly rebuild every page, including
        # Inventory, Hex, and Slot Tools can do table scans or directory scans,
        # so the UI felt slow before the user
        # even opened them. Keep the header/dashboard hot and defer heavier
        # pages until first use.
        self._sync_slot_combo_to_save()
        self._refresh_slot_summaries()
        current_idx = int(self.stack.currentIndex()) if hasattr(self, "stack") else 0
        self._mark_pages_stale(exclude={0, current_idx})
        self.stats_tab.refresh_from_context()
        if current_idx != 0:
            self._refresh_page(current_idx)
        self._update_title()

    def _on_backup_restored(self) -> None:
        if self.file_ctx.path is not None:
            self._remember_recent_file(self.file_ctx.path)
        self._refresh_loaded_save_views()
        active_slot = getattr(self.file_ctx.save, "active_slot", 1)
        self._set_status(f"Slot tool action staged. Opened active slot {active_slot}.")

    def _on_core_stats_changed(self, fields: set[str]) -> None:
        """Dashboard changed core resource bytes; refresh dependent views lazily."""
        current_idx = int(self.stack.currentIndex()) if hasattr(self, "stack") else 0
        self._stale_pages.update({1, 2, 3, 4})
        if current_idx == 2 and hasattr(self, "inventory_tab"):
            self.inventory_tab.refresh_from_context()
            self._stale_pages.discard(2)
        self._refresh_slot_summaries()
        self._sync_slot_summary_header()

    def _on_inventory_core_quantity_changed(self, fields: set[str]) -> None:
        """Inventory staged XP/Hacksilver changes; keep Dashboard/header in sync."""
        current_idx = int(self.stack.currentIndex()) if hasattr(self, "stack") else 0
        self._stale_pages.update({0, 1, 3, 4})
        if current_idx == 0 and hasattr(self, "stats_tab"):
            self.stats_tab.refresh_from_context()
            self._stale_pages.discard(0)
        else:
            # Updating the small Dashboard fields is cheap and keeps Save Preview
            # and the sidebar header honest without forcing heavy tabs to rebuild.
            if hasattr(self, "stats_tab"):
                self.stats_tab.refresh_from_context()
        self._sync_slot_summary_header()
        self._update_title()

    # ------------------------------------------------------------------
    # Slot handling
    # ------------------------------------------------------------------

    def _populate_slot_combo(self) -> None:
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
            self.slot_combo.addItem(str(num), num)

        self.slot_combo.blockSignals(False)

    def _sync_slot_combo_to_save(self) -> None:
        save = self.file_ctx.save
        if save is None:
            self.slot_combo.blockSignals(True)
            self.slot_combo.setCurrentIndex(-1)
            self.slot_combo.setEnabled(False)
            self.slot_combo.blockSignals(False)
            self._sync_slot_summary_header()
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
        self._sync_slot_summary_header()

    def _slot_summary_label(self, slot_index: int, summary: Optional[dict]) -> str:
        if not summary:
            return f"Slot {slot_index}"

        xp = int(summary.get("xp", 0) or 0)
        hs = int(summary.get("hacksilver", 0) or 0)
        location = str(summary.get("location", "") or "").strip()
        last_played = str(summary.get("last_played", "") or "").strip()
        difficulty = str(summary.get("difficulty_name", "") or "").strip()

        head = f"Slot {slot_index}"
        if location:
            head += f" — {location}"
        details = []
        if last_played:
            details.append(last_played)
        if difficulty:
            details.append(difficulty)
        details.append(f"XP {xp:,}")
        details.append(f"HS {hs:,}")
        return f"{head}  ·  {' | '.join(details)}"

    def _active_summary_with_staged_core_values(self, slot_index: int, summary: Optional[dict]) -> Optional[dict]:
        save = self.file_ctx.save
        if save is None or summary is None:
            return summary
        if int(getattr(save, "active_slot", 1) or 1) != int(slot_index):
            return summary
        patched = dict(summary)
        # Inventory edits stage XP/Hacksilver before the table is committed into
        # raw bytes. The header should reflect the staged active-slot core
        # values just like the Dashboard does.
        patched["xp"] = int(getattr(save, "kratos_xp", patched.get("xp", 0)) or 0)
        patched["hacksilver"] = int(getattr(save, "hacksilver", patched.get("hacksilver", 0)) or 0)
        return patched

    def _sync_slot_summary_header(self) -> None:
        save = self.file_ctx.save
        if save is None:
            self.slot_badge.setText("No file")
            self.slot_badge.setObjectName("WarnChip")
            self.slot_badge.style().unpolish(self.slot_badge)
            self.slot_badge.style().polish(self.slot_badge)
            self.slot_summary.setText("Open a decrypted memory.dat to auto-select the newest active slot.")
            return

        active = int(getattr(save, "active_slot", 1) or 1)
        summary = save.summarize_slot(active) if hasattr(save, "summarize_slot") else None
        summary = self._active_summary_with_staged_core_values(active, summary)
        self.slot_badge.setText(f"Slot {active}")
        self.slot_badge.setObjectName("GoodChip")
        self.slot_badge.style().unpolish(self.slot_badge)
        self.slot_badge.style().polish(self.slot_badge)
        self.slot_summary.setText(self._slot_summary_label(active, summary))

    def _refresh_slot_summaries(self) -> None:
        save = self.file_ctx.save
        if save is None or not hasattr(save, "summarize_slot"):
            self._sync_slot_summary_header()
            return

        items = []
        for i in range(self.slot_combo.count()):
            slot_num = self.slot_combo.itemData(i)
            if slot_num is None:
                continue
            try:
                slot_index = int(slot_num)
            except Exception:
                continue
            items.append((slot_index, save.summarize_slot(slot_index)))

        def ts_from_summary(summary):
            if not summary:
                return 0
            try:
                return int(summary.get("last_played_raw", 0))
            except Exception:
                return 0

        items.sort(key=lambda pair: ts_from_summary(pair[1]), reverse=True)
        save_active = getattr(save, "active_slot", None)

        self.slot_combo.blockSignals(True)
        self.slot_combo.clear()

        for slot_index, summary in items:
            summary = self._active_summary_with_staged_core_values(slot_index, summary)
            self.slot_combo.addItem(self._slot_summary_label(slot_index, summary), slot_index)

        self.slot_combo.blockSignals(False)

        if save_active is not None:
            self._sync_slot_combo_to_save()
        self._sync_slot_summary_header()

    def refresh_slot_summary_labels(self) -> None:
        self._refresh_slot_summaries()

    def select_slot(self, slot_index: int) -> None:
        """Select a slot from other tabs while reusing the normal guarded switch path."""
        for i in range(self.slot_combo.count()):
            if self.slot_combo.itemData(i) == int(slot_index):
                self.slot_combo.setCurrentIndex(i)
                return
        self._set_status(f"Slot {slot_index} is not available in the slot table.")

    def _on_slot_changed(self) -> None:
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

        try:
            self._commit_tabs_to_save()
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to commit current slot before switching:\n{exc}")
            self._sync_slot_combo_to_save()
            return

        if hasattr(save, "set_active_slot"):
            save.set_active_slot(new_slot)

        self._refresh_loaded_save_views()
        self._set_status(f"Switched to slot {new_slot}")


    # ------------------------------------------------------------------
    # Persistent UI settings / recent saves
    # ------------------------------------------------------------------

    def _load_theme_name(self) -> str:
        name = str(self._settings.value("ui/theme", DEFAULT_THEME) or DEFAULT_THEME)
        return name if name in theme_names() else DEFAULT_THEME

    def _load_recent_files(self) -> list[Path]:
        raw = str(self._settings.value("files/recent", "[]") or "[]")
        try:
            values = json.loads(raw)
        except Exception:
            values = []
        recent: list[Path] = []
        seen: set[str] = set()
        for value in values:
            path = Path(str(value)).expanduser()
            key = str(path.resolve()) if path.exists() else str(path)
            if key in seen:
                continue
            seen.add(key)
            recent.append(path)
            if len(recent) >= 8:
                break
        return recent

    def _store_recent_files(self) -> None:
        self._settings.setValue("files/recent", json.dumps([str(p) for p in self._recent_files[:8]]))

    def _remember_recent_file(self, path: Path) -> None:
        path = Path(path)
        normalized = str(path.resolve()) if path.exists() else str(path)
        kept: list[Path] = []
        for existing in self._recent_files:
            existing_key = str(existing.resolve()) if existing.exists() else str(existing)
            if existing_key != normalized:
                kept.append(existing)
        self._recent_files = [path] + kept
        self._recent_files = self._recent_files[:8]
        self._store_recent_files()
        self._settings.setValue("files/last_dir", str(path.parent))
        self._refresh_recent_menu()

    def _default_file_dialog_dir(self) -> str:
        last_dir = Path(str(self._settings.value("files/last_dir", "") or ""))
        if last_dir.exists() and last_dir.is_dir():
            return str(last_dir)
        for path in self._recent_files:
            if path.parent.exists():
                return str(path.parent)
        return ""

    def _refresh_recent_menu(self) -> None:
        if not hasattr(self, "_recent_actions"):
            return
        visible_count = 0
        for action, path in zip(self._recent_actions, self._recent_files):
            action.setText(str(path))
            action.setData(str(path))
            action.setVisible(True)
            visible_count += 1
        for action in self._recent_actions[visible_count:]:
            action.setVisible(False)
            action.setData("")
        if hasattr(self, "act_clear_recent"):
            self.act_clear_recent.setEnabled(bool(self._recent_files))
        if hasattr(self, "recent_menu"):
            self.recent_menu.setEnabled(bool(self._recent_files))

    def _clear_recent_files(self) -> None:
        self._recent_files = []
        self._store_recent_files()
        self._refresh_recent_menu()
        self._set_status("Recent save list cleared.")

    def _restore_window_settings(self) -> None:
        geometry = self._settings.value("window/geometry")
        if geometry is not None:
            try:
                self.restoreGeometry(geometry)
            except Exception:
                pass
        state = self._settings.value("window/state")
        if state is not None:
            try:
                self.restoreState(state)
            except Exception:
                pass
        try:
            page = int(self._settings.value("ui/page", 0) or 0)
        except Exception:
            page = 0
        if page in self.PAGE_META and hasattr(self, "stack"):
            self._set_page(page)

    def _save_window_settings(self) -> None:
        self._settings.setValue("ui/theme", self._theme_name)
        if hasattr(self, "stack"):
            self._settings.setValue("ui/page", int(self.stack.currentIndex()))
        self._settings.setValue("window/geometry", self.saveGeometry())
        self._settings.setValue("window/state", self.saveState())

    # ------------------------------------------------------------------
    # Status / theme
    # ------------------------------------------------------------------

    def _init_status_bar(self) -> None:
        status = QStatusBar(self)
        self.setStatusBar(status)
        self._set_status("Ready")

    def _set_status(self, text: str) -> None:
        if self.statusBar():
            self.statusBar().showMessage(text, 5000)

    def _update_title(self) -> None:
        dirty = " *" if self.file_ctx.dirty else ""
        name = self.file_ctx.path.name if self.file_ctx.path else "No save loaded"
        self.setWindowTitle(f"GoW Save Lab - {theme_display_name(self._theme_name)}{dirty}")
        save_loaded = self.file_ctx.save is not None
        if hasattr(self, "file_chip"):
            self.file_chip.setText(f"{name}{dirty}")
        if hasattr(self, "dirty_chip"):
            if self.file_ctx.dirty:
                self.dirty_chip.setText("Unsaved edits")
                self.dirty_chip.setObjectName("WarnChip")
            else:
                self.dirty_chip.setText("Clean")
                self.dirty_chip.setObjectName("GoodChip")
            self.dirty_chip.style().unpolish(self.dirty_chip)
            self.dirty_chip.style().polish(self.dirty_chip)
        if hasattr(self, "btn_save_sidebar"):
            self.btn_save_sidebar.setEnabled(save_loaded)
        if hasattr(self, "btn_save_as_sidebar"):
            self.btn_save_as_sidebar.setEnabled(save_loaded)
        if hasattr(self, "act_save"):
            self.act_save.setEnabled(save_loaded)
        if hasattr(self, "act_save_as"):
            self.act_save_as.setEnabled(save_loaded)
        self._sync_slot_summary_header()

    def available_theme_names(self) -> list[str]:
        return theme_names()

    def current_theme_name(self) -> str:
        return self._theme_name

    def current_theme_display_name(self) -> str:
        return theme_display_name(self._theme_name)

    def theme_display_name(self, theme_name: str) -> str:
        return theme_display_name(theme_name)

    def dark_mode_enabled(self) -> bool:
        return is_dark_theme(self._theme_name)

    def set_dark_mode(self, enabled: bool) -> None:
        self.set_theme_name("obsidian" if enabled else "daybreak")

    def set_theme_name(self, theme_name: str) -> None:
        if theme_name not in theme_names():
            theme_name = DEFAULT_THEME
        if self._theme_name == theme_name:
            return
        self._theme_name = theme_name
        self._settings.setValue("ui/theme", self._theme_name)
        self._apply_theme()
        if hasattr(self, "settings_tab") and hasattr(self.settings_tab, "refresh_theme_state"):
            self.settings_tab.refresh_theme_state()
        self._update_title()
        self._set_status(f"Theme changed to {theme_display_name(self._theme_name)}")

    def cycle_theme(self, _checked: bool = False) -> None:
        names = theme_names()
        try:
            idx = names.index(self._theme_name)
        except ValueError:
            idx = 0
        self.set_theme_name(names[(idx + 1) % len(names)])

    def _apply_theme(self) -> None:
        app = QApplication.instance()
        if app is not None:
            apply_app_theme(app, self._theme_name)

    # ------------------------------------------------------------------
    # File operations
    # ------------------------------------------------------------------

    def _commit_tabs_to_save(self) -> None:
        if hasattr(self.inventory_tab, "_flush_pending_filter_refreshes"):
            self.inventory_tab._flush_pending_filter_refreshes()
        self.stats_tab.apply_to_save()
        self.inventory_tab.apply_to_save()
        # Inventory can update inventory-backed core resources such as
        # XP/Hacksilver, so refresh the Dashboard widgets before final byte
        # generation/save preview.
        self.stats_tab.refresh_from_context()
        self.hex_tab.apply_to_save()
        self._sync_slot_summary_header()
        self._update_title()

    def _open_file(self) -> None:
        if not self._confirm_discard_unsaved():
            return

        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Open GoW 2018 Save",
            self._default_file_dialog_dir(),
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

        self._remember_recent_file(path)
        self._refresh_loaded_save_views()
        active_slot = getattr(self.file_ctx.save, "active_slot", 1)
        self._set_status(f"Loaded: {path.name} - opened most recent active slot {active_slot}")

    def _open_recent_file(self, path: Path) -> None:
        if not path.exists():
            QMessageBox.warning(self, "Recent save missing", f"This recent save no longer exists:\n{path}")
            self._recent_files = [p for p in self._recent_files if str(p) != str(path)]
            self._store_recent_files()
            self._refresh_recent_menu()
            return
        if not self._confirm_discard_unsaved():
            return
        try:
            self.file_ctx.load(path)
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to load save:\n{exc}")
            return
        self._remember_recent_file(path)
        self._refresh_loaded_save_views()
        active_slot = getattr(self.file_ctx.save, "active_slot", 1)
        self._set_status(f"Loaded: {path.name} - opened most recent active slot {active_slot}")

    def _confirm_save_preview(self) -> bool:
        report = self.file_ctx.build_change_report()
        if not report.has_changes:
            result = QMessageBox.question(
                self,
                "No byte changes detected",
                "No byte changes were detected compared with the loaded baseline. Save anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            return result == QMessageBox.StandardButton.Yes

        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle("Review changes before saving")
        msg.setText("Review the staged save changes before writing to disk.")
        msg.setInformativeText(
            "Save will create a timestamped rollback backup first. "
            "Open 'Show Details' to inspect the exact change report."
        )
        msg.setDetailedText(report.to_text())
        msg.setStandardButtons(QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Cancel)
        msg.setDefaultButton(QMessageBox.StandardButton.Save)
        return msg.exec() == QMessageBox.StandardButton.Save

    def _save(self) -> None:
        if self.file_ctx.save is None:
            QMessageBox.information(self, "No save loaded", "Open a decrypted memory.dat before saving.")
            return
        if self.file_ctx.path is None:
            return self._save_as()

        try:
            self._commit_tabs_to_save()
            if not self._confirm_save_preview():
                self._set_status("Save canceled during change review.")
                return
            self.file_ctx.save_to_disk()
            if self.file_ctx.path is not None:
                self._remember_recent_file(self.file_ctx.path)
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to save:\n{exc}")
            return

        self._refresh_loaded_save_views()
        self._set_status("Save successful. Backup created if the file existed.")

    def _save_as(self) -> None:
        if self.file_ctx.save is None:
            QMessageBox.information(self, "No save loaded", "Open a decrypted memory.dat before saving.")
            return

        path_str, _ = QFileDialog.getSaveFileName(
            self,
            "Save GoW 2018 Save As",
            self._default_file_dialog_dir(),
            "GoW 2018 Save (*.dat);;All Files (*)",
        )
        if not path_str:
            return

        path = Path(path_str)
        try:
            self._commit_tabs_to_save()
            if not self._confirm_save_preview():
                self._set_status("Save As canceled during change review.")
                return
            self.file_ctx.save_to_disk(path)
            self._remember_recent_file(path)
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to save:\n{exc}")
            return

        self._refresh_loaded_save_views()
        self._set_status(f"Saved as: {path.name}")

    def _confirm_discard_unsaved(self) -> bool:
        if not self.file_ctx.dirty:
            return True
        result = QMessageBox.question(
            self,
            "Unsaved changes",
            "This save has unsaved edits. Open another file anyway?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return result == QMessageBox.StandardButton.Yes

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API name
        if self.file_ctx.dirty:
            result = QMessageBox.question(
                self,
                "Unsaved changes",
                "Exit without saving your edits?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if result != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        self._save_window_settings()
        event.accept()
