# app/ui/tabs/settings_tab.py
from __future__ import annotations

from typing import Optional, Protocol

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QFrame, QComboBox


class HasThemeControls(Protocol):
    def available_theme_names(self) -> list[str]: ...
    def current_theme_name(self) -> str: ...
    def current_theme_display_name(self) -> str: ...
    def theme_display_name(self, theme_name: str) -> str: ...
    def dark_mode_enabled(self) -> bool: ...
    def set_dark_mode(self, enabled: bool) -> None: ...
    def set_theme_name(self, theme_name: str) -> None: ...


class SettingsTab(QWidget):
    """Settings tab for lightweight editor preferences."""

    def __init__(self, owner: HasThemeControls, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._owner = owner
        self.theme_combo: QComboBox
        self.dark_checkbox: QCheckBox
        self.theme_note: QLabel

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(16)

        hero = QFrame(self)
        hero.setObjectName("HeroCard")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(18, 18, 18, 18)
        hero_layout.setSpacing(8)
        title = QLabel("Editor Preferences", hero)
        title.setObjectName("SectionTitle")
        note = QLabel(
            "Tune the workspace without weakening the safety model: validated inventory writes, atomic backups, and explicit dirty-state warnings stay on in every style.",
            hero,
        )
        note.setObjectName("MutedLabel")
        note.setWordWrap(True)
        hero_layout.addWidget(title)
        hero_layout.addWidget(note)
        layout.addWidget(hero)

        row = QHBoxLayout()
        row.setSpacing(16)

        appearance_card = QFrame(self)
        appearance_card.setObjectName("Card")
        appearance_layout = QVBoxLayout(appearance_card)
        appearance_layout.setContentsMargins(18, 18, 18, 18)
        appearance_layout.setSpacing(12)
        appearance_title = QLabel("Appearance", appearance_card)
        appearance_title.setObjectName("SectionTitle")
        appearance_layout.addWidget(appearance_title)

        appearance_note = QLabel(
            "Pick a built-in theme. Ctrl+T cycles through styles from anywhere in the app. Your theme and recent saves are remembered between launches.",
            appearance_card,
        )
        appearance_note.setObjectName("MutedLabel")
        appearance_note.setWordWrap(True)
        appearance_layout.addWidget(appearance_note)

        self.theme_combo = QComboBox(appearance_card)
        self._populate_theme_combo()
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        appearance_layout.addWidget(self.theme_combo)

        self.theme_note = QLabel("", appearance_card)
        self.theme_note.setObjectName("Chip")
        self.theme_note.setWordWrap(True)
        appearance_layout.addWidget(self.theme_note)

        self.dark_checkbox = QCheckBox("Use the default dark workspace", appearance_card)
        self.dark_checkbox.setChecked(self._owner.dark_mode_enabled())
        self.dark_checkbox.toggled.connect(self._owner.set_dark_mode)
        appearance_layout.addWidget(self.dark_checkbox)
        appearance_layout.addStretch(1)
        row.addWidget(appearance_card, 1)

        safety_card = QFrame(self)
        safety_card.setObjectName("Card")
        safety_layout = QVBoxLayout(safety_card)
        safety_layout.setContentsMargins(18, 18, 18, 18)
        safety_layout.setSpacing(12)
        safety_title = QLabel("Safety Defaults", safety_card)
        safety_title.setObjectName("SectionTitle")
        safety_layout.addWidget(safety_title)

        for text in (
            "Inventory writes stay disabled until the XP-table anchor validates.",
            "Save and Save As write atomically and create timestamped rollback backups.",
            "Changing slots commits staged edits before loading the next slot.",
            "Opening another file or closing the editor warns about unsaved changes.",
            "Recent files only store local paths; save contents are never copied into settings.",
        ):
            chip = QLabel(f"✓ {text}", safety_card)
            chip.setObjectName("GoodChip")
            chip.setWordWrap(True)
            safety_layout.addWidget(chip)

        safety_layout.addStretch(1)
        row.addWidget(safety_card, 1)

        layout.addLayout(row)
        layout.addStretch(1)
        self.refresh_theme_state()

    def _populate_theme_combo(self) -> None:
        self.theme_combo.blockSignals(True)
        self.theme_combo.clear()
        for key in self._owner.available_theme_names():
            self.theme_combo.addItem(self._owner.theme_display_name(key), key)
        self.theme_combo.blockSignals(False)

    def refresh_theme_state(self) -> None:
        current = self._owner.current_theme_name()
        self.theme_combo.blockSignals(True)
        idx = self.theme_combo.findData(current)
        self.theme_combo.setCurrentIndex(max(0, idx))
        self.theme_combo.blockSignals(False)

        self.dark_checkbox.blockSignals(True)
        self.dark_checkbox.setChecked(self._owner.dark_mode_enabled())
        self.dark_checkbox.blockSignals(False)

        self.theme_note.setText(f"Active theme: {self._owner.current_theme_display_name()}")

    def _on_theme_changed(self, _index: int = -1) -> None:
        key = self.theme_combo.currentData()
        if key:
            self._owner.set_theme_name(str(key))
