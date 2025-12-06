# app/ui/tabs/stats_tab.py
from __future__ import annotations

from typing import Optional, Dict, Any

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QSpinBox,
    QPushButton,
    QGroupBox,
    QPlainTextEdit,
)

from app.core.file_context import FileContext
    # noinspection PyUnresolvedReferences
from app.core import gow2018_data

# Reuse the shared armor marker mapping from gow2018_data
ARMOR_STAT_MARKERS = gow2018_data.ARMOR_STAT_MARKERS


class StatsTab(QWidget):
    """
    Combined Stats / Status page:

    - Shows and lets you edit:
        * Difficulty
        * Kratos XP
        * Hacksilver

    - Also exposes convenience controls for armor stats:
        * "Max ALL Armor Stats to 99" cheat
        * Per-stat spinboxes so the user can choose values manually
          and apply them (Strength, Runic, etc.)

    The actual binary work is delegated to app.core.save_file.SaveFile.
    """

    def __init__(self, file_ctx: FileContext, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.file_ctx = file_ctx

        self.diff_combo: QComboBox
        self.xp_box: QSpinBox
        self.hacksilver_box: QSpinBox
        self.info_label: QLabel
        self.armor_values_view: QPlainTextEdit

        # New: per-stat spinboxes for armor
        self.armor_spinboxes: Dict[str, QSpinBox] = {}

        self._build_ui()
        self._wire_signals()
        self.refresh_from_save()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(12)

        # --------------------------------------------------------------
        # Core stats group (Difficulty / XP / Hacksilver)
        # --------------------------------------------------------------
        core_group = QGroupBox("Core Stats (Editable)", self)
        core_layout = QVBoxLayout(core_group)
        core_layout.setSpacing(8)

        # Difficulty row
        diff_row = QHBoxLayout()
        diff_label = QLabel("Difficulty:", core_group)
        self.diff_combo = QComboBox(core_group)

        # Order here should match whatever mapping you use in SaveFile
        # (e.g. 0=Story, 1=Balanced, 2=Challenge, 3=Give Me GoW).
        self.diff_combo.addItems(
            [
                "Story",
                "Balanced",
                "Challenge",
                "Give Me God of War",
            ]
        )

        diff_row.addWidget(diff_label)
        diff_row.addWidget(self.diff_combo, 1)
        core_layout.addLayout(diff_row)

        # XP row
        xp_row = QHBoxLayout()
        xp_label = QLabel("Kratos XP:", core_group)
        self.xp_box = QSpinBox(core_group)
        self.xp_box.setRange(0, 999_999_999)  # safe u32-friendly slice
        self.xp_box.setSingleStep(1_000)

        xp_row.addWidget(xp_label)
        xp_row.addWidget(self.xp_box, 1)
        core_layout.addLayout(xp_row)

        # Hacksilver row
        hs_row = QHBoxLayout()
        hs_label = QLabel("Hacksilver:", core_group)
        self.hacksilver_box = QSpinBox(core_group)
        self.hacksilver_box.setRange(0, 999_999_999)
        self.hacksilver_box.setSingleStep(1_000)

        hs_row.addWidget(hs_label)
        hs_row.addWidget(self.hacksilver_box, 1)
        core_layout.addLayout(hs_row)

        # Quick buttons: Max XP / Max Hacksilver
        quick_row = QHBoxLayout()
        btn_max_xp = QPushButton("Set XP to Max", core_group)
        btn_max_hs = QPushButton("Set Hacksilver to Max", core_group)

        btn_max_xp.clicked.connect(self._on_max_xp_clicked)
        btn_max_hs.clicked.connect(self._on_max_hacksilver_clicked)

        quick_row.addWidget(btn_max_xp)
        quick_row.addWidget(btn_max_hs)
        core_layout.addLayout(quick_row)

        root.addWidget(core_group)

        # --------------------------------------------------------------
        # Armor cheats / inspector group
        # --------------------------------------------------------------
        armor_group = QGroupBox("Armor Stats Cheats & Editor", self)
        armor_layout = QVBoxLayout(armor_group)
        armor_layout.setSpacing(8)

        # Top row: "max all" (still classic cheat)
        top_row = QHBoxLayout()
        btn_all = QPushButton("Max ALL Armor Stats to 99", armor_group)
        btn_all.clicked.connect(self._on_max_all_armor_stats)
        top_row.addWidget(btn_all)
        armor_layout.addLayout(top_row)

        # Second row: per-stat spinboxes + apply buttons
        # Each column is: [Label][SpinBox][Apply Button]
        spin_row = QHBoxLayout()

        def add_stat_column(key: str, label_text: str) -> None:
            col = QVBoxLayout()
            lbl = QLabel(label_text, armor_group)
            spin = QSpinBox(armor_group)
            spin.setRange(0, 999)       # armor stat range; tweak if needed
            spin.setSingleStep(1)
            spin.setValue(99)           # default to 99 as a starting "max"
            self.armor_spinboxes[key] = spin

            btn_apply = QPushButton("Apply", armor_group)
            btn_apply.clicked.connect(lambda _, k=key: self._on_apply_single_stat(k))

            col.addWidget(lbl)
            col.addWidget(spin)
            col.addWidget(btn_apply)
            spin_row.addLayout(col)

        add_stat_column("strength", "Strength")
        add_stat_column("runic", "Runic")
        add_stat_column("defense", "Defense")
        add_stat_column("vitality", "Vitality")
        add_stat_column("luck", "Luck")
        add_stat_column("cooldown", "Cooldown")

        armor_layout.addLayout(spin_row)

        # Info label for user feedback
        self.info_label = QLabel("", armor_group)
        self.info_label.setWordWrap(True)
        armor_layout.addWidget(self.info_label)

        # Read-only view of detected armor stat values
        self.armor_values_view = QPlainTextEdit(armor_group)
        self.armor_values_view.setReadOnly(True)
        self.armor_values_view.setPlaceholderText(
            "Detected armor stat values from the currently loaded save will "
            "appear here. Load a save to populate."
        )
        armor_layout.addWidget(self.armor_values_view, 1)

        root.addWidget(armor_group, 1)

        # Spacer at bottom
        root.addStretch(1)

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _wire_signals(self) -> None:
        # Whenever a value changes, write it back to the current save immediately.
        self.diff_combo.currentIndexChanged.connect(self._on_core_stat_changed)
        self.xp_box.valueChanged.connect(self._on_core_stat_changed)
        self.hacksilver_box.valueChanged.connect(self._on_core_stat_changed)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def refresh_from_save(self) -> None:
        """
        Pull current values from FileContext.save (if present) and update
        all widgets.
        """
        save = self.file_ctx.save
        if save is None:
            self._clear_ui()
            return

        # Difficulty
        try:
            diff_index = int(getattr(save, "difficulty", 0))
        except (TypeError, ValueError):
            diff_index = 0

        if 0 <= diff_index < self.diff_combo.count():
            self.diff_combo.setCurrentIndex(diff_index)
        else:
            self.diff_combo.setCurrentIndex(0)

        # XP
        xp_value = int(getattr(save, "kratos_xp", 0))
        xp_value = max(0, min(xp_value, self.xp_box.maximum()))
        self.xp_box.blockSignals(True)
        self.xp_box.setValue(xp_value)
        self.xp_box.blockSignals(False)

        # Hacksilver
        hs_value = int(getattr(save, "hacksilver", 0))
        hs_value = max(0, min(hs_value, self.hacksilver_box.maximum()))
        self.hacksilver_box.blockSignals(True)
        self.hacksilver_box.setValue(hs_value)
        self.hacksilver_box.blockSignals(False)

        # Armor inspector + sync spinboxes to something reasonable
        self._refresh_armor_stat_values()

    def refresh_from_context(self) -> None:
        """
        Backwards-compat wrapper for older MainWindow code that calls
        stats_tab.refresh_from_context(). Just forwards to refresh_from_save().
        """
        self.refresh_from_save()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _clear_ui(self) -> None:
        self.diff_combo.setCurrentIndex(0)
        self.xp_box.blockSignals(True)
        self.hacksilver_box.blockSignals(True)

        self.xp_box.setValue(0)
        self.hacksilver_box.setValue(0)

        self.xp_box.blockSignals(False)
        self.hacksilver_box.blockSignals(False)

        self.info_label.setText("No save loaded.")
        self.armor_values_view.clear()

    def _refresh_armor_stat_values(self) -> None:
        """
        Ask SaveFile for a snapshot of armor stat values (per stat) and
        show a compact summary in the text area.

        Uses SaveFile.get_armor_stat_values(key: str) for each known key.
        Also sets each spinbox to a representative current value if found.
        """
        save = self.file_ctx.save
        if save is None or not hasattr(save, "get_armor_stat_values"):
            self.armor_values_view.setPlainText(
                "No save loaded, or SaveFile is missing get_armor_stat_values()."
            )
            return

        lines = []

        for key in ARMOR_STAT_MARKERS.keys():
            try:
                vals = save.get_armor_stat_values(key)
            except Exception as exc:  # noqa: BLE001
                lines.append(f"{key}: error while reading ({exc!r})")
                continue

            if not vals:
                lines.append(f"{key}: —")
                continue

            # Round to 2 decimals for display
            rounded = [round(float(v), 2) for v in vals]
            unique_vals = sorted(set(rounded))

            # Update spinbox to the first value (or any representative)
            spin = self.armor_spinboxes.get(key)
            if spin is not None:
                spin.blockSignals(True)
                try:
                    # clamp into spinbox range
                    rep_val = int(round(unique_vals[0]))
                    rep_val = max(spin.minimum(), min(spin.maximum(), rep_val))
                    spin.setValue(rep_val)
                finally:
                    spin.blockSignals(False)

            if len(unique_vals) == 1:
                lines.append(f"{key}: {unique_vals[0]:.2f}  (x{len(vals)})")
            else:
                lines.append(
                    f"{key}: {unique_vals[0]:.2f}..{unique_vals[-1]:.2f}  "
                    f"({len(vals)} entries)"
                )

        self.armor_values_view.setPlainText("\n".join(lines))

    # ------------------------------------------------------------------
    # Core stats callbacks
    # ------------------------------------------------------------------

    def _on_core_stat_changed(self) -> None:
        """
        Called whenever difficulty, XP, or hacksilver changes in the UI.
        Writes the new values back to the SaveFile and marks the file as
        dirty so Save triggers are enabled.
        """
        save = self.file_ctx.save
        if save is None:
            return

        # Difficulty (index-based mapping)
        setattr(save, "difficulty", int(self.diff_combo.currentIndex()))

        # XP & Hacksilver, both clamped already by QSpinBox ranges
        setattr(save, "kratos_xp", int(self.xp_box.value()))
        setattr(save, "hacksilver", int(self.hacksilver_box.value()))

        self.file_ctx.mark_dirty()

    def _on_max_xp_clicked(self) -> None:
        save = self.file_ctx.save
        if save is None:
            return

        max_val = self.xp_box.maximum()
        setattr(save, "kratos_xp", int(max_val))

        self.xp_box.blockSignals(True)
        self.xp_box.setValue(max_val)
        self.xp_box.blockSignals(False)

        self.file_ctx.mark_dirty()
        self.info_label.setText(f"XP set to max: {max_val}")

    def _on_max_hacksilver_clicked(self) -> None:
        save = self.file_ctx.save
        if save is None:
            return

        max_val = self.hacksilver_box.maximum()
        setattr(save, "hacksilver", int(max_val))

        self.hacksilver_box.blockSignals(True)
        self.hacksilver_box.setValue(max_val)
        self.hacksilver_box.blockSignals(False)

        self.file_ctx.mark_dirty()
        self.info_label.setText(f"Hacksilver set to max: {max_val}")

    # ------------------------------------------------------------------
    # Armor cheats / editor callbacks
    # ------------------------------------------------------------------

    def _on_max_all_armor_stats(self) -> None:
        """
        Classic cheat: set *all* armor stats to 99.0 using the SaveFile
        helper boost_all_armor_stats.
        """
        save = self.file_ctx.save
        if save is None:
            return

        if not hasattr(save, "boost_all_armor_stats"):
            self.info_label.setText(
                "SaveFile is missing boost_all_armor_stats(). "
                "Please update app/core/save_file.py."
            )
            return

        result: Dict[str, int] = save.boost_all_armor_stats(99.0)
        self.file_ctx.mark_dirty()

        if not result:
            self.info_label.setText(
                "No armor stats were patched. (No matching entries found.)"
            )
        else:
            pretty = ", ".join(f"{k}: {v}" for k, v in result.items())
            self.info_label.setText(
                f"Armor stats set to 99 where found.\nPatches -> {pretty}"
            )

        # Refresh displayed values after modifying the save
        self._refresh_armor_stat_values()

    def _on_apply_single_stat(self, key: str) -> None:
        """
        Apply the value from that stat's spinbox to all armor entries
        for this stat via SaveFile.boost_armor_stat.
        """
        save = self.file_ctx.save
        if save is None:
            return

        if key not in ARMOR_STAT_MARKERS:
            self.info_label.setText(
                f"Unknown armor stat key: {key!r}. Check ARMOR_STAT_MARKERS."
            )
            return

        if not hasattr(save, "boost_armor_stat"):
            self.info_label.setText(
                "SaveFile is missing boost_armor_stat(). "
                "Please update app/core/save_file.py."
            )
            return

        spin = self.armor_spinboxes.get(key)
        if spin is None:
            self.info_label.setText(
                f"No spinbox registered for armor stat key: {key!r}."
            )
            return

        value = float(spin.value())
        count = save.boost_armor_stat(key, value)
        self.file_ctx.mark_dirty()

        self.info_label.setText(
            f"{key.capitalize()} set to {value:.2f} for {count} armor entries."
        )

        # Refresh displayed values after modifying the save
        self._refresh_armor_stat_values()
