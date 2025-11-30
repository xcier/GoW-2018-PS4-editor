# app/ui/tabs/stats_tab.py
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QFormLayout,
    QGroupBox,
    QSpinBox,
    QComboBox,
    QLabel,
    QHBoxLayout,
    QPushButton,
)

from app.core.file_context import FileContext
from app.core.save_file import ARMOR_STAT_MARKERS


class StatsTab(QWidget):
    """
    Main tab: direct editing of core save values + 1-click armor stat cheats.

      - Difficulty (0–3)
      - XP
      - Hacksilver

      - Buttons to:
          * Max XP / Max Hacksilver
          * Max All Armor Stats to 99
          * Max individual armor stats (Defense, Vitality, Luck, Runic, Cooldown, Strength)
    """

    def __init__(self, file_ctx: FileContext, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.file_ctx = file_ctx

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # ------------------------------------------------------------------
        # Core stats group
        # ------------------------------------------------------------------
        stats_box = QGroupBox("Core Slot Stats", self)
        form = QFormLayout(stats_box)

        self.diff_combo = QComboBox(self)
        self.diff_combo.addItem("Story", 0)
        self.diff_combo.addItem("Balanced", 1)
        self.diff_combo.addItem("Challenge", 2)
        self.diff_combo.addItem("God of War", 3)
        self.diff_combo.currentIndexChanged.connect(self._on_changed)

        self.xp_box = QSpinBox(self)
        self.xp_box.setRange(0, 999_999_999)
        self.xp_box.valueChanged.connect(self._on_changed)

        self.hacksilver_box = QSpinBox(self)
        self.hacksilver_box.setRange(0, 999_999_999)
        self.hacksilver_box.valueChanged.connect(self._on_changed)

        form.addRow("Difficulty", self.diff_combo)
        form.addRow("XP", self.xp_box)
        form.addRow("Hacksilver", self.hacksilver_box)

        root.addWidget(stats_box)

        # ------------------------------------------------------------------
        # Quick "cheat" buttons (apply directly to save)
        # ------------------------------------------------------------------
        quick_row = QHBoxLayout()
        quick_row.setSpacing(6)

        self.btn_max_xp = QPushButton("Max XP", self)
        self.btn_max_xp.clicked.connect(self._on_max_xp)
        quick_row.addWidget(self.btn_max_xp)

        self.btn_max_hs = QPushButton("Max Hacksilver", self)
        self.btn_max_hs.clicked.connect(self._on_max_hs)
        quick_row.addWidget(self.btn_max_hs)

        quick_row.addStretch(1)
        root.addLayout(quick_row)

        # Armor stat cheats
        armor_box = QGroupBox("Armor Stat Cheats (Use Skiller's IDs)", self)
        armor_layout = QVBoxLayout(armor_box)

        row_all = QHBoxLayout()
        self.btn_all_stats = QPushButton("Max ALL Armor Stats to 99", self)
        self.btn_all_stats.clicked.connect(self._on_max_all_armor_stats)
        row_all.addWidget(self.btn_all_stats)
        row_all.addStretch(1)
        armor_layout.addLayout(row_all)

        # Per-stat row
        row_stats = QHBoxLayout()
        self.stat_buttons: dict[str, QPushButton] = {}

        for stat_key in ["defense", "vitality", "luck", "runic", "cooldown", "strength"]:
            btn = QPushButton(stat_key.capitalize(), self)
            btn.clicked.connect(lambda _checked=False, k=stat_key: self._on_max_single_stat(k))
            self.stat_buttons[stat_key] = btn
            row_stats.addWidget(btn)

        row_stats.addStretch(1)
        armor_layout.addLayout(row_stats)

        root.addWidget(armor_box)

        # Info label
        self.info_label = QLabel(
            "Open a decrypted memory.dat to edit these values.\n"
            "Armor stat cheats search for Skiller's markers in the save and "
            "set the following float to 99.0.",
            self,
        )
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self.info_label)

        self.setDisabled(True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def refresh_from_context(self) -> None:
        save = self.file_ctx.save
        if save is None:
            self.setDisabled(True)
            return

        self.setDisabled(False)

        self.xp_box.blockSignals(True)
        self.hacksilver_box.blockSignals(True)
        self.diff_combo.blockSignals(True)

        self.xp_box.setValue(getattr(save, "kratos_xp", 0))
        self.hacksilver_box.setValue(getattr(save, "hacksilver", 0))

        diff_val = getattr(save, "difficulty", 0)
        idx = 0
        for i in range(self.diff_combo.count()):
            if self.diff_combo.itemData(i) == diff_val:
                idx = i
                break
        self.diff_combo.setCurrentIndex(idx)

        self.xp_box.blockSignals(False)
        self.hacksilver_box.blockSignals(False)
        self.diff_combo.blockSignals(False)

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def _on_changed(self) -> None:
        save = self.file_ctx.save
        if save is None:
            return

        save.kratos_xp = self.xp_box.value()
        save.hacksilver = self.hacksilver_box.value()

        diff_index = self.diff_combo.currentIndex()
        diff_val = self.diff_combo.itemData(diff_index)
        if diff_val is None:
            diff_val = 0
        save.difficulty = int(diff_val)

        self.file_ctx.mark_dirty()

    def _on_max_xp(self) -> None:
        self.xp_box.setValue(999_999_999)

    def _on_max_hs(self) -> None:
        self.hacksilver_box.setValue(999_999_999)

    def _on_max_all_armor_stats(self) -> None:
        save = self.file_ctx.save
        if save is None:
            return

        result = save.boost_all_armor_stats(value=99.0)
        self.file_ctx.mark_dirty()

        # optional: quick feedback in the label
        pretty = ", ".join(f"{k}: {v}" for k, v in result.items())
        self.info_label.setText(
            f"Armor stats set to 99 where found.\nPatches -> {pretty}"
        )

    def _on_max_single_stat(self, key: str) -> None:
        save = self.file_ctx.save
        if save is None:
            return

        if key not in ARMOR_STAT_MARKERS:
            return

        count = save.boost_armor_stat(key, value=99.0)
        self.file_ctx.mark_dirty()
        self.info_label.setText(
            f"{key.capitalize()} set to 99 for {count} armor entries."
        )
