# app/ui/tabs/stats_tab.py
from __future__ import annotations

from typing import Optional, Dict

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


STAT_KEYS_ORDER = ["defense", "vitality", "luck", "runic", "cooldown", "strength"]


class StatsTab(QWidget):
    def __init__(self, file_ctx: FileContext, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.file_ctx = file_ctx

        # label widgets for detected armor stats
        self.armor_value_labels: Dict[str, QLabel] = {}

        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # Core stats group
        self.stats_box = QGroupBox("Core Slot Stats", self)
        form = QFormLayout(self.stats_box)

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

        root.addWidget(self.stats_box)

        # Quick stat buttons
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

        # Armor stat cheats group
        armor_box = QGroupBox("Armor Stat Cheats (Use Skiller's IDs)", self)
        armor_layout = QVBoxLayout(armor_box)

        all_row = QHBoxLayout()
        self.btn_all_stats = QPushButton("Max ALL Armor Stats to 99", self)
        self.btn_all_stats.clicked.connect(self._on_max_all_armor_stats)
        all_row.addWidget(self.btn_all_stats)
        all_row.addStretch(1)
        armor_layout.addLayout(all_row)

        row_stats = QHBoxLayout()
        self.stat_buttons: dict[str, QPushButton] = {}
        for stat_key in STAT_KEYS_ORDER:
            btn = QPushButton(stat_key.capitalize(), self)
            btn.clicked.connect(
                lambda _checked=False, k=stat_key: self._on_max_single_stat(k)
            )
            self.stat_buttons[stat_key] = btn
            row_stats.addWidget(btn)
        row_stats.addStretch(1)
        armor_layout.addLayout(row_stats)

        root.addWidget(armor_box)

        # Detected armor stat values
        values_box = QGroupBox("Detected Armor Stat Values (from save)", self)
        values_form = QFormLayout(values_box)

        for key in STAT_KEYS_ORDER:
            label = QLabel("—", self)
            label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            pretty_name = key.capitalize()
            values_form.addRow(pretty_name, label)
            self.armor_value_labels[key] = label

        root.addWidget(values_box)

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

        # Show which slot we are editing
        slot_index = getattr(save, "active_slot", 1)
        self.stats_box.setTitle(f"Core Slot Stats (Slot {slot_index})")

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

        # Also refresh the detected armor stat values from the save
        self._refresh_armor_stat_values()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _refresh_armor_stat_values(self) -> None:
        """
        Query the SaveFile for each armor stat's float values and show a
        compact summary per stat.
        """
        save = self.file_ctx.save
        if save is None or not hasattr(save, "get_armor_stat_values"):
            for lbl in self.armor_value_labels.values():
                lbl.setText("N/A")
            return

        for key, lbl in self.armor_value_labels.items():
            vals = save.get_armor_stat_values(key)
            if not vals:
                lbl.setText("—")
                continue

            # Round to 2 decimals for display
            rounded = [round(v, 2) for v in vals]
            unique_vals = sorted(set(rounded))

            if len(unique_vals) == 1:
                lbl.setText(f"{unique_vals[0]:.2f}  (x{len(vals)})")
            else:
                lbl.setText(
                    f"{unique_vals[0]:.2f}..{unique_vals[-1]:.2f}  ({len(vals)} entries)"
                )

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

        # Commit immediately into the underlying buffer for this slot
        if hasattr(save, "commit_core_stats"):
            save.commit_core_stats()

        self.file_ctx.mark_dirty()

        # Ask the main window to refresh the Slot combo label for this slot
        win = self.window()
        if win is not None and hasattr(win, "refresh_slot_summary_labels"):
            win.refresh_slot_summary_labels()

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

        pretty = ", ".join(f"{k}: {v}" for k, v in result.items())
        self.info_label.setText(
            f"Armor stats set to 99 where found.\nPatches -> {pretty}"
        )

        # Refresh displayed values after modifying the save
        self._refresh_armor_stat_values()

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

        # Refresh displayed values after modifying the save
        self._refresh_armor_stat_values()
