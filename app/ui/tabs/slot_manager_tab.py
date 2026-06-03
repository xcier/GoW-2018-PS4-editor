from __future__ import annotations

from typing import Callable, Optional

from PyQt6.QtCore import Qt
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
)

from app.core import gow2018_data
from app.core.file_context import FileContext


class SlotManagerTab(QWidget):
    """Safe overview of the 20 physical save slots."""

    def __init__(
        self,
        file_ctx: FileContext,
        on_open_slot: Optional[Callable[[int], None]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.file_ctx = file_ctx
        self.on_open_slot = on_open_slot
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
        title = QLabel("Slot Manager", hero)
        title.setObjectName("SectionTitle")
        subtitle = QLabel(
            "Review every physical slot, verify which ones are active, and manually open a specific slot when needed.",
            hero,
        )
        subtitle.setObjectName("MutedLabel")
        subtitle.setWordWrap(True)
        text_col.addWidget(title)
        text_col.addWidget(subtitle)
        hero_layout.addLayout(text_col, 1)

        self.active_chip = QLabel("No save loaded", hero)
        self.active_chip.setObjectName("Chip")
        hero_layout.addWidget(self.active_chip)
        root.addWidget(hero)

        action_bar = QHBoxLayout()
        self.btn_open_slot = QPushButton("Open Selected Slot", self)
        self.btn_open_slot.setObjectName("PrimaryButton")
        self.btn_open_slot.clicked.connect(self._open_selected_slot)
        self.btn_refresh = QPushButton("Refresh", self)
        self.btn_refresh.clicked.connect(self.refresh_from_context)
        action_bar.addWidget(self.btn_open_slot)
        action_bar.addWidget(self.btn_refresh)
        action_bar.addStretch(1)
        root.addLayout(action_bar)

        self.table = QTableWidget(self)
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Slot",
            "Status",
            "Last Played",
            "Difficulty",
            "XP",
            "Hacksilver",
            "Inventory",
            "Location / Objective",
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.setWordWrap(False)
        self.table.doubleClicked.connect(self._open_selected_slot)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        root.addWidget(self.table, 1)

        self.status_label = QLabel("Open a decrypted memory.dat to inspect slot health.", self)
        self.status_label.setObjectName("Chip")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

    @staticmethod
    def _summary_active(summary: Optional[dict]) -> bool:
        if not summary:
            return False
        try:
            if int(summary.get("last_played_raw", 0) or 0) > 0:
                return True
            if int(summary.get("xp", 0) or 0) > 0 or int(summary.get("hacksilver", 0) or 0) > 0:
                return True
        except Exception:
            pass
        return bool(str(summary.get("location", "") or "").strip())

    def refresh_from_context(self) -> None:
        save = self.file_ctx.save
        if save is None:
            self.table.setRowCount(0)
            self.active_chip.setText("No save loaded")
            self.active_chip.setObjectName("Chip")
            self.btn_open_slot.setEnabled(False)
            self.status_label.setText("No save loaded.")
            return

        raw = getattr(save, "raw", b"")
        active_slot = int(getattr(save, "active_slot", 1) or 1)
        rows = []
        for slot in range(1, 21):
            summary = save.summarize_slot(slot) if hasattr(save, "summarize_slot") else None
            anchor_valid = gow2018_data.inventory_anchor_is_valid(raw, slot)
            start, end = gow2018_data.inventory_region_for_slot(len(raw), slot)
            is_active = self._summary_active(summary)
            status = "Active" if slot == active_slot else ("Used" if is_active else "Empty")
            if is_active and not anchor_valid:
                status = "Used / inventory locked"
            inv = "Validated" if anchor_valid else ("Disabled" if start and end else "No region")
            rows.append((slot, status, summary, inv))

        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))
        for r, (slot, status, summary, inv) in enumerate(rows):
            xp = int(summary.get("xp", 0) or 0) if summary else 0
            hs = int(summary.get("hacksilver", 0) or 0) if summary else 0
            values = [
                str(slot),
                status,
                str(summary.get("last_played", "") or "") if summary else "",
                str(summary.get("difficulty_name", "") or "") if summary else "",
                f"{xp:,}",
                f"{hs:,}",
                inv,
                str(summary.get("location", "") or "") if summary else "",
            ]
            for c, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
                item.setData(Qt.ItemDataRole.UserRole, slot)
                if c in {0, 4, 5}:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(r, c, item)
        self.table.setSortingEnabled(True)

        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) == active_slot:
                self.table.selectRow(r)
                break

        newest = save.find_most_recent_active_slot() if hasattr(save, "find_most_recent_active_slot") else active_slot
        self.active_chip.setText(f"Open: slot {active_slot} · newest: slot {newest}")
        self.active_chip.setObjectName("GoodChip")
        self.active_chip.style().unpolish(self.active_chip)
        self.active_chip.style().polish(self.active_chip)
        self.btn_open_slot.setEnabled(True)
        used_count = sum(1 for _, _, summary, _ in rows if self._summary_active(summary))
        self.status_label.setText(f"Detected {used_count} used slot(s). Double-click any row to open that slot.")

    def _selected_slot(self) -> Optional[int]:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if item is None:
            return None
        data = item.data(Qt.ItemDataRole.UserRole)
        try:
            return int(data)
        except Exception:
            try:
                return int(item.text())
            except Exception:
                return None

    def _open_selected_slot(self) -> None:
        slot = self._selected_slot()
        if slot is None:
            return
        if self.on_open_slot is not None:
            self.on_open_slot(slot)
