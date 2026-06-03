# app/ui/tabs/inventory_tab.py
from __future__ import annotations

from typing import Callable, Dict, List, Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QHeaderView,
    QAbstractItemView,
    QCheckBox,
    QFrame,
    QMessageBox,
    QTabBar,
    QTabWidget,
)

from app.core.file_context import FileContext
from app.core import gow2018_data
from app.core.inventory_model import (
    CORE_FIELD_BY_ITEM_ID,
    CORE_QUANTITY_ITEM_IDS,
    InventoryCommitError,
    MAX_INVENTORY_QTY,
    NON_DELETABLE_ITEM_IDS,
    commit_inventory_rows,
    read_inventory_rows,
)


INVENTORY_TYPE_GROUPS: list[tuple[str, set[str] | None]] = [
    ("All", None),
    ("Resources", {"Resources", "Main"}),
    ("Armor", {"Armor", "Chest Armor", "Waist Armor", "Wrist Armor"}),
    (
        "Runic / Weapon",
        {
            "Axe Pommel",
            "Weapon / Upgrade",
            "Heavy Runic Attack",
            "Light Runic Attack",
            "Runic Summon",
            "Rune",
            "Stats Runes",
        },
    ),
    ("Enchantments", {"Enchantments", "Perk / Enchantment"}),
    ("Talismans", {"Talisman"}),
    (
        "Quest / Special",
        {
            "Quest",
            "Special Items",
            "Shield",
            "Atreus",
            "Bestiary / Progression",
            "Quest / Lore",
            "Progression / Unlock",
            "Tutorial",
        },
    ),
    ("Technical", {"", "Unknown", "System / Locked", "Technical / Unclassified"}),
]


