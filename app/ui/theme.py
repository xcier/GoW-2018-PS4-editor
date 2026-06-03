from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Union

from PyQt6.QtWidgets import QApplication


@dataclass(frozen=True)
class ThemePalette:
    key: str
    name: str
    dark: bool
    accent: str
    accent_hover: str
    accent_muted: str
    window: str
    window_alt: str
    sidebar_top: str
    sidebar_bottom: str
    sidebar_border: str
    surface: str
    surface_alt: str
    surface_soft: str
    card_border: str
    input_bg: str
    text: str
    muted: str
    dim: str
    header_from: str
    header_to: str
    nav_checked_from: str
    nav_checked_to: str
    table_bg: str
    table_alt: str
    table_grid: str
    table_header: str
    selected: str
    selected_text: str
    chip_bg: str
    chip_border: str
    chip_text: str
    good_bg: str
    good_border: str
    good_text: str
    warn_bg: str
    warn_border: str
    warn_text: str
    danger_bg: str
    danger_border: str
    danger_text: str
    scrollbar: str


THEME_PRESETS: Dict[str, ThemePalette] = {
    "obsidian": ThemePalette(
        key="obsidian",
        name="Obsidian Forge",
        dark=True,
        accent="#f59e0b",
        accent_hover="#fbbf24",
        accent_muted="#7c4a03",
        window="#090d14",
        window_alt="#0b1020",
        sidebar_top="#111827",
        sidebar_bottom="#0b1020",
        sidebar_border="#223047",
        surface="#111827",
        surface_alt="#0f172a",
        surface_soft="#172033",
        card_border="#26344d",
        input_bg="#0b1220",
        text="#e7edf7",
        muted="#98a8bd",
        dim="#64748b",
        header_from="#151d2c",
        header_to="#0f172a",
        nav_checked_from="#31220a",
        nav_checked_to="#172033",
        table_bg="#0b1220",
        table_alt="#101a2b",
        table_grid="#1c2637",
        table_header="#172033",
        selected="#334155",
        selected_text="#ffffff",
        chip_bg="#1b2639",
        chip_border="#33435c",
        chip_text="#d7e0ec",
        good_bg="#0f2f22",
        good_border="#1f7049",
        good_text="#bbf7d0",
        warn_bg="#3a2609",
        warn_border="#8a6115",
        warn_text="#fde68a",
        danger_bg="#3b1720",
        danger_border="#7f1d1d",
        danger_text="#fecdd3",
        scrollbar="#334155",
    ),
    "bifrost": ThemePalette(
        key="bifrost",
        name="Bifröst Neon",
        dark=True,
        accent="#38bdf8",
        accent_hover="#7dd3fc",
        accent_muted="#075985",
        window="#050914",
        window_alt="#07111f",
        sidebar_top="#08111f",
        sidebar_bottom="#0b1222",
        sidebar_border="#153047",
        surface="#0d1726",
        surface_alt="#0b1322",
        surface_soft="#13233a",
        card_border="#1d4260",
        input_bg="#07111f",
        text="#e5f6ff",
        muted="#91bad4",
        dim="#5d7f96",
        header_from="#0c2238",
        header_to="#111827",
        nav_checked_from="#072d3f",
        nav_checked_to="#12233a",
        table_bg="#07111f",
        table_alt="#0d1a2b",
        table_grid="#14304a",
        table_header="#10233a",
        selected="#155e75",
        selected_text="#ffffff",
        chip_bg="#0c2a3d",
        chip_border="#17617f",
        chip_text="#c7efff",
        good_bg="#082f2a",
        good_border="#0f766e",
        good_text="#ccfbf1",
        warn_bg="#332908",
        warn_border="#a16207",
        warn_text="#fde68a",
        danger_bg="#3b1420",
        danger_border="#9f1239",
        danger_text="#ffe4e6",
        scrollbar="#1d5672",
    ),
    "spartan": ThemePalette(
        key="spartan",
        name="Spartan Crimson",
        dark=True,
        accent="#ef4444",
        accent_hover="#f87171",
        accent_muted="#7f1d1d",
        window="#10090a",
        window_alt="#160c0f",
        sidebar_top="#1a0f12",
        sidebar_bottom="#0f0b0c",
        sidebar_border="#3a1d22",
        surface="#1b1114",
        surface_alt="#160d10",
        surface_soft="#25151a",
        card_border="#44232a",
        input_bg="#120b0e",
        text="#fff1f2",
        muted="#d6a2aa",
        dim="#9f6872",
        header_from="#2a1217",
        header_to="#1b1114",
        nav_checked_from="#40171b",
        nav_checked_to="#23141a",
        table_bg="#120b0e",
        table_alt="#1a1014",
        table_grid="#321b20",
        table_header="#27151a",
        selected="#7f1d1d",
        selected_text="#ffffff",
        chip_bg="#2a171c",
        chip_border="#5b2931",
        chip_text="#ffe4e6",
        good_bg="#123022",
        good_border="#277044",
        good_text="#bbf7d0",
        warn_bg="#3a2609",
        warn_border="#8a6115",
        warn_text="#fde68a",
        danger_bg="#3b1720",
        danger_border="#be123c",
        danger_text="#ffe4e6",
        scrollbar="#5b2931",
    ),
    "daybreak": ThemePalette(
        key="daybreak",
        name="Daybreak Clean",
        dark=False,
        accent="#f59e0b",
        accent_hover="#d97706",
        accent_muted="#fed7aa",
        window="#f3f6fb",
        window_alt="#eef3fa",
        sidebar_top="#ffffff",
        sidebar_bottom="#ffffff",
        sidebar_border="#dbe3ef",
        surface="#ffffff",
        surface_alt="#f8fafc",
        surface_soft="#f1f5f9",
        card_border="#dbe3ef",
        input_bg="#ffffff",
        text="#111827",
        muted="#64748b",
        dim="#94a3b8",
        header_from="#ffffff",
        header_to="#fff7ed",
        nav_checked_from="#fff7ed",
        nav_checked_to="#ffffff",
        table_bg="#ffffff",
        table_alt="#f8fafc",
        table_grid="#e2e8f0",
        table_header="#f1f5f9",
        selected="#dbeafe",
        selected_text="#111827",
        chip_bg="#eef3fa",
        chip_border="#dbe3ef",
        chip_text="#334155",
        good_bg="#ecfdf5",
        good_border="#bbf7d0",
        good_text="#166534",
        warn_bg="#fffbeb",
        warn_border="#fde68a",
        warn_text="#92400e",
        danger_bg="#fff1f2",
        danger_border="#fecdd3",
        danger_text="#9f1239",
        scrollbar="#cbd5e1",
    ),
}

