# app/ui/tabs/inventory_tab.py
from __future__ import annotations

from typing import List, Dict, Optional

from PyQt6.QtCore import Qt
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
    QFrame,
    QAbstractItemView,
    QCheckBox,
)

from app.core.file_context import FileContext
from app.core import gow2018_data


class InventoryTab(QWidget):
    """
    Inventory editor for GoW 2018.

    Left side:
        - All known items from gow2018_items.json (database only)
        - Filter by Type + search box + "Hide Unknown items" checkbox

    Right side:
        - Items actually present in the currently loaded save (active slot)
        - Same "Hide Unknown items" checkbox hides unknown entries here too
          (but does not delete them from the save).

    Editing:
        - Add/Remove/Clear via buttons
        - Directly edit Qty column (double-click)
        - MainWindow calls apply_to_save() before saving to disk.
    """

    INVENTORY_TABLE_REL_OFFSET = 0x001041D
    INVENTORY_ENTRY_SIZE = 16
    INVENTORY_MAX_ENTRIES = 256  # safe upper bound

    def __init__(self, file_ctx: FileContext, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self._file_ctx = file_ctx

        self._all_items: List[Dict] = []
        self._filtered_items: List[Dict] = []

        # items in current slot: {id, name, type, qty}
        self._items_in_save: List[Dict] = []
        self._item_write_info: Dict[str, List[int]] = {}
        self._free_entry_positions: List[int] = []

        self._updating_save_table: bool = False
        self._hide_unknowns: bool = False

        self._build_ui()
        self._load_items_db()
        self._apply_filters()

        self.setDisabled(True)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # Filters row
        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)

        filter_row.addWidget(QLabel("Type:", self))

        self.type_combo = QComboBox(self)
        self.type_combo.addItem("All")
        self.type_combo.currentIndexChanged.connect(self._on_filter_changed)
        filter_row.addWidget(self.type_combo)

        filter_row.addWidget(QLabel("Search:", self))

        self.search_edit = QLineEdit(self)
        self.search_edit.setPlaceholderText("Search by name or ID...")
        self.search_edit.textChanged.connect(self._on_filter_changed)
        filter_row.addWidget(self.search_edit, 1)

        # NEW: Hide-unknowns checkbox
        self.hide_unknowns_chk = QCheckBox("Hide Unknown items", self)
        self.hide_unknowns_chk.toggled.connect(self._on_hide_unknowns_toggled)
        filter_row.addWidget(self.hide_unknowns_chk)

        layout.addLayout(filter_row)

        # Main area
        main_row = QHBoxLayout()
        main_row.setSpacing(8)

        # Left: database ------------------------------------------------
        left_col = QVBoxLayout()
        left_col.setSpacing(4)
        left_col.addWidget(QLabel("Available Items (database)", self))

        self.table_available = QTableWidget(self)
        self.table_available.setColumnCount(4)
        self.table_available.setHorizontalHeaderLabels(["#", "Name", "Type", "ID"])
        self.table_available.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table_available.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.table_available.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_available.verticalHeader().setVisible(False)
        left_col.addWidget(self.table_available, 1)

        main_row.addLayout(left_col, 2)

        # Middle: buttons ----------------------------------------------
        btn_col = QVBoxLayout()
        btn_col.addStretch(1)

        self.btn_add = QPushButton("→ Add →", self)
        self.btn_add.clicked.connect(self._on_add_clicked)
        btn_col.addWidget(self.btn_add)

        self.btn_remove = QPushButton("← Remove", self)
        self.btn_remove.clicked.connect(self._on_remove_clicked)
        btn_col.addWidget(self.btn_remove)

        self.btn_clear = QPushButton("Clear All", self)
        self.btn_clear.clicked.connect(self._on_clear_clicked)
        btn_col.addWidget(self.btn_clear)

        btn_col.addStretch(2)
        main_row.addLayout(btn_col)

        # Right: items in save -----------------------------------------
        right_col = QVBoxLayout()
        right_col.setSpacing(4)
        right_col.addWidget(QLabel("Items in Save", self))

        self.table_save = QTableWidget(self)
        self.table_save.setColumnCount(4)
        self.table_save.setHorizontalHeaderLabels(["Name", "Type", "ID", "Qty"])
        self.table_save.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table_save.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )

        self.table_save.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.SelectedClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
        )

        self.table_save.verticalHeader().setVisible(False)
        self.table_save.itemChanged.connect(self._on_save_table_item_changed)
        right_col.addWidget(self.table_save, 1)

        main_row.addLayout(right_col, 3)

        layout.addLayout(main_row, 1)

        # Footer note
        note = QLabel(
            "Open a decrypted memory.dat to view and edit items in the current slot.\n"
            "You can edit quantities directly in the Qty column.\n"
            "Remember: File → Save / Save As will commit changes to disk.",
            self,
        )
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        note.setFrameStyle(QFrame.Shape.NoFrame.value)
        layout.addWidget(note)

        self._configure_headers()

    def _configure_headers(self) -> None:
        hl = self.table_available.horizontalHeader()
        hl.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hl.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hl.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hl.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)

        hr = self.table_save.horizontalHeader()
        hr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hr.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hr.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_unknown_row(row: Dict) -> bool:
        """
        Decide whether a DB/save row counts as 'unknown' for hiding.
        We treat things like:
          - type: 'Unknown' or '?' or empty
          - name: '(Unknown)' or '' or startswith 'unknown'
        as unknown.
        """
        name = (row.get("name") or "").strip().lower()
        type_ = (row.get("type") or "").strip().lower()

        if type_ in ("unknown", "?", "") and (
            not name
            or name.startswith("unknown")
            or name.startswith("(unknown")
        ):
            return True
        return False

    # ------------------------------------------------------------------
    # Items DB + filters
    # ------------------------------------------------------------------

    def _load_items_db(self) -> None:
        try:
            self._all_items = gow2018_data.get_all_items()
        except Exception as exc:
            print(f"[InventoryTab] Failed to load items DB: {exc}")
            self._all_items = []

        # type list
        types: List[str] = []
        if hasattr(gow2018_data, "get_all_types"):
            try:
                types = list(gow2018_data.get_all_types())
            except Exception:
                types = []
        if not types:
            tset = {row.get("type") for row in self._all_items if row.get("type")}
            types = sorted(tset)

        self.type_combo.blockSignals(True)
        self.type_combo.clear()
        self.type_combo.addItem("All")
        for t in types:
            self.type_combo.addItem(t)
        self.type_combo.blockSignals(False)

    def _on_filter_changed(self) -> None:
        self._apply_filters()

    def _on_hide_unknowns_toggled(self, checked: bool) -> None:
        self._hide_unknowns = bool(checked)
        # Refilter DB side
        self._apply_filters()
        # Rebuild Items-in-save side
        self._populate_save_table()

    def _apply_filters(self) -> None:
        type_filter = self.type_combo.currentText()
        search = self.search_edit.text().strip().lower()

        def match(row: Dict) -> bool:
            if self._hide_unknowns and self._is_unknown_row(row):
                return False
            if type_filter and type_filter != "All":
                if (row.get("type") or "") != type_filter:
                    return False
            if search:
                name = (row.get("name") or "").lower()
                item_id = (row.get("id") or "").lower()
                if search not in name and search not in item_id:
                    return False
            return True

        self._filtered_items = [r for r in self._all_items if match(r)]
        self._populate_available_table()

    def _populate_available_table(self) -> None:
        table = self.table_available
        rows = self._filtered_items

        table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            idx_item = QTableWidgetItem(str(r + 1))
            idx_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            idx_item.setFlags(
                Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled
            )
            table.setItem(r, 0, idx_item)

            for col, key in enumerate(("name", "type", "id"), start=1):
                item = QTableWidgetItem(row.get(key) or "")
                item.setFlags(
                    Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled
                )
                table.setItem(r, col, item)

    # ------------------------------------------------------------------
    # Reading inventory from the save
    # ------------------------------------------------------------------

    def refresh_from_save(self) -> None:
        self._reload_items_in_save()
        self._populate_save_table()
        self.setDisabled(self._file_ctx.save is None)

    def refresh_from_context(self) -> None:
        self.refresh_from_save()

    def _reload_items_in_save(self) -> None:
        save = getattr(self._file_ctx, "save", None)
        if save is None:
            self._items_in_save = []
            self._item_write_info = {}
            self._free_entry_positions = []
            return

        raw: bytes = getattr(save, "raw", b"")
        if not raw:
            self._items_in_save = []
            self._item_write_info = {}
            self._free_entry_positions = []
            return

        slot_index = getattr(save, "active_slot", 1)
        base_offset = gow2018_data.resolve_slot_base_offset(slot_index)
        if base_offset <= 0 or base_offset >= len(raw):
            self._items_in_save = []
            self._item_write_info = {}
            self._free_entry_positions = []
            return

        start = base_offset + self.INVENTORY_TABLE_REL_OFFSET
        entry_size = self.INVENTORY_ENTRY_SIZE
        max_entries = self.INVENTORY_MAX_ENTRIES

        if start >= len(raw):
            self._items_in_save = []
            self._item_write_info = {}
            self._free_entry_positions = []
            return

        items_by_id = gow2018_data.get_items_by_id()

        self._item_write_info = {}
        self._free_entry_positions = []
        aggregated: Dict[str, Dict] = {}

        for i in range(max_entries):
            pos = start + i * entry_size
            if pos + 12 > len(raw):
                break

            id_bytes = raw[pos : pos + 8]
            qty = int.from_bytes(raw[pos + 8 : pos + 12], "little", signed=False)
            id_hex = id_bytes.hex().upper()

            if id_bytes == b"\x00" * 8 and qty == 0:
                self._free_entry_positions.append(pos)
                continue

            meta = items_by_id.get(id_hex)
            # If unknown ID, we'll still keep it but mark name/type so our
            # _is_unknown_row() can hide it when requested.
            if meta:
                name = meta.get("name") or ""
                type_ = meta.get("type") or ""
            else:
                name = "(Unknown)"
                type_ = "Unknown"

            if qty <= 0:
                continue

            lst = self._item_write_info.setdefault(id_hex, [])
            lst.append(pos)

            existing = aggregated.get(id_hex)
            if existing is None:
                aggregated[id_hex] = {
                    "id": id_hex,
                    "name": name,
                    "type": type_,
                    "qty": qty,
                }
            else:
                existing["qty"] += qty

        self._items_in_save = sorted(
            aggregated.values(),
            key=lambda r: (r["name"].lower(), r["id"]),
        )

    def _populate_save_table(self) -> None:
        """
        Build the right-side table. We may hide unknown rows, so we also
        store the underlying index of each visible row in the ID cell's
        UserRole for mapping edits/removals back into _items_in_save.
        """
        table = self.table_save
        self._updating_save_table = True

        # Build list of (index_in_items_in_save, row_dict) for visible rows
        visible_rows = []
        for idx, row in enumerate(self._items_in_save):
            if self._hide_unknowns and self._is_unknown_row(row):
                continue
            visible_rows.append((idx, row))

        table.setRowCount(len(visible_rows))

        for r, (src_idx, row) in enumerate(visible_rows):
            # Name
            name_item = QTableWidgetItem(row["name"])
            name_item.setFlags(
                Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled
            )
            table.setItem(r, 0, name_item)

            # Type
            type_item = QTableWidgetItem(row["type"])
            type_item.setFlags(
                Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled
            )
            table.setItem(r, 1, type_item)

            # ID (store underlying index in UserRole)
            id_item = QTableWidgetItem(row["id"])
            id_item.setFlags(
                Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled
            )
            id_item.setData(Qt.ItemDataRole.UserRole, src_idx)
            table.setItem(r, 2, id_item)

            # Qty (also store underlying index in UserRole)
            qty_item = QTableWidgetItem(str(row["qty"]))
            qty_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            qty_item.setFlags(
                Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsEditable
            )
            qty_item.setData(Qt.ItemDataRole.UserRole, src_idx)
            table.setItem(r, 3, qty_item)

        self._updating_save_table = False

    # ------------------------------------------------------------------
    # Handle manual edits in the Qty column
    # ------------------------------------------------------------------

    def _on_save_table_item_changed(self, item: QTableWidgetItem) -> None:
        if self._updating_save_table:
            return
        if item.column() != 3:
            return

        src_idx = item.data(Qt.ItemDataRole.UserRole)
        if src_idx is None:
            return
        src_idx = int(src_idx)
        if src_idx < 0 or src_idx >= len(self._items_in_save):
            return

        text = item.text().strip()
        if not text:
            new_qty = 0
        else:
            try:
                new_qty = int(text)
            except ValueError:
                # revert to previous
                self._updating_save_table = True
                item.setText(str(self._items_in_save[src_idx]["qty"]))
                self._updating_save_table = False
                return

        if new_qty < 0:
            new_qty = 0

        self._items_in_save[src_idx]["qty"] = new_qty

        self._updating_save_table = True
        item.setText(str(new_qty))
        self._updating_save_table = False

    # ------------------------------------------------------------------
    # Writing inventory back to the save
    # ------------------------------------------------------------------

    def apply_to_save(self) -> None:
        """
        Push current _items_in_save back into save.raw for the active slot.
        Unknown items are still written back even when hidden.
        """
        save = getattr(self._file_ctx, "save", None)
        if save is None:
            print("[InventoryTab] apply_to_save: no save loaded in FileContext.")
            return

        raw = getattr(save, "raw", None)
        if not raw:
            print("[InventoryTab] apply_to_save: save.raw is empty.")
            return

        if isinstance(raw, (bytes, bytearray)):
            buf = bytearray(raw)
        else:
            print("[InventoryTab] apply_to_save: unsupported save.raw type.")
            return

        # 1) Clear entries for removed items
        current_ids = {row["id"] for row in self._items_in_save}
        for item_id, positions in list(self._item_write_info.items()):
            if item_id not in current_ids:
                for pos_entry in positions:
                    buf[pos_entry : pos_entry + 8] = b"\x00" * 8
                    buf[pos_entry + 8 : pos_entry + 12] = (0).to_bytes(4, "little")
                self._free_entry_positions.extend(positions)
                del self._item_write_info[item_id]

        # 2) Write entries for current items
        for row in self._items_in_save:
            item_id = row["id"]
            qty = int(row["qty"])

            positions = self._item_write_info.get(item_id, [])

            if qty <= 0:
                # clear any existing entries for this id
                for pos_entry in positions:
                    buf[pos_entry : pos_entry + 8] = b"\x00" * 8
                    buf[pos_entry + 8 : pos_entry + 12] = (0).to_bytes(4, "little")
                    self._free_entry_positions.append(pos_entry)
                self._item_write_info[item_id] = []
                continue

            if not positions:
                if not self._free_entry_positions:
                    print(
                        f"[InventoryTab] apply_to_save: no free inventory slots for {item_id}."
                    )
                    continue
                pos_entry = self._free_entry_positions.pop(0)
                positions = [pos_entry]
                self._item_write_info[item_id] = positions

            remaining = qty
            id_bytes = bytes.fromhex(item_id)

            for idx, pos_entry in enumerate(positions):
                if idx == 0:
                    q_here = remaining
                else:
                    q_here = 0

                buf[pos_entry : pos_entry + 8] = id_bytes
                buf[pos_entry + 8 : pos_entry + 12] = int(q_here).to_bytes(
                    4, "little"
                )

        save.raw = bytes(buf)

        if hasattr(self._file_ctx, "mark_dirty"):
            try:
                self._file_ctx.mark_dirty()
            except Exception:
                pass

        print("[InventoryTab] apply_to_save: changes written into save.raw.")

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------

    def _on_add_clicked(self) -> None:
        row = self.table_available.currentRow()
        if row < 0 or row >= len(self._filtered_items):
            return

        src = self._filtered_items[row]
        item_id = src.get("id") or ""
        if not item_id:
            return

        for dst in self._items_in_save:
            if dst["id"] == item_id:
                dst["qty"] += 1
                break
        else:
            self._items_in_save.append(
                {
                    "id": item_id,
                    "name": src.get("name") or "",
                    "type": src.get("type") or "",
                    "qty": 1,
                }
            )

        self._items_in_save.sort(key=lambda r: (r["name"].lower(), r["id"]))
        self._populate_save_table()

    def _on_remove_clicked(self) -> None:
        row = self.table_save.currentRow()
        if row < 0:
            return

        id_item = self.table_save.item(row, 2)
        if id_item is None:
            return

        src_idx = id_item.data(Qt.ItemDataRole.UserRole)
        if src_idx is None:
            return
        src_idx = int(src_idx)
        if src_idx < 0 or src_idx >= len(self._items_in_save):
            return

        entry = self._items_in_save[src_idx]
        if entry["qty"] > 1:
            entry["qty"] -= 1
        else:
            del self._items_in_save[src_idx]

        self._populate_save_table()

    def _on_clear_clicked(self) -> None:
        self._items_in_save.clear()
        self._populate_save_table()
