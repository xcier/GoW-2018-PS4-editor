# app/ui/tabs/stats_tab.py
from __future__ import annotations

from typing import Callable, Optional, Dict

from PyQt6.QtCore import Qt
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
    QGridLayout,
    QFormLayout,
    QFrame,
    QScrollArea,
)

from app.core.file_context import FileContext
from app.core import gow2018_data

ARMOR_STAT_MARKERS = gow2018_data.ARMOR_STAT_MARKERS


class StatsTab(QWidget):
    """Stats/status page for the active God of War 2018 save slot."""

    def __init__(
        self,
        file_ctx: FileContext,
        parent: Optional[QWidget] = None,
        on_core_stats_changed: Optional[Callable[[set[str]], None]] = None,
    ) -> None:
        super().__init__(parent)
        self.file_ctx = file_ctx
        self._on_core_stats_changed = on_core_stats_changed

        self.diff_combo: QComboBox
        self.xp_box: QSpinBox
        self.hacksilver_box: QSpinBox
        self.info_label: QLabel
        self.armor_values_view: QPlainTextEdit
        self.armor_spinboxes: Dict[str, QSpinBox] = {}
        self.metric_values: Dict[str, QLabel] = {}
        self._dirty_core_fields: set[str] = set()

        self._build_ui()
        self._wire_signals()
        self.refresh_from_save()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea(self)
        scroll.setObjectName("DashboardScroll")
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidgetResizable(True)
        # Qt gives scroll-area viewports their own palette. Without explicit
        # object names/theme rules, that viewport can stay platform-white even
        # while the rest of the app is dark themed.
        scroll.viewport().setObjectName("DashboardViewport")
        scroll.viewport().setAutoFillBackground(False)
        root.addWidget(scroll)

        body = QWidget(scroll)
        body.setObjectName("DashboardBody")
        body.setAutoFillBackground(False)
        scroll.setWidget(body)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(16)

        self._build_metric_strip(layout, body)

        self.core_group = QGroupBox("Core Slot Stats", body)
        core_layout = QGridLayout(self.core_group)
        core_layout.setContentsMargins(18, 22, 18, 18)
        core_layout.setHorizontalSpacing(22)
        core_layout.setVerticalSpacing(14)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(12)

        self.diff_combo = QComboBox(self.core_group)
        self.diff_combo.addItems(["Story", "Balanced", "Challenge", "Give Me God of War"])
        self.diff_combo.setToolTip("Current active-slot difficulty value.")
        form.addRow("Difficulty", self.diff_combo)

        self.xp_box = QSpinBox(self.core_group)
        self.xp_box.setRange(0, 999_999_999)
        self.xp_box.setSingleStep(1_000)
        self.xp_box.setAccelerated(True)
        form.addRow("Kratos XP", self.xp_box)

        self.hacksilver_box = QSpinBox(self.core_group)
        self.hacksilver_box.setRange(0, 999_999_999)
        self.hacksilver_box.setSingleStep(1_000)
        self.hacksilver_box.setAccelerated(True)
        form.addRow("Hacksilver", self.hacksilver_box)

        core_layout.addLayout(form, 0, 0)

        quick_card = QFrame(self.core_group)
        quick_card.setObjectName("MetricCard")
        quick_layout = QVBoxLayout(quick_card)
        quick_layout.setContentsMargins(16, 14, 16, 14)
        quick_layout.setSpacing(10)
        quick_title = QLabel("Quick Actions", quick_card)
        quick_title.setObjectName("SectionTitle")
        quick_note = QLabel(
            "Core stat changes are staged into the in-memory save immediately, then flushed to disk on Save.",
            quick_card,
        )
        quick_note.setObjectName("MutedLabel")
        quick_note.setWordWrap(True)
        btn_max_xp = QPushButton("Max XP", quick_card)
        btn_max_hs = QPushButton("Max Hacksilver", quick_card)
        btn_max_xp.setObjectName("PrimaryButton")
        btn_max_hs.setObjectName("PrimaryButton")
        btn_max_xp.clicked.connect(self._on_max_xp_clicked)
        btn_max_hs.clicked.connect(self._on_max_hacksilver_clicked)
        quick_layout.addWidget(quick_title)
        quick_layout.addWidget(quick_note)
        quick_layout.addSpacing(4)
        quick_layout.addWidget(btn_max_xp)
        quick_layout.addWidget(btn_max_hs)
        quick_layout.addStretch(1)
        core_layout.addWidget(quick_card, 0, 1)
        core_layout.setColumnStretch(0, 2)
        core_layout.setColumnStretch(1, 1)
        layout.addWidget(self.core_group)

        self.armor_group = QGroupBox("Armor Stat Helpers", body)
        armor_layout = QVBoxLayout(self.armor_group)
        armor_layout.setContentsMargins(18, 22, 18, 18)
        armor_layout.setSpacing(14)

        intro = QLabel(
            "These helpers scan the save for known armor stat marker pairs. They do not guess offsets.",
            self.armor_group,
        )
        intro.setObjectName("MutedLabel")
        intro.setWordWrap(True)
        armor_layout.addWidget(intro)

        top_row = QHBoxLayout()
        btn_all = QPushButton("Max All Armor Stats to 99", self.armor_group)
        btn_all.setObjectName("PrimaryButton")
        btn_all.clicked.connect(self._on_max_all_armor_stats)
        top_row.addWidget(btn_all)
        top_row.addStretch(1)
        armor_layout.addLayout(top_row)

        stats_grid = QGridLayout()
        stats_grid.setHorizontalSpacing(12)
        stats_grid.setVerticalSpacing(12)

        def add_stat_card(index: int, key: str, label_text: str) -> None:
            card = QFrame(self.armor_group)
            card.setObjectName("MetricCard")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(14, 12, 14, 12)
            card_layout.setSpacing(8)

            lbl = QLabel(label_text, card)
            lbl.setObjectName("SectionTitle")
            spin = QSpinBox(card)
            spin.setRange(0, 999)
            spin.setSingleStep(1)
            spin.setValue(99)
            spin.setAccelerated(True)
            self.armor_spinboxes[key] = spin

            btn_apply = QPushButton("Apply", card)
            btn_apply.clicked.connect(lambda _, k=key: self._on_apply_single_stat(k))

            card_layout.addWidget(lbl)
            card_layout.addWidget(spin)
            card_layout.addWidget(btn_apply)
            row = index // 3
            col = index % 3
            stats_grid.addWidget(card, row, col)

        labels = [
            ("strength", "Strength"),
            ("runic", "Runic"),
            ("defense", "Defense"),
            ("vitality", "Vitality"),
            ("luck", "Luck"),
            ("cooldown", "Cooldown"),
        ]
        for idx, (key, label) in enumerate(labels):
            add_stat_card(idx, key, label)

        armor_layout.addLayout(stats_grid)

        self.info_label = QLabel("", self.armor_group)
        self.info_label.setObjectName("Chip")
        self.info_label.setWordWrap(True)
        armor_layout.addWidget(self.info_label)

        self.armor_values_view = QPlainTextEdit(self.armor_group)
        self.armor_values_view.setObjectName("LogView")
        self.armor_values_view.setReadOnly(True)
        self.armor_values_view.setMinimumHeight(160)
        self.armor_values_view.setPlaceholderText("Detected armor stat values appear here after loading a save.")
        armor_layout.addWidget(self.armor_values_view)

        layout.addWidget(self.armor_group, 1)
        layout.addStretch(1)


    def _build_metric_strip(self, layout: QVBoxLayout, parent: QWidget) -> None:
        strip = QFrame(parent)
        strip.setObjectName("HeroCard")
        strip_layout = QHBoxLayout(strip)
        strip_layout.setContentsMargins(16, 16, 16, 16)
        strip_layout.setSpacing(12)

        for key, label in (
            ("slot", "ACTIVE SLOT"),
            ("difficulty", "DIFFICULTY"),
            ("xp", "KRATOS XP"),
            ("hacksilver", "HACKSILVER"),
        ):
            card = QFrame(strip)
            card.setObjectName("MetricCard")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(16, 12, 16, 12)
            card_layout.setSpacing(4)

            label_widget = QLabel(label, card)
            label_widget.setObjectName("MetricLabel")
            value_widget = QLabel("—", card)
            value_widget.setObjectName("MetricValue")
            value_widget.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.metric_values[key] = value_widget

            card_layout.addWidget(label_widget)
            card_layout.addWidget(value_widget)
            strip_layout.addWidget(card, 1)

        layout.addWidget(strip)

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _wire_signals(self) -> None:
        self.diff_combo.currentIndexChanged.connect(lambda _=None: self._on_core_stat_changed("difficulty"))
        self.xp_box.valueChanged.connect(lambda _=None: self._on_core_stat_changed("kratos_xp"))
        self.hacksilver_box.valueChanged.connect(lambda _=None: self._on_core_stat_changed("hacksilver"))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def refresh_from_save(self) -> None:
        save = self.file_ctx.save
        if save is None:
            self._clear_ui()
            return

        self.core_group.setEnabled(True)
        self.armor_group.setEnabled(True)

        try:
            diff_index = int(getattr(save, "difficulty", 0))
        except (TypeError, ValueError):
            diff_index = 0

        self.diff_combo.blockSignals(True)
        self.diff_combo.setCurrentIndex(diff_index if 0 <= diff_index < self.diff_combo.count() else 0)
        self.diff_combo.blockSignals(False)

        xp_value = max(0, min(int(getattr(save, "kratos_xp", 0)), self.xp_box.maximum()))
        self.xp_box.blockSignals(True)
        self.xp_box.setValue(xp_value)
        self.xp_box.blockSignals(False)

        hs_value = max(0, min(int(getattr(save, "hacksilver", 0)), self.hacksilver_box.maximum()))
        self.hacksilver_box.blockSignals(True)
        self.hacksilver_box.setValue(hs_value)
        self.hacksilver_box.blockSignals(False)

        self._dirty_core_fields.clear()
        self._refresh_metric_cards()
        self._refresh_armor_stat_values()

    def refresh_from_context(self) -> None:
        self.refresh_from_save()

    def apply_to_save(self) -> None:
        if self._dirty_core_fields:
            self._commit_core_stats_to_save(mark_dirty=False)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _clear_ui(self) -> None:
        self.diff_combo.blockSignals(True)
        self.xp_box.blockSignals(True)
        self.hacksilver_box.blockSignals(True)
        self.diff_combo.setCurrentIndex(0)
        self.xp_box.setValue(0)
        self.hacksilver_box.setValue(0)
        self.diff_combo.blockSignals(False)
        self.xp_box.blockSignals(False)
        self.hacksilver_box.blockSignals(False)

        self.core_group.setEnabled(False)
        self.armor_group.setEnabled(False)
        self.info_label.setText("No save loaded.")
        self.armor_values_view.clear()
        self._dirty_core_fields.clear()
        self._refresh_metric_cards()

    def _refresh_metric_cards(self) -> None:
        save = self.file_ctx.save
        if not self.metric_values:
            return
        if save is None:
            for widget in self.metric_values.values():
                widget.setText("—")
            return

        difficulty_names = ["Story", "Balanced", "Challenge", "God of War"]
        diff_index = max(0, min(int(getattr(save, "difficulty", 0) or 0), len(difficulty_names) - 1))
        self.metric_values["slot"].setText(str(int(getattr(save, "active_slot", 1) or 1)))
        self.metric_values["difficulty"].setText(difficulty_names[diff_index])
        self.metric_values["xp"].setText(f"{int(getattr(save, 'kratos_xp', 0) or 0):,}")
        self.metric_values["hacksilver"].setText(f"{int(getattr(save, 'hacksilver', 0) or 0):,}")

    def _refresh_armor_stat_values(self) -> None:
        save = self.file_ctx.save
        if save is None or not hasattr(save, "get_armor_stat_values"):
            self.armor_values_view.setPlainText("No save loaded, or SaveFile is missing armor-stat readers.")
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

            rounded = [round(float(v), 2) for v in vals]
            unique_vals = sorted(set(rounded))

            spin = self.armor_spinboxes.get(key)
            if spin is not None:
                spin.blockSignals(True)
                rep_val = int(round(unique_vals[0]))
                spin.setValue(max(spin.minimum(), min(spin.maximum(), rep_val)))
                spin.blockSignals(False)

            if len(unique_vals) == 1:
                lines.append(f"{key}: {unique_vals[0]:.2f}  (x{len(vals)})")
            else:
                lines.append(f"{key}: {unique_vals[0]:.2f}..{unique_vals[-1]:.2f}  ({len(vals)} entries)")

        self.armor_values_view.setPlainText("\n".join(lines))

    # ------------------------------------------------------------------
    # Core stats callbacks
    # ------------------------------------------------------------------

    def _commit_core_stats_to_save(self, mark_dirty: bool = True) -> None:
        save = self.file_ctx.save
        if save is None or not self._dirty_core_fields:
            return

        fields = set(self._dirty_core_fields)
        if "difficulty" in fields:
            setattr(save, "difficulty", int(self.diff_combo.currentIndex()))
        if "kratos_xp" in fields:
            setattr(save, "kratos_xp", int(self.xp_box.value()))
        if "hacksilver" in fields:
            setattr(save, "hacksilver", int(self.hacksilver_box.value()))

        if hasattr(save, "commit_core_stats"):
            save.commit_core_stats(fields=fields)

        self._dirty_core_fields.clear()
        if hasattr(save, "_load_core_stats_from_binary"):
            save._load_core_stats_from_binary()

        if mark_dirty:
            self.file_ctx.mark_dirty()
            if self._on_core_stats_changed is not None:
                self._on_core_stats_changed(fields)

    def _on_core_stat_changed(self, field: str) -> None:
        self._dirty_core_fields.add(field)
        self._commit_core_stats_to_save(mark_dirty=True)
        self._refresh_metric_cards()

    def _on_max_xp_clicked(self) -> None:
        save = self.file_ctx.save
        if save is None:
            return
        max_val = self.xp_box.maximum()
        setattr(save, "kratos_xp", int(max_val))
        self.xp_box.blockSignals(True)
        self.xp_box.setValue(max_val)
        self.xp_box.blockSignals(False)
        if hasattr(save, "commit_core_stats"):
            save.commit_core_stats(fields={"kratos_xp"})
        if hasattr(save, "_load_core_stats_from_binary"):
            save._load_core_stats_from_binary()
        self._dirty_core_fields.clear()
        self.file_ctx.mark_dirty()
        if self._on_core_stats_changed is not None:
            self._on_core_stats_changed({"kratos_xp"})
        self.info_label.setText(f"XP set to max: {max_val:,}")
        self._refresh_metric_cards()

    def _on_max_hacksilver_clicked(self) -> None:
        save = self.file_ctx.save
        if save is None:
            return
        max_val = self.hacksilver_box.maximum()
        setattr(save, "hacksilver", int(max_val))
        self.hacksilver_box.blockSignals(True)
        self.hacksilver_box.setValue(max_val)
        self.hacksilver_box.blockSignals(False)
        if hasattr(save, "commit_core_stats"):
            save.commit_core_stats(fields={"hacksilver"})
        if hasattr(save, "_load_core_stats_from_binary"):
            save._load_core_stats_from_binary()
        self._dirty_core_fields.clear()
        self.file_ctx.mark_dirty()
        if self._on_core_stats_changed is not None:
            self._on_core_stats_changed({"hacksilver"})
        self.info_label.setText(f"Hacksilver set to max: {max_val:,}")
        self._refresh_metric_cards()

    # ------------------------------------------------------------------
    # Armor helpers
    # ------------------------------------------------------------------

    def _on_max_all_armor_stats(self) -> None:
        save = self.file_ctx.save
        if save is None:
            return
        if not hasattr(save, "boost_all_armor_stats"):
            self.info_label.setText("SaveFile is missing boost_all_armor_stats().")
            return

        result: Dict[str, int] = save.boost_all_armor_stats(99.0)
        patched = sum(int(v) for v in result.values()) if result else 0
        if patched:
            self.file_ctx.mark_dirty()
            pretty = ", ".join(f"{k}: {v}" for k, v in result.items())
            self.info_label.setText(f"Armor stats set to 99 where found. Patches: {pretty}")
        else:
            self.info_label.setText("No armor stat markers were patched for this save.")
        self._refresh_armor_stat_values()

    def _on_apply_single_stat(self, key: str) -> None:
        save = self.file_ctx.save
        if save is None:
            return
        if key not in ARMOR_STAT_MARKERS:
            self.info_label.setText(f"Unknown armor stat key: {key!r}.")
            return
        if not hasattr(save, "boost_armor_stat"):
            self.info_label.setText("SaveFile is missing boost_armor_stat().")
            return

        spin = self.armor_spinboxes.get(key)
        if spin is None:
            self.info_label.setText(f"No spinbox registered for armor stat key: {key!r}.")
            return

        value = float(spin.value())
        count = save.boost_armor_stat(key, value)
        if count:
            self.file_ctx.mark_dirty()
            self.info_label.setText(f"{key.capitalize()} set to {value:.2f} for {count} armor entries.")
        else:
            self.info_label.setText(f"No {key} armor stat markers found; nothing changed.")
        self._refresh_armor_stat_values()