DEFAULT_THEME = "obsidian"


def theme_names() -> list[str]:
    return list(THEME_PRESETS.keys())


def iter_theme_presets() -> Iterable[ThemePalette]:
    return THEME_PRESETS.values()


def normalize_theme_name(theme: Union[str, bool, None]) -> str:
    if isinstance(theme, bool):
        return DEFAULT_THEME if theme else "daybreak"
    if not theme:
        return DEFAULT_THEME
    key = str(theme).strip().lower()
    return key if key in THEME_PRESETS else DEFAULT_THEME


def theme_display_name(theme: Union[str, bool, None]) -> str:
    return THEME_PRESETS[normalize_theme_name(theme)].name


def is_dark_theme(theme: Union[str, bool, None]) -> bool:
    return THEME_PRESETS[normalize_theme_name(theme)].dark


def _contrast_for_accent(p: ThemePalette) -> str:
    return "#07111f" if p.accent.lower() in {"#38bdf8", "#f59e0b"} else "#ffffff"


def build_stylesheet(theme: Union[str, bool, None] = DEFAULT_THEME) -> str:
    p = THEME_PRESETS[normalize_theme_name(theme)]
    accent_text = _contrast_for_accent(p)
    sidebar_bg = (
        f"qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {p.sidebar_top}, stop:1 {p.sidebar_bottom})"
        if p.sidebar_top != p.sidebar_bottom
        else p.sidebar_top
    )

    return f"""
* {{
    font-family: "Segoe UI Variable", "Segoe UI", "Inter", "Arial";
    font-size: 10pt;
}}
QMainWindow {{
    background-color: {p.window};
    color: {p.text};
}}
QWidget {{
    color: {p.text};
}}
QWidget#AppRoot, QWidget#ContentPane, QWidget#DashboardBody, QWidget#DashboardViewport, QWidget#InventoryPage, QStackedWidget {{
    background-color: {p.window};
}}
QLabel {{
    background: transparent;
    border: none;
}}
QMenuBar {{
    background: {p.window};
    color: {p.text};
    border-bottom: 1px solid {p.card_border};
    padding: 4px 8px;
}}
QMenuBar::item {{
    padding: 6px 10px;
    border-radius: 8px;
}}
QMenuBar::item:selected {{
    background: {p.surface_soft};
}}
QMenu {{
    background: {p.surface};
    color: {p.text};
    border: 1px solid {p.card_border};
    border-radius: 10px;
    padding: 8px;
}}
QMenu::item {{
    padding: 7px 28px 7px 18px;
    border-radius: 8px;
}}
QMenu::item:selected {{
    background: {p.surface_soft};
}}
QStatusBar {{
    background: {p.window};
    color: {p.dim};
    border-top: 1px solid {p.card_border};
    padding: 4px 10px;
}}
#Sidebar {{
    background: {sidebar_bg};
    border-right: 1px solid {p.sidebar_border};
}}
#BrandCard {{
    background: {p.surface_soft};
    border: 1px solid {p.card_border};
    border-radius: 24px;
}}
#BrandCard QLabel {{
    background: transparent;
    border: none;
}}
#BrandBadge {{
    background: {p.accent};
    color: {accent_text};
    border-radius: 17px;
    font-size: 21pt;
    font-weight: 950;
}}
#AppTitle {{
    color: {p.text};
    font-size: 15pt;
    font-weight: 900;
    letter-spacing: -0.2px;
}}
#AppSubtitle {{
    color: {p.muted};
    font-size: 9pt;
}}
#NavButton {{
    background: transparent;
    color: {p.muted};
    border: 1px solid transparent;
    border-radius: 16px;
    padding: 12px 14px;
    text-align: left;
    font-size: 10.5pt;
    font-weight: 800;
}}
#NavButton:hover {{
    background: {p.surface_soft};
    color: {p.text};
    border-color: {p.card_border};
}}
#NavButton:checked {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {p.nav_checked_from}, stop:1 {p.nav_checked_to});
    color: {p.text};
    border: 1px solid {p.accent_muted};
    border-left: 5px solid {p.accent};
}}
#SidebarFooter {{
    background: {p.surface_alt};
    border: 1px solid {p.card_border};
    border-radius: 20px;
}}
#Header {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {p.header_from}, stop:1 {p.header_to});
    border: 1px solid {p.card_border};
    border-radius: 26px;
}}
#Header QLabel {{
    background: transparent;
    border: none;
}}
#PageEyebrow {{
    color: {p.accent};
    font-size: 8.5pt;
    font-weight: 900;
    letter-spacing: 1.3px;
}}
#PageTitle {{
    color: {p.text};
    font-size: 23pt;
    font-weight: 950;
    letter-spacing: -0.7px;
}}
#PageSubtitle, #MutedLabel {{
    color: {p.muted};
}}
#SectionTitle {{
    color: {p.text};
    font-size: 13pt;
    font-weight: 950;
}}
#TinyLabel {{
    color: {p.dim};
    font-size: 8.5pt;
    font-weight: 850;
}}
#Card, #Surface, QGroupBox {{
    background: {p.surface};
    border: 1px solid {p.card_border};
    border-radius: 24px;
}}
#Card QLabel, #Surface QLabel, QGroupBox QLabel {{
    background: transparent;
    border: none;
}}
#SurfaceAlt {{
    background: {p.surface_alt};
    border: 1px solid {p.card_border};
    border-radius: 20px;
}}
#SoftCard {{
    background: {p.surface_alt};
    border: 1px solid {p.card_border};
    border-radius: 18px;
}}
#SoftCard QLabel {{
    background: transparent;
    border: none;
}}
#InventoryActionBar {{
    background: {p.surface_soft};
    border: 1px solid {p.chip_border};
    border-radius: 18px;
}}
#InventoryActionBar QLabel {{
    background: transparent;
    border: none;
}}
#InventoryActionBar QPushButton {{
    padding: 8px 12px;
}}
#HeroCard, #MetricCard {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {p.surface_soft}, stop:1 {p.surface});
    border: 1px solid {p.card_border};
    border-radius: 24px;
}}
#HeroCard QLabel, #MetricCard QLabel {{
    background: transparent;
    border: none;
}}
#MetricValue {{
    color: {p.text};
    font-size: 19pt;
    font-weight: 950;
    letter-spacing: -0.5px;
}}
#MetricLabel {{
    color: {p.dim};
    font-size: 8.5pt;
    font-weight: 900;
    letter-spacing: 0.8px;
}}
#Chip, #StatusPill {{
    background: {p.chip_bg};
    color: {p.chip_text};
    border: 1px solid {p.chip_border};
    border-radius: 999px;
    padding: 6px 12px;
    font-weight: 800;
}}
#GoodChip {{
    background: {p.good_bg};
    color: {p.good_text};
    border: 1px solid {p.good_border};
    border-radius: 999px;
    padding: 6px 12px;
    font-weight: 850;
}}
#WarnChip {{
    background: {p.warn_bg};
    color: {p.warn_text};
    border: 1px solid {p.warn_border};
    border-radius: 999px;
    padding: 6px 12px;
    font-weight: 850;
}}
#PrimaryButton {{
    background: {p.accent};
    color: {accent_text};
    border: none;
    border-radius: 14px;
    padding: 10px 16px;
    font-weight: 950;
}}
#PrimaryButton:hover {{
    background: {p.accent_hover};
}}
#SubtleButton {{
    background: {p.surface_soft};
    color: {p.text};
    border: 1px solid {p.card_border};
    border-radius: 14px;
    padding: 10px 16px;
    font-weight: 850;
}}
#SubtleButton:hover {{
    background: {p.surface_alt};
}}
#DangerButton {{
    background: {p.danger_bg};
    color: {p.danger_text};
    border: 1px solid {p.danger_border};
    border-radius: 14px;
    padding: 9px 14px;
    font-weight: 900;
}}
#DangerButton:hover {{
    border-color: {p.danger_text};
}}
QPushButton {{
    background: {p.surface_soft};
    color: {p.text};
    border: 1px solid {p.card_border};
    border-radius: 14px;
    padding: 9px 14px;
    font-weight: 800;
}}
QPushButton:hover {{
    background: {p.surface_alt};
    border-color: {p.muted};
}}
QPushButton:pressed {{
    background: {p.input_bg};
}}
QPushButton:disabled {{
    background: {p.surface};
    color: {p.dim};
    border-color: {p.card_border};
}}
QGroupBox {{
    margin-top: 20px;
    padding: 18px 16px 16px 16px;
    font-weight: 950;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 18px;
    padding: 0 8px;
    color: {p.text};
}}
QLineEdit, QComboBox, QSpinBox, QTextEdit, QTextBrowser, QPlainTextEdit {{
    background: {p.input_bg};
    color: {p.text};
    border: 1px solid {p.card_border};
    border-radius: 14px;
    padding: 8px 11px;
    selection-background-color: {p.accent};
    selection-color: {accent_text};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTextEdit:focus, QTextBrowser:focus, QPlainTextEdit:focus {{
    border: 1px solid {p.accent};
}}
QComboBox::drop-down {{
    border: none;
    width: 32px;
}}
QComboBox QAbstractItemView {{
    background: {p.surface};
    color: {p.text};
    border: 1px solid {p.card_border};
    selection-background-color: {p.selected};
    selection-color: {p.selected_text};
    outline: 0;
}}
QTabWidget#InventoryWorkspace {{
    background: transparent;
}}
QTabWidget#InventoryWorkspace::pane {{
    border: none;
    background: transparent;
    margin-top: 10px;
}}
QTabWidget#InventoryWorkspace QTabBar {{
    background: transparent;
    border: none;
}}
QTabWidget#InventoryWorkspace QTabBar::base {{
    height: 0px;
    background: transparent;
    border: none;
}}
QTabWidget#InventoryWorkspace QTabBar::tab {{
    background: {p.surface_soft};
    color: {p.muted};
    border: 1px solid {p.card_border};
    border-radius: 13px;
    padding: 8px 16px;
    margin-right: 6px;
    font-weight: 900;
}}
QTabWidget#InventoryWorkspace QTabBar::tab:selected {{
    background: {p.accent};
    color: {accent_text};
    border-color: {p.accent};
}}
QTabWidget#InventoryWorkspace QTabBar::tab:hover:!selected {{
    color: {p.text};
    border-color: {p.accent};
}}
QTabBar#InventoryTypeTabs {{
    background: transparent;
    border: none;
}}
QTabBar#InventoryTypeTabs::base {{
    height: 0px;
    background: transparent;
    border: none;
}}
QTabBar#InventoryTypeTabs::tab {{
    background: {p.surface_soft};
    color: {p.muted};
    border: 1px solid {p.card_border};
    border-radius: 13px;
    padding: 8px 14px;
    margin-right: 6px;
    font-weight: 850;
}}
QTabBar#InventoryTypeTabs::tab:selected {{
    background: {p.accent};
    color: {accent_text};
    border-color: {p.accent};
}}
QTabBar#InventoryTypeTabs::tab:hover:!selected {{
    color: {p.text};
    border-color: {p.accent};
}}
QTableWidget, QTableView {{
    background: {p.table_bg};
    alternate-background-color: {p.table_alt};
    color: {p.text};
    gridline-color: {p.table_grid};
    border: 1px solid {p.card_border};
    border-radius: 18px;
}}
QTableWidget::item {{
    padding: 9px 10px;
    border-bottom: 1px solid {p.table_grid};
}}
QTableWidget::item:selected {{
    background: {p.selected};
    color: {p.selected_text};
}}
QHeaderView::section {{
    background: {p.table_header};
    color: {p.muted};
    border: none;
    border-right: 1px solid {p.table_grid};
    border-bottom: 1px solid {p.table_grid};
    padding: 10px;
    font-weight: 950;
}}
QScrollArea {{
    border: none;
    background: {p.window};
}}
QScrollArea#DashboardScroll, QScrollArea#DashboardScroll > QWidget, QScrollArea#DashboardScroll > QWidget > QWidget {{
    border: none;
    background: {p.window};
}}
QScrollBar:vertical {{
    background: transparent;
    width: 12px;
    margin: 4px;
}}
QScrollBar::handle:vertical {{
    background: {p.scrollbar};
    border-radius: 6px;
    min-height: 36px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
QSplitter::handle {{
    background: {p.window_alt};
    margin: 0 5px;
}}
QCheckBox {{
    color: {p.text};
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 19px;
    height: 19px;
    border-radius: 7px;
    border: 1px solid {p.muted};
    background: {p.input_bg};
}}
QCheckBox::indicator:checked {{
    background: {p.accent};
    border: 1px solid {p.accent};
}}
QPlainTextEdit#LogView, QPlainTextEdit#HexView {{
    font-family: "Cascadia Mono", "Consolas", "Courier New", monospace;
    font-size: 9pt;
}}
QPlainTextEdit#HexView {{
    line-height: 1.25;
}}
QToolTip {{
    background: {p.surface};
    color: {p.text};
    border: 1px solid {p.card_border};
    padding: 6px;
}}
"""


def apply_app_theme(app: QApplication, theme: Union[str, bool, None] = DEFAULT_THEME) -> None:
    app.setStyleSheet(build_stylesheet(theme))