class InventoryTab(QWidget):
    """Validated slot inventory editor for decrypted God of War 2018 memory.dat files."""

    INVENTORY_TABLE_REL_OFFSET = gow2018_data.INVENTORY_TABLE_REL_OFFSET
    INVENTORY_ENTRY_SIZE = gow2018_data.INVENTORY_ENTRY_SIZE
    INVENTORY_MAX_ENTRIES = gow2018_data.INVENTORY_ENTRY_COUNT

    def __init__(
        self,
        file_ctx: FileContext,
        parent: Optional[QWidget] = None,
        on_core_quantity_changed: Optional[Callable[[set[str]], None]] = None,
    ) -> None:
        super().__init__(parent)

        self._file_ctx = file_ctx
        self._on_core_quantity_changed = on_core_quantity_changed
        self._all_items: List[Dict] = []
        self._filtered_items: List[Dict] = []
        self._available_by_id: Dict[str, Dict] = {}
        self._current_qty_by_item_id: Dict[str, int] = {}
        self._current_row_count_by_item_id: Dict[str, int] = {}
        self._items_in_save: List[Dict] = []
        self._item_write_info: Dict[str, List[int]] = {}
        self._free_entry_positions: List[int] = []
        self._inventory_dirty = False
        self._inventory_region: tuple[int, int] = (0, 0)
        self._updating_save_table = False
        self._hide_unknowns = True
        self._show_item_ids = False
        self._unlock_locked_rows = False
        self._experimental_append_rows = False
        self._selected_type_group: set[str] | None = None
        self._inventory_controls_enabled = False
        self._original_qty_by_offset: Dict[int, int] = {}
        self._original_id_by_offset: Dict[int, str] = {}
        self._visible_save_row_by_source_idx: Dict[int, int] = {}
        self._save_table_populating = False
        self._available_table_populating = False
        self._available_table_dirty = True
        self._pending_filter_refresh = False
        self._pending_save_filter_refresh = False
        self._has_bulk_editable_rows = False
        self._has_removable_rows = False

        self._build_ui()
        self._load_items_db()
        self._apply_filters()
        self._set_inventory_controls_enabled(False)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Compact filter strip. The previous design put category tabs, filters,
        # database search, inventory search, and editor actions in one visual
        # field. Keeping the category tabs here but moving the item database and
        # row actions into separate workspace pages makes the screen much easier
        # to scan.
        filter_card = QFrame(self)
        filter_card.setObjectName("Card")
        filter_layout = QVBoxLayout(filter_card)
        filter_layout.setContentsMargins(14, 12, 14, 12)
        filter_layout.setSpacing(10)

        category_row = QHBoxLayout()
        category_row.setSpacing(8)
        self.type_tab_bar = QTabBar(filter_card)
        self.type_tab_bar.setObjectName("InventoryTypeTabs")
        self.type_tab_bar.setDocumentMode(True)
        self.type_tab_bar.setDrawBase(False)
        self.type_tab_bar.setExpanding(False)
        self.type_tab_bar.setUsesScrollButtons(True)
        for label, types in INVENTORY_TYPE_GROUPS:
            idx = self.type_tab_bar.addTab(label)
            self.type_tab_bar.setTabData(idx, types)
        self.type_tab_bar.currentChanged.connect(self._on_type_tab_changed)
        category_row.addWidget(self.type_tab_bar, 1)
        filter_layout.addLayout(category_row)

        refine_row = QHBoxLayout()
        refine_row.setSpacing(8)
        refine_row.addWidget(QLabel("Exact Type", filter_card))
        self.type_combo = QComboBox(filter_card)
        self.type_combo.setMinimumWidth(150)
        self.type_combo.currentIndexChanged.connect(self._on_exact_type_changed)
        refine_row.addWidget(self.type_combo)

        self.hide_unknowns_chk = QCheckBox("Hide unknown/system rows", filter_card)
        self.hide_unknowns_chk.setChecked(True)
        self.hide_unknowns_chk.setToolTip("Hide raw IDs that are not present in the item database. Inferred database rows still stay readable in their category tabs.")
        self.hide_unknowns_chk.toggled.connect(self._on_hide_unknowns_toggled)
        refine_row.addWidget(self.hide_unknowns_chk)

        self.show_ids_chk = QCheckBox("Show technical IDs", filter_card)
        self.show_ids_chk.setToolTip("Reveal raw 16-character item/resource IDs for debugging.")
        self.show_ids_chk.toggled.connect(self._on_show_ids_toggled)
        refine_row.addWidget(self.show_ids_chk)

        self.unlock_locked_chk = QCheckBox("Advanced unlock", filter_card)
        self.unlock_locked_chk.setToolTip(
            "Allow manual quantity edits on locked/system rows. "
            "This does not make them removable, and Max All still skips them."
        )
        self.unlock_locked_chk.toggled.connect(self._on_unlock_locked_toggled)
        refine_row.addWidget(self.unlock_locked_chk)
        filter_layout.addLayout(refine_row)
        layout.addWidget(filter_card)

        self.inventory_workspace = QTabWidget(self)
        self.inventory_workspace.setObjectName("InventoryWorkspace")
        self.inventory_workspace.setDocumentMode(True)
        self.inventory_workspace.tabBar().setDrawBase(False)
        self.inventory_workspace.currentChanged.connect(self._on_inventory_workspace_changed)
        layout.addWidget(self.inventory_workspace, 1)

        # --------------------------------------------------------------
        # Page 1: current slot editor. This is the main workflow, so it
        # gets the full width instead of sharing space with the item DB.
        # --------------------------------------------------------------
        current_page = QWidget(self.inventory_workspace)
        current_page.setObjectName("InventoryPage")
        current_layout = QVBoxLayout(current_page)
        current_layout.setContentsMargins(0, 0, 0, 0)
        current_layout.setSpacing(10)

        right_card = QFrame(current_page)
        right_card.setObjectName("Card")
        right_layout = QVBoxLayout(right_card)
        right_layout.setContentsMargins(14, 14, 14, 14)
        right_layout.setSpacing(10)
        current_layout.addWidget(right_card, 1)

        right_header = QHBoxLayout()
        save_title = QLabel("Current Slot", right_card)
        save_title.setObjectName("SectionTitle")
        right_header.addWidget(save_title)
        right_header.addStretch(1)

        self.count_chip = QLabel("0 rows", right_card)
        self.count_chip.setObjectName("Chip")
        self.free_chip = QLabel("0 free", right_card)
        self.free_chip.setObjectName("Chip")
        self.stage_chip = QLabel("Clean", right_card)
        self.stage_chip.setObjectName("GoodChip")
        right_header.addWidget(self.count_chip)
        right_header.addWidget(self.free_chip)
        right_header.addWidget(self.stage_chip)
        right_layout.addLayout(right_header)

        save_filter_row = QHBoxLayout()
        save_filter_row.setSpacing(8)
        save_filter_row.addWidget(QLabel("Find", right_card))
        self.save_search_edit = QLineEdit(right_card)
        self.save_search_edit.setPlaceholderText("Filter current inventory by name, type, quantity, or technical ID...")
        self.save_search_edit.textChanged.connect(self._on_save_search_text_changed)
        save_filter_row.addWidget(self.save_search_edit, 1)

        self.btn_open_add_items = QPushButton("Add Items", right_card)
        self.btn_open_add_items.setObjectName("SubtleButton")
        self.btn_open_add_items.setToolTip("Open the item database page without crowding the current slot editor.")
        self.btn_open_add_items.clicked.connect(lambda: self.inventory_workspace.setCurrentIndex(1))
        save_filter_row.addWidget(self.btn_open_add_items)
        right_layout.addLayout(save_filter_row)

        edit_panel = QFrame(right_card)
        edit_panel.setObjectName("InventoryActionBar")
        edit_layout = QHBoxLayout(edit_panel)
        edit_layout.setContentsMargins(12, 10, 12, 10)
        edit_layout.setSpacing(8)

        self.save_detail = QLabel("Select an editable row", edit_panel)
        self.save_detail.setObjectName("MutedLabel")
        self.save_detail.setMinimumWidth(220)
        self.save_detail.setWordWrap(False)
        edit_layout.addWidget(self.save_detail, 1)

        edit_layout.addWidget(QLabel("Qty", edit_panel))
        self.selected_qty_edit = QLineEdit(edit_panel)
        self.selected_qty_edit.setPlaceholderText("Quantity")
        self.selected_qty_edit.setMinimumWidth(120)
        edit_layout.addWidget(self.selected_qty_edit)

        self.btn_set_qty = QPushButton("Set Qty", edit_panel)
        self.btn_set_qty.setObjectName("PrimaryButton")
        self.btn_set_qty.clicked.connect(self._on_set_qty_clicked)
        edit_layout.addWidget(self.btn_set_qty)

        self.btn_max_qty = QPushButton("Max Selected", edit_panel)
        self.btn_max_qty.clicked.connect(self._on_max_qty_clicked)
        edit_layout.addWidget(self.btn_max_qty)

        self.btn_max_all = QPushButton("Max All", edit_panel)
        self.btn_max_all.setObjectName("PrimaryButton")
        self.btn_max_all.setToolTip("Set every editable inventory row to 999,999,999. Locked/system rows are left alone.")
        self.btn_max_all.clicked.connect(self._on_max_all_clicked)
        edit_layout.addWidget(self.btn_max_all)

        self.btn_remove = QPushButton("Remove", edit_panel)
        self.btn_remove.clicked.connect(self._on_remove_clicked)
        edit_layout.addWidget(self.btn_remove)

        self.btn_clear = QPushButton("Clear", edit_panel)
        self.btn_clear.setObjectName("DangerButton")
        self.btn_clear.clicked.connect(self._on_clear_clicked)
        edit_layout.addWidget(self.btn_clear)

        self.btn_reload_inventory = QPushButton("Discard", edit_panel)
        self.btn_reload_inventory.setObjectName("SubtleButton")
        self.btn_reload_inventory.clicked.connect(self._on_discard_inventory_edits)
        edit_layout.addWidget(self.btn_reload_inventory)
        right_layout.addWidget(edit_panel)

        self.table_save = QTableWidget(right_card)
        self.table_save.setColumnCount(5)
        self.table_save.setHorizontalHeaderLabels(["Name", "Type", "ID", "Qty", "State"])
        self.table_save.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_save.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table_save.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.SelectedClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
        )
        self.table_save.verticalHeader().setVisible(False)
        self.table_save.setAlternatingRowColors(True)
        # Keep sorting disabled by default. QTableWidget sorting is expensive
        # while the user is editing cells because row moves invalidate indexes on
        # every quantity change; filters are the primary navigation path here.
        self.table_save.setSortingEnabled(False)
        self.table_save.setWordWrap(False)
        self.table_save.itemChanged.connect(self._on_save_table_item_changed)
        self.table_save.itemSelectionChanged.connect(self._on_save_selection_changed)
        right_layout.addWidget(self.table_save, 1)
        self.inventory_workspace.addTab(current_page, "Current Slot")

        # --------------------------------------------------------------
        # Page 2: addable database. Moving this out of the main editor
        # removes the crowded split view while keeping full add/remove support.
        # --------------------------------------------------------------
        add_page = QWidget(self.inventory_workspace)
        add_page.setObjectName("InventoryPage")
        add_layout = QVBoxLayout(add_page)
        add_layout.setContentsMargins(0, 0, 0, 0)
        add_layout.setSpacing(10)

        left_card = QFrame(add_page)
        left_card.setObjectName("Card")
        left_layout = QVBoxLayout(left_card)
        left_layout.setContentsMargins(14, 14, 14, 14)
        left_layout.setSpacing(10)
        add_layout.addWidget(left_card, 1)

        left_header_row = QHBoxLayout()
        left_header = QLabel("Item Database", left_card)
        left_header.setObjectName("SectionTitle")
        left_header_row.addWidget(left_header)
        left_header_row.addStretch(1)
        self.available_count_chip = QLabel("0 results", left_card)
        self.available_count_chip.setObjectName("Chip")
        self.available_capacity_chip = QLabel("0 open slots", left_card)
        self.available_capacity_chip.setObjectName("Chip")
        self.available_capacity_chip.setToolTip("Free inventory records available for brand-new items in the active slot. Stacking an item you already have does not consume a new slot.")
        left_header_row.addWidget(self.available_count_chip)
        left_header_row.addWidget(self.available_capacity_chip)
        left_layout.addLayout(left_header_row)

        database_search_row = QHBoxLayout()
        database_search_row.setSpacing(8)
        database_search_row.addWidget(QLabel("Search Database", left_card))
        self.search_edit = QLineEdit(left_card)
        self.search_edit.setPlaceholderText("Search names, types, file names, slot codes, or technical IDs...")
        self.search_edit.textChanged.connect(self._on_search_text_changed)
        database_search_row.addWidget(self.search_edit, 1)
        left_layout.addLayout(database_search_row)

        self.available_detail = QLabel(
            "Search the community item database. The You Have column shows the active slot's current quantity before you add anything. Open item slots shows how many brand-new rows can still be allocated. Technical IDs are hidden by default.",
            left_card,
        )
        self.available_detail.setObjectName("MutedLabel")
        self.available_detail.setWordWrap(True)
        left_layout.addWidget(self.available_detail)

        add_row = QHBoxLayout()
        add_row.setSpacing(8)
        add_row.addWidget(QLabel("Add amount", left_card))
        self.add_qty_edit = QLineEdit(left_card)
        self.add_qty_edit.setPlaceholderText("1")
        self.add_qty_edit.setText("1")
        self.add_qty_edit.setMinimumWidth(90)
        self.add_qty_edit.setToolTip("Amount to add when using Add Selected. Values are clamped to 999,999,999.")
        add_row.addWidget(self.add_qty_edit)

        self.stack_existing_chk = QCheckBox("Stack existing", left_card)
        self.stack_existing_chk.setChecked(True)
        self.stack_existing_chk.setToolTip("When checked, adding an item already in the slot increases that row instead of creating a duplicate record.")
        self.stack_existing_chk.toggled.connect(self._on_stack_existing_toggled)
        add_row.addWidget(self.stack_existing_chk)

        self.experimental_append_chk = QCheckBox("Experimental append", left_card)
        self.experimental_append_chk.setToolTip(
            "When the active slot has no free records, stage new rows after the detected item table instead of refusing the add. "
            "This can overwrite unknown slot data and is for testing only."
        )
        self.experimental_append_chk.toggled.connect(self._on_experimental_append_toggled)
        add_row.addWidget(self.experimental_append_chk)

        self.btn_add = QPushButton("Add Selected", left_card)
        self.btn_add.setObjectName("PrimaryButton")
        self.btn_add.clicked.connect(self._on_add_clicked)
        add_row.addWidget(self.btn_add)

        self.btn_add_all_visible = QPushButton("Add All Visible", left_card)
        self.btn_add_all_visible.setObjectName("DangerButton")
        self.btn_add_all_visible.setToolTip("Experimental: stage every visible database item. Use filters first; Save Preview will still run before disk write.")
        self.btn_add_all_visible.clicked.connect(self._on_add_all_visible_clicked)
        add_row.addWidget(self.btn_add_all_visible)
        add_row.addStretch(1)
        self.available_capacity_line = QLabel("Open item slots: 0", left_card)
        self.available_capacity_line.setObjectName("Chip")
        self.available_capacity_line.setToolTip("Free records available for items that need a new inventory row. Stacking an existing item does not use one.")
        add_row.addWidget(self.available_capacity_line)
        left_layout.addLayout(add_row)

        self.table_available = QTableWidget(left_card)
        self.table_available.setColumnCount(5)
        self.table_available.setHorizontalHeaderLabels(["Name", "You Have", "Type", "Add Action", "ID"])
        self.table_available.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_available.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table_available.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_available.verticalHeader().setVisible(False)
        self.table_available.setAlternatingRowColors(True)
        self.table_available.setSortingEnabled(False)
        self.table_available.setWordWrap(False)
        self.table_available.doubleClicked.connect(self._on_add_clicked)
        self.table_available.itemSelectionChanged.connect(self._on_available_selection_changed)
        left_layout.addWidget(self.table_available, 1)
        self.inventory_workspace.addTab(add_page, "Add Items")

        self.status_label = QLabel(
            "Open a decrypted memory.dat. Inventory writes stay disabled until the active slot's table validates.",
            self,
        )
        self.status_label.setObjectName("Chip")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self._build_filter_timers()
        self._configure_headers()

    def _build_filter_timers(self) -> None:
        # Search fields can emit on every keystroke. Debouncing prevents a
        # complete table rebuild for each typed character, which was one of
        # the remaining sources of Inventory-tab click/typing lag.
        self._filter_timer = QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.setInterval(120)
        self._filter_timer.timeout.connect(self._run_deferred_filter_refresh)

        self._save_filter_timer = QTimer(self)
        self._save_filter_timer.setSingleShot(True)
        self._save_filter_timer.setInterval(120)
        self._save_filter_timer.timeout.connect(self._run_deferred_save_filter_refresh)

    def _configure_headers(self) -> None:
        # Avoid automatic content-width resizing here. On Windows, Qt recalculates
        # column widths aggressively during selection/edit repaints, which made the Inventory
        # page feel laggy even though the tables are only a few hundred rows.
        hl = self.table_available.horizontalHeader()
        hl.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hl.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        hl.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        hl.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        self.table_available.setColumnWidth(1, 120)
        self.table_available.setColumnWidth(2, 190)
        self.table_available.setColumnWidth(3, 155)
        self.table_available.setColumnWidth(4, 165)

        hr = self.table_save.horizontalHeader()
        hr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in (1, 2, 3, 4):
            hr.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
        self.table_save.setColumnWidth(1, 210)
        self.table_save.setColumnWidth(2, 165)
        self.table_save.setColumnWidth(3, 115)
        self.table_save.setColumnWidth(4, 100)
        self.table_available.verticalHeader().setDefaultSectionSize(28)
        self.table_save.verticalHeader().setDefaultSectionSize(28)
        self._apply_id_column_visibility()

    def _apply_id_column_visibility(self) -> None:
        hidden = not bool(self._show_item_ids)
        self.table_available.setColumnHidden(4, hidden)
        self.table_save.setColumnHidden(2, hidden)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_unknown_row(row: Dict) -> bool:
        name = (row.get("name") or "").strip().lower()
        type_ = (row.get("type") or "").strip().lower()
        return type_ in ("unknown", "?", "", "system / locked") and (
            not name or name.startswith("unknown") or name.startswith("(unknown")
        )

    @staticmethod
    def _raw_bytes(raw) -> bytes:
        if isinstance(raw, bytearray):
            return bytes(raw)
        if isinstance(raw, bytes):
            return raw
        return b""

    def _parse_u32_text(self, text: str, default: int = 0, minimum: int = 0) -> int:
        cleaned = str(text or "").strip().replace(",", "")
        if not cleaned:
            return default
        try:
            value = int(cleaned, 0)
        except ValueError:
            raise ValueError("Quantity must be a whole number.")
        return max(minimum, min(value, MAX_INVENTORY_QTY))

    def _format_qty(self, value) -> str:
        try:
            return f"{int(value):,}"
        except Exception:
            return "0"

    def _refresh_current_item_totals(self) -> None:
        totals: Dict[str, int] = {}
        counts: Dict[str, int] = {}
        for row in self._items_in_save:
            item_id = gow2018_data.normalize_item_id(row.get("id"))
            if not item_id:
                continue
            try:
                qty = int(row.get("qty", 0) or 0)
            except Exception:
                qty = 0
            totals[item_id] = totals.get(item_id, 0) + qty
            counts[item_id] = counts.get(item_id, 0) + 1
        self._current_qty_by_item_id = totals
        self._current_row_count_by_item_id = counts

    def _owned_qty_for_item_id(self, item_id: str) -> int:
        return int(self._current_qty_by_item_id.get(gow2018_data.normalize_item_id(item_id) or "", 0) or 0)

    def _owned_row_count_for_item_id(self, item_id: str) -> int:
        return int(self._current_row_count_by_item_id.get(gow2018_data.normalize_item_id(item_id) or "", 0) or 0)

    def _owned_text_for_item_id(self, item_id: str) -> str:
        item_id = gow2018_data.normalize_item_id(item_id) or ""
        qty = self._owned_qty_for_item_id(item_id)
        count = self._owned_row_count_for_item_id(item_id)
        if count <= 0:
            return "0"
        text = self._format_qty(qty)
        if count > 1:
            text += f" ({count} rows)"
        return text

    def _add_action_text_for_item_id(self, item_id: str) -> str:
        item_id = gow2018_data.normalize_item_id(item_id) or ""
        owned_rows = self._owned_row_count_for_item_id(item_id)
        if owned_rows > 0 and self.stack_existing_chk.isChecked():
            return "Stacks existing"
        if owned_rows > 0 and item_id in NON_DELETABLE_ITEM_IDS:
            return "Edit existing"
        if owned_rows > 0:
            return "Adds new row" if self._available_new_entry_slots() > 0 else ("Experimental append" if self._experimental_append_rows else "No free slots")
        return "Uses 1 slot" if self._available_new_entry_slots() > 0 else ("Experimental append" if self._experimental_append_rows else "No free slots")

    def _mark_available_table_dirty(self) -> None:
        self._refresh_current_item_totals()
        self._available_table_dirty = True
        if self._should_populate_available_table():
            self._populate_available_table()
        else:
            self._update_count_chips()

    @staticmethod
    def _build_search_text(row: Dict) -> str:
        values = [
            row.get("name"),
            row.get("type"),
            row.get("file"),
            row.get("slot_code"),
            row.get("id"),
        ]
        return " ".join(str(value or "").lower() for value in values)

    @staticmethod
    def _search_matches(search: str, haystack: str) -> bool:
        # Treat multi-word searches as an AND query so "aegir gold" and
        # "chaos flame" work reliably without requiring exact punctuation.
        terms = [part for part in str(search or "").lower().split() if part]
        if not terms:
            return True
        return all(term in haystack for term in terms)

    def _set_inventory_controls_enabled(self, enabled: bool) -> None:
        self._inventory_controls_enabled = bool(enabled)
        for widget in (
            self.btn_add,
            self.btn_remove,
            self.btn_clear,
            self.btn_reload_inventory,
            self.btn_set_qty,
            self.btn_max_qty,
            self.btn_max_all,
            self.table_save,
            self.add_qty_edit,
            self.selected_qty_edit,
            self.stack_existing_chk,
            self.experimental_append_chk,
            self.btn_add_all_visible,
            self.save_search_edit,
        ):
            widget.setEnabled(enabled)
        self._sync_action_state()

    def _mark_inventory_dirty(self) -> None:
        self._inventory_dirty = True
        if hasattr(self._file_ctx, "mark_dirty"):
            self._file_ctx.mark_dirty()
        self._refresh_stage_chip_only()

    def _row_editable(self, row: Dict) -> bool:
        # Safe mode keeps unknown/system rows locked. Advanced Unlock allows
        # targeted manual quantity edits without pretending those rows are safe
        # for bulk operations or deletion.
        return not bool(row.get("protected", False)) or bool(self._unlock_locked_rows)

    def _row_bulk_editable(self, row: Dict) -> bool:
        # Max All intentionally remains conservative. Unknown/system rows may
        # use their quantity bytes as flags or progression state, so bulk edits
        # should not touch them even when Advanced Unlock is enabled.
        return not bool(row.get("protected", False))

    def _row_removable(self, row: Dict) -> bool:
        if bool(row.get("protected", False)):
            return False
        return bool(row.get("removable", True))

    def _row_state(self, row: Dict) -> str:
        protected = bool(row.get("protected", False))
        offset = row.get("offset")
        if offset is None or offset == "":
            return "New"
        try:
            pos = int(offset)
        except Exception:
            return "Staged"
        original_qty = self._original_qty_by_offset.get(pos)
        original_id = self._original_id_by_offset.get(pos)
        if original_id and original_id != gow2018_data.normalize_item_id(row.get("id")):
            return "Edited"
        if original_qty is not None and int(row.get("qty", 0) or 0) != original_qty:
            return "Edited"
        if protected:
            return "Unlocked" if self._unlock_locked_rows else "Locked"
        if not self._row_removable(row):
            return "Core"
        return "Saved"

    def _retained_existing_positions(self) -> set[int]:
        positions: set[int] = set()
        for row in self._items_in_save:
            offset = row.get("offset")
            if offset is None or offset == "":
                continue
            try:
                positions.add(int(offset))
            except Exception:
                pass
        return positions

    def _available_new_entry_slots(self) -> int:
        original_positions = {int(p) for positions in self._item_write_info.values() for p in positions}
        retained_positions = self._retained_existing_positions()
        deleted_positions = original_positions - retained_positions
        staged_new = sum(1 for row in self._items_in_save if row.get("offset") in (None, ""))
        return max(0, len(set(self._free_entry_positions)) + len(deleted_positions) - staged_new)

    def _refresh_row_capability_cache(self) -> None:
        self._has_bulk_editable_rows = any(self._row_bulk_editable(row) for row in self._items_in_save)
        self._has_removable_rows = any(self._row_removable(row) for row in self._items_in_save)

    def _update_count_chips(self) -> None:
        self._refresh_current_item_totals()
        self._refresh_row_capability_cache()
        open_slots = self._available_new_entry_slots()
        self.count_chip.setText(f"{len(self._items_in_save):,} rows")
        self.free_chip.setText(f"{open_slots:,} free")
        if self._inventory_dirty:
            self.stage_chip.setText("Staged edits")
            self.stage_chip.setObjectName("WarnChip")
        else:
            self.stage_chip.setText("Clean")
            self.stage_chip.setObjectName("GoodChip")
        self.stage_chip.style().unpolish(self.stage_chip)
        self.stage_chip.style().polish(self.stage_chip)
        if hasattr(self, "available_count_chip"):
            if len(self._filtered_items) == len(self._all_items):
                self.available_count_chip.setText(f"{len(self._filtered_items):,} results")
            else:
                self.available_count_chip.setText(f"{len(self._filtered_items):,} / {len(self._all_items):,} results")
        capacity_text = f"{open_slots:,} open slots"
        if self._experimental_append_rows:
            capacity_text += " + experimental append"
        if hasattr(self, "available_capacity_chip"):
            self.available_capacity_chip.setText(capacity_text)
        if hasattr(self, "available_capacity_line"):
            self.available_capacity_line.setText(f"Open item slots: {capacity_text}")

    def _refresh_stage_chip_only(self) -> None:
        """Update dirty/clean chips without recalculating table content."""
        if self._inventory_dirty:
            self.stage_chip.setText("Staged edits")
            self.stage_chip.setObjectName("WarnChip")
        else:
            self.stage_chip.setText("Clean")
            self.stage_chip.setObjectName("GoodChip")
        self.stage_chip.style().unpolish(self.stage_chip)
        self.stage_chip.style().polish(self.stage_chip)

    def _rebuild_visible_save_row_index(self) -> None:
        mapping: Dict[int, int] = {}
        for visual_row in range(self.table_save.rowCount()):
            item = self.table_save.item(visual_row, 0)
            if item is None:
                continue
            src_idx = item.data(Qt.ItemDataRole.UserRole)
            if src_idx is None:
                continue
            try:
                mapping[int(src_idx)] = visual_row
            except Exception:
                continue
        self._visible_save_row_by_source_idx = mapping

    def _select_save_source_index(self, src_idx: Optional[int]) -> None:
        if src_idx is None:
            return
        self._rebuild_visible_save_row_index()
        visual_row = self._visible_save_row_by_source_idx.get(int(src_idx))
        if visual_row is None:
            return
        self.table_save.setCurrentCell(visual_row, 0)

    def _save_row_values(self, row: Dict) -> list[str]:
        protected = bool(row.get("protected", False))
        removable = self._row_removable(row)
        type_text = str(row.get("type") or "Unknown")
        if protected:
            type_text = f"{type_text} / {'unlocked' if self._unlock_locked_rows else 'locked'}"
        elif not removable:
            type_text = f"{type_text} / synced core"
        return [
            row.get("name") or "(Unnamed)",
            type_text,
            row.get("id") or "",
            str(int(row.get("qty", 0) or 0)),
            self._row_state(row),
        ]

    def _make_save_table_item(self, src_idx: int, row: Dict, col: int, value: str) -> QTableWidgetItem:
        item = QTableWidgetItem(str(value))
        item.setData(Qt.ItemDataRole.UserRole, int(src_idx))
        if col == 3:
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            flags = Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled
            if self._row_editable(row):
                flags |= Qt.ItemFlag.ItemIsEditable
            item.setFlags(flags)
        else:
            item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
        return item

    def _refresh_visible_save_row(self, src_idx: int) -> bool:
        """Patch one visible row after a value edit instead of rebuilding the full table."""
        if src_idx < 0 or src_idx >= len(self._items_in_save):
            return False
        row = self._items_in_save[src_idx]
        if not self._save_row_matches_filters(row):
            return False
        self._rebuild_visible_save_row_index()
        visual_row = self._visible_save_row_by_source_idx.get(int(src_idx))
        if visual_row is None:
            return False

        table = self.table_save
        old_sorting = table.isSortingEnabled()
        old_updates = table.updatesEnabled()
        old_blocked = table.blockSignals(True)
        table.setSortingEnabled(False)
        table.setUpdatesEnabled(False)
        self._updating_save_table = True
        try:
            for col, value in enumerate(self._save_row_values(row)):
                table.setItem(visual_row, col, self._make_save_table_item(src_idx, row, col, value))
        finally:
            self._updating_save_table = False
            table.setSortingEnabled(old_sorting)
            table.setUpdatesEnabled(old_updates)
            table.blockSignals(old_blocked)

        self._rebuild_visible_save_row_index()
        self._select_save_source_index(src_idx)
        self._refresh_stage_chip_only()
        self._sync_selected_qty_editor()
        self._update_selection_details()
        self._sync_action_state()
        return True

    def _sync_action_state(self) -> None:
        enabled = bool(self._inventory_controls_enabled)
        selected_save_idx = self._selected_save_source_index()
        selected_row = self._items_in_save[selected_save_idx] if selected_save_idx is not None else None
        editable_selected = bool(selected_row) and self._row_editable(selected_row)
        removable_selected = bool(selected_row) and self._row_removable(selected_row)
        addable = enabled and self._should_populate_available_table() and self._selected_available_item() is not None
        bulk_addable = enabled and self._should_populate_available_table() and bool(self._filtered_items)

        if hasattr(self, "btn_add"):
            self.btn_add.setEnabled(addable)
        if hasattr(self, "btn_add_all_visible"):
            self.btn_add_all_visible.setEnabled(bulk_addable)
        for widget in ("btn_set_qty", "btn_max_qty"):
            if hasattr(self, widget):
                getattr(self, widget).setEnabled(enabled and editable_selected)
        if hasattr(self, "btn_remove"):
            self.btn_remove.setEnabled(enabled and removable_selected)
        if hasattr(self, "btn_max_all"):
            self.btn_max_all.setEnabled(enabled and bool(getattr(self, "_has_bulk_editable_rows", False)))
        if hasattr(self, "selected_qty_edit"):
            self.selected_qty_edit.setEnabled(enabled and editable_selected)
        if hasattr(self, "btn_clear"):
            self.btn_clear.setEnabled(enabled and bool(getattr(self, "_has_removable_rows", False)))
        if hasattr(self, "btn_reload_inventory"):
            self.btn_reload_inventory.setEnabled(enabled and self._inventory_dirty)

    def _sync_selected_qty_editor(self) -> None:
        if not hasattr(self, "selected_qty_edit"):
            return
        src_idx = self._selected_save_source_index()
        if src_idx is None:
            self.selected_qty_edit.setText("")
            self.selected_qty_edit.setPlaceholderText("Select an editable row")
            return
        row = self._items_in_save[src_idx]
        self.selected_qty_edit.setText(str(int(row.get("qty", 0) or 0)))

    # ------------------------------------------------------------------
    # Type tab helpers
    # ------------------------------------------------------------------

    def _type_group_types(self) -> set[str] | None:
        if not hasattr(self, "type_tab_bar"):
            return None
        data = self.type_tab_bar.tabData(self.type_tab_bar.currentIndex())
        return set(data) if data is not None else None

    def _row_in_type_group(self, row: Dict) -> bool:
        group = self._selected_type_group
        if group is None:
            return True
        type_text = str(row.get("type") or "").strip()
        if "" in group and not type_text:
            return True
        return type_text in group

    def _types_for_current_group(self) -> List[str]:
        group = self._selected_type_group
        all_types = sorted({str(row.get("type") or "").strip() for row in self._all_items})
        if group is None:
            return [t for t in all_types if t]
        if "" in group:
            return sorted(t for t in all_types if not t or t in group)
        return sorted(t for t in all_types if t in group)

    def _on_type_tab_changed(self, index: int) -> None:
        self._selected_type_group = self._type_group_types()
        self._rebuild_exact_type_filter()
        self._apply_filters()
        self._populate_save_table()

    def _rebuild_exact_type_filter(self) -> None:
        if not hasattr(self, "type_combo"):
            return
        current = self.type_combo.currentText() if self.type_combo.count() else "All"
        self.type_combo.blockSignals(True)
        self.type_combo.clear()
        self.type_combo.addItem("All")
        types = self._types_for_current_group()
        for t in types:
            label = t if t else "Unknown"
            self.type_combo.addItem(label, t)
        idx = self.type_combo.findText(current)
        self.type_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.type_combo.blockSignals(False)

    # ------------------------------------------------------------------
    # Items DB + filters
    # ------------------------------------------------------------------

    def _load_items_db(self) -> None:
        try:
            self._all_items = [dict(row) for row in gow2018_data.get_all_items()]
            for row in self._all_items:
                row["_search_text"] = self._build_search_text(row)
        except Exception as exc:
            print(f"[InventoryTab] Failed to load items DB: {exc}")
            self._all_items = []

        self._available_by_id = {
            gow2018_data.normalize_item_id(row.get("id")): row
            for row in self._all_items
            if gow2018_data.normalize_item_id(row.get("id"))
        }

        self._selected_type_group = self._type_group_types()
        self._rebuild_exact_type_filter()

    def _on_exact_type_changed(self) -> None:
        self._apply_filters()
        self._populate_save_table()

    def _on_search_text_changed(self) -> None:
        self._schedule_filter_refresh()

    def _on_save_search_text_changed(self) -> None:
        self._schedule_save_filter_refresh()

    # Compatibility aliases used by older tests/tools. They now route through
    # the debounced refresh path instead of rebuilding tables immediately.
    def _on_filter_changed(self) -> None:
        self._schedule_filter_refresh()

    def _on_save_filter_changed(self) -> None:
        self._schedule_save_filter_refresh()

    def _schedule_filter_refresh(self) -> None:
        self._pending_filter_refresh = True
        timer = getattr(self, "_filter_timer", None)
        if timer is None:
            self._run_deferred_filter_refresh()
        else:
            timer.start()

    def _schedule_save_filter_refresh(self) -> None:
        self._pending_save_filter_refresh = True
        timer = getattr(self, "_save_filter_timer", None)
        if timer is None:
            self._run_deferred_save_filter_refresh()
        else:
            timer.start()

    def _flush_pending_database_filter_refresh(self) -> None:
        if getattr(self, "_pending_filter_refresh", False):
            timer = getattr(self, "_filter_timer", None)
            if timer is not None:
                timer.stop()
            self._run_deferred_filter_refresh()

    def _flush_pending_save_filter_refresh(self) -> None:
        if getattr(self, "_pending_save_filter_refresh", False):
            timer = getattr(self, "_save_filter_timer", None)
            if timer is not None:
                timer.stop()
            self._run_deferred_save_filter_refresh()

    def _flush_pending_filter_refreshes(self) -> None:
        self._flush_pending_database_filter_refresh()
        self._flush_pending_save_filter_refresh()

    def _run_deferred_filter_refresh(self) -> None:
        self._pending_filter_refresh = False
        # Database search now affects only the Add Items table. Rebuilding the
        # current-slot table here made the editor lag while typing in the hidden
        # database search field and made search look broken on the Current Slot
        # page because the visible table did not actually use that text.
        self._apply_filters()

    def _run_deferred_save_filter_refresh(self) -> None:
        self._pending_save_filter_refresh = False
        self._populate_save_table()

    def _on_stack_existing_toggled(self, _checked: bool) -> None:
        self._mark_available_table_dirty()
        self._update_selection_details()
        self._sync_action_state()

    def _on_experimental_append_toggled(self, checked: bool) -> None:
        self._experimental_append_rows = bool(checked)
        self._mark_available_table_dirty()
        self._update_selection_details()
        self._sync_action_state()
        if self._experimental_append_rows:
            self.status_label.setText(
                "Experimental append is ON: Add Selected/Add All Visible can stage rows after the detected item table when no free records exist. "
                "This is intentionally unsafe for testing; Save Preview and backups still run before disk write."
            )
        elif self._inventory_controls_enabled:
            self.status_label.setText("Experimental append is off: new items require existing free inventory records or stacking onto owned rows.")

    def _on_hide_unknowns_toggled(self, checked: bool) -> None:
        self._hide_unknowns = bool(checked)
        self._apply_filters()
        self._populate_save_table()

    def _on_show_ids_toggled(self, checked: bool) -> None:
        self._show_item_ids = bool(checked)
        self._apply_id_column_visibility()
        self._update_selection_details()

    def _on_unlock_locked_toggled(self, checked: bool) -> None:
        self._unlock_locked_rows = bool(checked)
        self._populate_save_table()
        if self._unlock_locked_rows:
            self.status_label.setText(
                "Advanced Unlock is on: locked/system rows can be edited manually with Set Qty or Max Selected. "
                "They still cannot be removed, and Max All still skips them."
            )
        elif self._inventory_controls_enabled:
            self.status_label.setText(
                "Advanced Unlock is off: unknown/system rows are locked again. Existing staged edits remain until Discard or Save."
            )

    def _should_populate_available_table(self) -> bool:
        return bool(hasattr(self, "inventory_workspace") and self.inventory_workspace.currentIndex() == 1)

    def _on_inventory_workspace_changed(self, index: int) -> None:
        if int(index) == 1 and getattr(self, "_available_table_dirty", True):
            self._populate_available_table()
        self._sync_action_state()

    def _apply_filters(self) -> None:
        type_filter = self.type_combo.currentData()
        if type_filter is None:
            type_filter = self.type_combo.currentText()
        search = self.search_edit.text().strip().lower()

        def match(row: Dict) -> bool:
            if self._hide_unknowns and self._is_unknown_row(row):
                return False
            if not self._row_in_type_group(row):
                return False
            if type_filter and type_filter != "All" and (row.get("type") or "") != type_filter:
                return False
            if search and not self._search_matches(search, str(row.get("_search_text") or self._build_search_text(row))):
                return False
            return True

        self._filtered_items = [r for r in self._all_items if match(r)]
        self._available_table_dirty = True
        if self._should_populate_available_table():
            self._populate_available_table()
        else:
            self._update_count_chips()
            self._update_selection_details()
            self._sync_action_state()

    def _save_row_matches_filters(self, row: Dict) -> bool:
        if self._hide_unknowns and self._is_unknown_row(row):
            return False
        if not self._row_in_type_group(row):
            return False
        type_filter = self.type_combo.currentData()
        if type_filter is None:
            type_filter = self.type_combo.currentText()
        if type_filter and type_filter != "All" and (row.get("type") or "") != type_filter:
            return False
        search = self.save_search_edit.text().strip().lower() if hasattr(self, "save_search_edit") else ""
        if search:
            haystack = " ".join(
                [
                    str(row.get("name") or ""),
                    str(row.get("type") or ""),
                    str(row.get("file") or ""),
                    str(row.get("id") or ""),
                    str(row.get("qty") or ""),
                    self._row_state(row),
                ]
            ).lower()
            if not self._search_matches(search, haystack):
                return False
        return True

    def _populate_available_table(self) -> None:
        table = self.table_available
        old_sorting = table.isSortingEnabled()
        old_updates = table.updatesEnabled()
        old_blocked = table.blockSignals(True)
        self._available_table_populating = True
        table.setSortingEnabled(False)
        table.setUpdatesEnabled(False)
        try:
            self._available_table_dirty = False
            table.setRowCount(len(self._filtered_items))

            self._refresh_current_item_totals()
            for r, row in enumerate(self._filtered_items):
                item_id = gow2018_data.normalize_item_id(row.get("id")) or ""
                values = [
                    row.get("name") or "",
                    self._owned_text_for_item_id(item_id),
                    row.get("type") or "",
                    self._add_action_text_for_item_id(item_id),
                    item_id,
                ]
                for col, value in enumerate(values):
                    item = QTableWidgetItem(str(value))
                    item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
                    item.setData(Qt.ItemDataRole.UserRole, item_id)
                    if col == 1:
                        item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    table.setItem(r, col, item)
        finally:
            self._available_table_populating = False
            table.setSortingEnabled(old_sorting)
            table.setUpdatesEnabled(old_updates)
            table.blockSignals(old_blocked)

        self._update_count_chips()
        self._update_selection_details()
        self._sync_action_state()

    # ------------------------------------------------------------------
    # Reading inventory from the save
    # ------------------------------------------------------------------

    def refresh_from_save(self) -> None:
        self._reload_items_in_save()
        self._populate_save_table()

    def refresh_from_context(self) -> None:
        self.refresh_from_save()

    def _reload_items_in_save(self) -> None:
        save = getattr(self._file_ctx, "save", None)
        if save is None:
            self._items_in_save = []
            self._item_write_info = {}
            self._free_entry_positions = []
            self._inventory_region = (0, 0)
            self._inventory_dirty = False
            self._original_qty_by_offset = {}
            self._original_id_by_offset = {}
            self._set_inventory_controls_enabled(False)
            self._update_count_chips()
            self.status_label.setText("No save loaded.")
            return

        raw = self._raw_bytes(getattr(save, "raw", b""))
        slot_index = int(getattr(save, "active_slot", 1))
        start, end = gow2018_data.inventory_region_for_slot(len(raw), slot_index)
        self._inventory_region = (start, end)

        if not raw or end <= start:
            self._items_in_save = []
            self._item_write_info = {}
            self._free_entry_positions = []
            self._inventory_dirty = False
            self._original_qty_by_offset = {}
            self._original_id_by_offset = {}
            self._set_inventory_controls_enabled(False)
            self._update_count_chips()
            self.status_label.setText(
                "Inventory region could not be validated for this save/slot. Writes are disabled to avoid corruption."
            )
            return

        snapshot = read_inventory_rows(raw, slot_index, gow2018_data.get_items_by_id())
        if not snapshot.anchor_valid:
            self._items_in_save = []
            self._item_write_info = {}
            self._free_entry_positions = []
            self._inventory_dirty = False
            self._original_qty_by_offset = {}
            self._original_id_by_offset = {}
            self._set_inventory_controls_enabled(False)
            self._update_count_chips()
            self.status_label.setText(
                f"Inventory address range exists at 0x{start:08X}-0x{end:08X}, "
                "but the XP table anchor was not found. Writes are disabled for this slot."
            )
            return

        self._item_write_info = snapshot.write_info
        self._free_entry_positions = snapshot.free_positions
        self._items_in_save = [dict(row) for row in snapshot.items]
        self._original_qty_by_offset = {
            int(row["offset"]): int(row.get("qty", 0) or 0)
            for row in self._items_in_save
            if row.get("offset") not in (None, "")
        }
        self._original_id_by_offset = {
            int(row["offset"]): gow2018_data.normalize_item_id(row.get("id")) or ""
            for row in self._items_in_save
            if row.get("offset") not in (None, "")
        }
        self._inventory_dirty = False
        self._set_inventory_controls_enabled(True)
        self._update_count_chips()
        self.status_label.setText(
            f"Inventory/resource table validated: 0x{start:08X}-0x{end:08X}. "
            f"Detected {len(self._items_in_save)} rows. XP/Hacksilver sync with Dashboard; edit safe quantities, add known items, remove editable rows, or enable Advanced Unlock for targeted locked-row edits, then Save."
        )

    def _populate_save_table(self) -> None:
        table = self.table_save
        previous_src_idx = self._selected_save_source_index()
        old_sorting = table.isSortingEnabled()
        old_updates = table.updatesEnabled()
        old_blocked = table.blockSignals(True)
        table.setSortingEnabled(False)
        table.setUpdatesEnabled(False)
        self._updating_save_table = True
        self._save_table_populating = True

        try:
            visible_rows = []
            for idx, row in enumerate(self._items_in_save):
                if self._save_row_matches_filters(row):
                    visible_rows.append((idx, row))

            table.setRowCount(len(visible_rows))

            for r, (src_idx, row) in enumerate(visible_rows):
                for col, value in enumerate(self._save_row_values(row)):
                    table.setItem(r, col, self._make_save_table_item(src_idx, row, col, value))
        finally:
            self._save_table_populating = False
            self._updating_save_table = False
            table.setSortingEnabled(old_sorting)
            table.setUpdatesEnabled(old_updates)
            table.blockSignals(old_blocked)

        self._rebuild_visible_save_row_index()
        self._update_count_chips()
        self._select_save_source_index(previous_src_idx)
        self._sync_selected_qty_editor()
        self._update_selection_details()
        self._sync_action_state()

    def _update_selection_details(self) -> None:
        if hasattr(self, "available_detail"):
            src = self._selected_available_item()
            if src:
                item_id = gow2018_data.normalize_item_id(src.get("id")) or ""
                owned_qty = self._owned_qty_for_item_id(item_id)
                owned_rows = self._owned_row_count_for_item_id(item_id)
                open_slots = self._available_new_entry_slots()
                action_text = self._add_action_text_for_item_id(item_id)
                detail = (
                    f"Selected: {src.get('name') or 'Unnamed'}  ·  {src.get('type') or 'Unknown'}"
                    f"  ·  You have {self._format_qty(owned_qty)}"
                )
                if owned_rows > 1:
                    detail += f" across {owned_rows} rows"
                detail += f"  ·  {action_text}  ·  Open item slots {open_slots:,}"
                if self._experimental_append_rows:
                    detail += "  ·  Experimental append ON"
                if self._show_item_ids:
                    detail += f"  ·  ID {item_id or '—'}"
                self.available_detail.setText(detail)
            else:
                self.available_detail.setText(
                    "Pick a type tab, search the community item database, then double-click/Add Selected or use Add All Visible. The You Have column shows your current quantity before adding. Experimental append can bypass full-slot checks for testing."
                )

        if hasattr(self, "save_detail"):
            src_idx = self._selected_save_source_index()
            if src_idx is not None and 0 <= src_idx < len(self._items_in_save):
                row = self._items_in_save[src_idx]
                state = self._row_state(row)
                locked = ""
                if bool(row.get("protected", False)):
                    locked = " · advanced-unlocked" if self._unlock_locked_rows else " · locked"
                pinned = " · synced with Dashboard/non-removable" if self._is_core_quantity_row(row) else (" · non-removable" if not bool(row.get("protected", False)) and not self._row_removable(row) else "")
                detail = (
                    f"Selected: {row.get('name') or 'Unnamed'}  ·  {row.get('type') or 'Unknown'}"
                    f"  ·  Qty {self._format_qty(row.get('qty', 0))}  ·  {state}{locked}{pinned}"
                )
                if row.get("offset") not in (None, "") and self._show_item_ids:
                    detail += f"  ·  Offset 0x{int(row.get('offset')):08X}"
                if self._show_item_ids:
                    item_id = gow2018_data.normalize_item_id(row.get("id")) or "—"
                    detail += f"  ·  ID {item_id}"
                self.save_detail.setText(detail)
            else:
                self.save_detail.setText(
                    "Select a row, enter a quantity, then use Set Qty, Max Selected, Max All, Remove, Clear, or Discard. Core XP/Hacksilver are editable but cannot be removed. Use Advanced Unlock for manual locked-row edits."
                )

    def _on_available_selection_changed(self) -> None:
        if self._available_table_populating:
            return
        self._update_selection_details()
        self._sync_action_state()

    def _on_save_selection_changed(self) -> None:
        if self._save_table_populating:
            return
        self._sync_selected_qty_editor()
        self._update_selection_details()
        self._sync_action_state()

    # ------------------------------------------------------------------
    # Manual edits
    # ------------------------------------------------------------------

    def _is_core_quantity_row(self, row: Dict) -> bool:
        return gow2018_data.normalize_item_id(row.get("id")) in CORE_QUANTITY_ITEM_IDS

    def _sync_core_quantity_to_save(self, row: Dict, qty: int) -> None:
        """Mirror staged core inventory quantities onto SaveFile fields.

        Inventory edits are staged in the table model until Save, but the
        Dashboard reads save.kratos_xp/save.hacksilver. Updating those in-memory
        fields here keeps both tabs honest without writing disk early.
        """
        save = getattr(self._file_ctx, "save", None)
        if save is None:
            return
        item_id = gow2018_data.normalize_item_id(row.get("id"))
        field_name = CORE_FIELD_BY_ITEM_ID.get(item_id)
        if not field_name:
            return
        setattr(save, field_name, int(qty))
        if self._on_core_quantity_changed is not None:
            self._on_core_quantity_changed({field_name})

    def _sync_core_quantities_from_rows(self) -> None:
        changed: set[str] = set()
        save = getattr(self._file_ctx, "save", None)
        if save is None:
            return
        for row in self._items_in_save:
            item_id = gow2018_data.normalize_item_id(row.get("id"))
            field_name = CORE_FIELD_BY_ITEM_ID.get(item_id)
            if not field_name:
                continue
            qty = int(row.get("qty", 0) or 0)
            if int(getattr(save, field_name, -1) or 0) != qty:
                setattr(save, field_name, qty)
                changed.add(field_name)
        if changed and self._on_core_quantity_changed is not None:
            self._on_core_quantity_changed(changed)

    def _set_row_qty(self, src_idx: int, new_qty: int) -> None:
        if src_idx < 0 or src_idx >= len(self._items_in_save):
            return
        row = self._items_in_save[src_idx]
        if not self._row_editable(row):
            return
        new_qty = max(0, min(int(new_qty), MAX_INVENTORY_QTY))
        if int(row.get("qty", 0) or 0) == new_qty:
            return
        row["qty"] = new_qty
        self._sync_core_quantity_to_save(row, new_qty)
        self._mark_inventory_dirty()
        self._mark_available_table_dirty()
        if not self._refresh_visible_save_row(src_idx):
            self._populate_save_table()

    def _on_save_table_item_changed(self, item: QTableWidgetItem) -> None:
        if self._updating_save_table or item.column() != 3:
            return

        src_idx = item.data(Qt.ItemDataRole.UserRole)
        if src_idx is None:
            return
        src_idx = int(src_idx)
        if src_idx < 0 or src_idx >= len(self._items_in_save):
            return
        if not self._row_editable(self._items_in_save[src_idx]):
            return

        text = item.text().strip()
        try:
            new_qty = self._parse_u32_text(text, default=int(self._items_in_save[src_idx].get("qty", 0) or 0))
        except ValueError:
            QMessageBox.warning(self, "Invalid quantity", "Quantity must be a whole number from 0 to 999,999,999.")
            self._populate_save_table()
            return

        self._set_row_qty(src_idx, new_qty)

    def _on_set_qty_clicked(self) -> None:
        self._flush_pending_save_filter_refresh()
        src_idx = self._selected_save_source_index()
        if src_idx is None:
            return
        try:
            new_qty = self._parse_u32_text(self.selected_qty_edit.text(), default=0)
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid quantity", str(exc))
            return
        self._set_row_qty(src_idx, new_qty)

    def _on_max_qty_clicked(self) -> None:
        self._flush_pending_save_filter_refresh()
        src_idx = self._selected_save_source_index()
        if src_idx is None:
            return
        self._set_row_qty(src_idx, MAX_INVENTORY_QTY)

    def _on_max_all_clicked(self) -> None:
        self._flush_pending_save_filter_refresh()
        editable_rows = [row for row in self._items_in_save if self._row_bulk_editable(row)]
        if not editable_rows:
            QMessageBox.information(
                self,
                "Nothing editable",
                "Only locked/system rows are available for safe bulk editing. Use Advanced Unlock and Max Selected/Set Qty for targeted manual rows.",
            )
            return

        result = QMessageBox.question(
            self,
            "Max all editable inventory values?",
            f"Set {len(editable_rows):,} editable inventory rows to {self._format_qty(MAX_INVENTORY_QTY)}? "
            "Locked/system rows will not be changed by Max All. Use Advanced Unlock for targeted manual rows. The file is not changed until Save.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if result != QMessageBox.StandardButton.Yes:
            return

        changed = 0
        changed_core_fields: set[str] = set()
        for row in editable_rows:
            if int(row.get("qty", 0) or 0) != MAX_INVENTORY_QTY:
                row["qty"] = MAX_INVENTORY_QTY
                item_id = gow2018_data.normalize_item_id(row.get("id"))
                field_name = CORE_FIELD_BY_ITEM_ID.get(item_id)
                if field_name:
                    changed_core_fields.add(field_name)
                changed += 1

        if changed_core_fields:
            self._sync_core_quantities_from_rows()

        if changed <= 0:
            QMessageBox.information(
                self,
                "Already maxed",
                f"All editable inventory rows are already {self._format_qty(MAX_INVENTORY_QTY)}.",
            )
            return

        self._mark_inventory_dirty()
        self._mark_available_table_dirty()
        self._populate_save_table()
        self.status_label.setText(
            f"Staged Max All: {changed:,} editable inventory rows set to {self._format_qty(MAX_INVENTORY_QTY)}. "
            "Use Save or Save As to write disk with backup + change review."
        )

    # ------------------------------------------------------------------
    # Writing inventory back to the save
    # ------------------------------------------------------------------

    def apply_to_save(self, force: bool = False) -> None:
        if not self._inventory_dirty and not force:
            return

        save = getattr(self._file_ctx, "save", None)
        if save is None:
            return

        raw = getattr(save, "raw", None)
        if not isinstance(raw, (bytes, bytearray)):
            raise ValueError("Unsupported save.raw type; expected bytes/bytearray.")

        slot_index = int(getattr(save, "active_slot", 1))

        try:
            result = commit_inventory_rows(
                raw,
                slot_index,
                self._items_in_save,
                self._item_write_info,
                self._free_entry_positions,
                allow_overflow_append=self._experimental_append_rows,
            )
        except InventoryCommitError:
            self._inventory_dirty = True
            raise

        save.raw = result.raw
        self._inventory_dirty = False
        if hasattr(save, "_load_inventory_from_binary"):
            save._load_inventory_from_binary()
        if hasattr(save, "_load_core_stats_from_binary"):
            # XP and Hacksilver are inventory-backed, so reload core stats after
            # an inventory commit to keep the Dashboard/slot summary in sync.
            save._load_core_stats_from_binary()
        if self._on_core_quantity_changed is not None:
            self._on_core_quantity_changed({"kratos_xp", "hacksilver"})

        # Re-read after commit so write positions/free counts exactly match the persisted buffer.
        self._reload_items_in_save()
        self._populate_save_table()
        self.status_label.setText(
            "Inventory edits committed into the in-memory save buffer. "
            f"Written: {result.written_items}, allocated: {result.allocated_entries}, freed: {result.freed_entries}. "
            + ("Experimental append was enabled for this commit. " if self._experimental_append_rows else "")
            + "Use Save or Save As to write disk with backup + change review."
        )

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------

    def _selected_available_item(self) -> Optional[Dict]:
        if not self._should_populate_available_table():
            return None
        self._flush_pending_database_filter_refresh()
        if getattr(self, "_available_table_dirty", False):
            self._populate_available_table()
        row = self.table_available.currentRow()
        if row < 0:
            return None
        item = self.table_available.item(row, 0)
        if item is None:
            return None
        item_id = item.data(Qt.ItemDataRole.UserRole)
        if not item_id:
            return None
        return self._available_by_id.get(str(item_id))


    def _make_new_staged_item(self, src: Dict, qty: int) -> Dict:
        item_id = gow2018_data.normalize_item_id(src.get("id"))
        return {
            "id": item_id,
            "name": src.get("name") or "",
            "type": src.get("type") or "",
            "qty": max(0, min(int(qty), MAX_INVENTORY_QTY)),
            "offset": None,
            "row": -1,
            "protected": False,
            "removable": item_id not in NON_DELETABLE_ITEM_IDS,
        }

    def _can_stage_new_row(self) -> bool:
        return self._available_new_entry_slots() > 0 or self._experimental_append_rows

    def _warn_or_confirm_experimental_append(self, item_count: int) -> bool:
        if self._available_new_entry_slots() > 0:
            return True
        if not self._experimental_append_rows:
            QMessageBox.warning(
                self,
                "Inventory table is full",
                "There are no free inventory records available for a new item. Remove an editable item first, stack onto an existing row, or enable Experimental append for a risky test build.",
            )
            return False
        result = QMessageBox.warning(
            self,
            "Experimental append is risky",
            f"Stage {item_count:,} new row(s) after the detected item table? This may overwrite unknown slot data and can corrupt the save. "
            "Use this only for testing with backups. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return result == QMessageBox.StandardButton.Yes

    def _on_add_clicked(self) -> None:
        self._flush_pending_database_filter_refresh()
        src = self._selected_available_item()
        if not src:
            return

        item_id = gow2018_data.normalize_item_id(src.get("id"))
        if not item_id:
            return
        try:
            add_qty = self._parse_u32_text(self.add_qty_edit.text(), default=1, minimum=1)
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid add amount", str(exc))
            return

        if self.stack_existing_chk.isChecked():
            for dst in self._items_in_save:
                if dst.get("id") == item_id and self._row_editable(dst):
                    dst["qty"] = min(MAX_INVENTORY_QTY, int(dst.get("qty", 0) or 0) + add_qty)
                    self._sync_core_quantity_to_save(dst, int(dst.get("qty", 0) or 0))
                    self._mark_inventory_dirty()
                    self._mark_available_table_dirty()
                    dst_idx = self._items_in_save.index(dst)
                    if not self._refresh_visible_save_row(dst_idx):
                        self._populate_save_table()
                    if hasattr(self, "inventory_workspace"):
                        self.inventory_workspace.setCurrentIndex(0)
                    return

        if item_id in NON_DELETABLE_ITEM_IDS:
            QMessageBox.information(
                self,
                "Core inventory row already controlled",
                "This is a core economy row. Select the existing row and edit its quantity instead of creating a duplicate.",
            )
            return

        if not self._warn_or_confirm_experimental_append(1):
            return

        self._items_in_save.append(self._make_new_staged_item(src, add_qty))
        self._items_in_save.sort(key=lambda r: (bool(r.get("protected", False)), str(r.get("name") or "").lower(), str(r.get("id") or "")))
        self._mark_inventory_dirty()
        self._mark_available_table_dirty()
        self._populate_save_table()
        if hasattr(self, "inventory_workspace"):
            self.inventory_workspace.setCurrentIndex(0)

    def _on_add_all_visible_clicked(self) -> None:
        self._flush_pending_database_filter_refresh()
        if not self._filtered_items:
            return
        try:
            add_qty = self._parse_u32_text(self.add_qty_edit.text(), default=1, minimum=1)
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid add amount", str(exc))
            return

        existing_by_id = {gow2018_data.normalize_item_id(row.get("id")): row for row in self._items_in_save if gow2018_data.normalize_item_id(row.get("id"))}
        new_items: list[Dict] = []
        stacked = 0
        skipped_core = 0
        for src in self._filtered_items:
            item_id = gow2018_data.normalize_item_id(src.get("id"))
            if not item_id:
                continue
            existing = existing_by_id.get(item_id)
            if existing is not None and self.stack_existing_chk.isChecked() and self._row_editable(existing):
                existing["qty"] = min(MAX_INVENTORY_QTY, int(existing.get("qty", 0) or 0) + add_qty)
                self._sync_core_quantity_to_save(existing, int(existing.get("qty", 0) or 0))
                stacked += 1
                continue
            if item_id in NON_DELETABLE_ITEM_IDS:
                skipped_core += 1
                continue
            new_items.append(self._make_new_staged_item(src, add_qty))

        if new_items and not self._warn_or_confirm_experimental_append(len(new_items)):
            return

        if not new_items and stacked <= 0:
            QMessageBox.information(self, "Nothing to add", "All visible rows were core rows or invalid database entries.")
            return

        self._items_in_save.extend(new_items)
        self._items_in_save.sort(key=lambda r: (bool(r.get("protected", False)), str(r.get("name") or "").lower(), str(r.get("id") or "")))
        self._mark_inventory_dirty()
        self._mark_available_table_dirty()
        self._populate_save_table()
        if hasattr(self, "inventory_workspace"):
            self.inventory_workspace.setCurrentIndex(0)
        self.status_label.setText(
            f"Staged Add All Visible: {len(new_items):,} new rows, {stacked:,} stacked existing rows"
            + (f", {skipped_core:,} core rows skipped" if skipped_core else "")
            + ". Use Save/Save As to review and write."
        )

    def _selected_save_source_index(self) -> Optional[int]:
        # Do not flush here. This method is used during repaint/rebuild paths;
        # forcing a pending search refresh from inside a table refresh can cause
        # nested rebuilds and sluggish selection behavior. Button handlers flush
        # before using the current row when they need latest search results.
        row = self.table_save.currentRow()
        if row < 0:
            return None
        item = self.table_save.item(row, 0)
        if item is None:
            return None
        src_idx = item.data(Qt.ItemDataRole.UserRole)
        if src_idx is None:
            return None
        src_idx = int(src_idx)
        if src_idx < 0 or src_idx >= len(self._items_in_save):
            return None
        return src_idx

    def _on_remove_clicked(self) -> None:
        self._flush_pending_save_filter_refresh()
        src_idx = self._selected_save_source_index()
        if src_idx is None:
            return
        row = self._items_in_save[src_idx]
        if not self._row_removable(row):
            QMessageBox.information(
                self,
                "Core or locked record",
                "This row is required by the save structure. Advanced Unlock can allow manual quantity edits, but removal stays blocked because deleting the row can corrupt progression or slot structure.",
            )
            return
        name = row.get("name") or row.get("id") or "selected item"
        result = QMessageBox.question(
            self,
            "Remove inventory item?",
            f"Stage removal of {name}? The file is not changed until Save.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if result != QMessageBox.StandardButton.Yes:
            return
        self._items_in_save.pop(src_idx)
        self._mark_inventory_dirty()
        self._mark_available_table_dirty()
        self._populate_save_table()

    def _on_clear_clicked(self) -> None:
        self._flush_pending_save_filter_refresh()
        if not self._items_in_save:
            return
        result = QMessageBox.warning(
            self,
            "Clear editable inventory items?",
            "This will stage removal of every editable item in the active slot. Locked system/unknown rows will remain. The file is not changed until you press Save. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if result != QMessageBox.StandardButton.Yes:
            return
        before = len(self._items_in_save)
        self._items_in_save = [row for row in self._items_in_save if not self._row_removable(row)]
        removed = before - len(self._items_in_save)
        if removed <= 0:
            QMessageBox.information(
                self,
                "Nothing removable",
                "Only locked/core system records are currently visible for this slot.",
            )
            return
        self._mark_inventory_dirty()
        self._mark_available_table_dirty()
        self._populate_save_table()

    def _on_discard_inventory_edits(self) -> None:
        if not self._inventory_dirty:
            return
        result = QMessageBox.question(
            self,
            "Discard staged inventory edits?",
            "Reload the active slot inventory from the current in-memory save buffer and discard uncommitted inventory table edits?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if result != QMessageBox.StandardButton.Yes:
            return
        self._reload_items_in_save()
        self._sync_core_quantities_from_rows()
        self._mark_available_table_dirty()
        self._populate_save_table()
        self.status_label.setText("Inventory edits were discarded for the active slot. Other staged editor changes are unchanged.")
