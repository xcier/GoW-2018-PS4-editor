from pathlib import Path


def test_main_window_has_slot_tools_and_save_preview_pages() -> None:
    source = Path("app/ui/main_window.py").read_text(encoding="utf-8")
    assert "SlotManagerTab" in source
    assert "BackupManagerTab" in source
    assert "Review changes before saving" in source
    assert "_confirm_save_preview" in source


def test_slot_manager_and_slot_tools_tabs_exist() -> None:
    assert Path("app/ui/tabs/slot_manager_tab.py").exists()
    assert Path("app/ui/tabs/backup_tab.py").exists()
    slot_source = Path("app/ui/tabs/slot_manager_tab.py").read_text(encoding="utf-8")
    backup_source = Path("app/ui/tabs/backup_tab.py").read_text(encoding="utf-8")
    assert "Open Selected Slot" in slot_source
    assert "Restore Selected → Loaded" in backup_source
    assert "Copy Loaded → Other Save…" in backup_source
    assert "Slot Tools" in backup_source
