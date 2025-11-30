# app/ui/tabs/settings_tab.py
from __future__ import annotations

from typing import Optional, Protocol

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QCheckBox


class HasThemeControls(Protocol):
    def dark_mode_enabled(self) -> bool: ...
    def set_dark_mode(self, enabled: bool) -> None: ...


class SettingsTab(QWidget):
    """
    Simple Settings tab with a Dark Mode toggle.

    It talks to the MainWindow via the HasThemeControls protocol:
      - dark_mode_enabled() to init the checkbox
      - set_dark_mode(bool) when the user toggles it
    """

    def __init__(self, owner: HasThemeControls, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._owner = owner

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel("Settings", self)
        title.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        layout.addSpacing(8)

        appearance = QLabel("Appearance", self)
        appearance.setStyleSheet("font-weight: bold;")
        layout.addWidget(appearance)

        self.dark_checkbox = QCheckBox("Enable dark mode", self)
        self.dark_checkbox.setChecked(self._owner.dark_mode_enabled())
        self.dark_checkbox.toggled.connect(self._owner.set_dark_mode)
        layout.addWidget(self.dark_checkbox)

        layout.addStretch(1)
