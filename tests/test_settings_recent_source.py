from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "app" / "ui" / "main_window.py").read_text(encoding="utf-8")
MAIN = (ROOT / "main.py").read_text(encoding="utf-8")


def test_main_window_persists_theme_window_and_recent_files() -> None:
    assert "QSettings" in SOURCE
    assert "_load_recent_files" in SOURCE
    assert "_remember_recent_file" in SOURCE
    assert 'files/recent' in SOURCE
    assert 'ui/theme' in SOURCE
    assert 'window/geometry' in SOURCE


def test_recent_files_menu_and_open_recent_handler_are_wired() -> None:
    assert 'QMenu("Open Recent"' in SOURCE
    assert "_open_recent_file" in SOURCE
    assert "Clear Recent Saves" in SOURCE
    assert "_default_file_dialog_dir" in SOURCE


def test_qapplication_uses_app_metadata() -> None:
    assert "app import __about__" in MAIN
    assert "setOrganizationName(__about__.__organization__)" in MAIN
    assert "setApplicationVersion(__about__.__version__)" in MAIN
