from pathlib import Path


MAIN = Path("app/ui/main_window.py").read_text(encoding="utf-8")
SLOT_TOOLS = Path("app/ui/tabs/backup_tab.py").read_text(encoding="utf-8")


def test_slot_tools_replaces_separate_transfer_and_backup_pages() -> None:
    assert "⇄  Slot Tools" in MAIN
    assert "Slot Tools" in MAIN
    assert "SlotTransferTab" not in MAIN
    assert "slot_transfer_tab" not in MAIN
    assert "Slot Backups" not in MAIN


def test_slot_tools_contains_backup_restore_and_transfer_actions() -> None:
    assert "Backup Source" in SLOT_TOOLS
    assert "Copy Within Save" in SLOT_TOOLS
    assert "Copy Loaded → Other Save…" in SLOT_TOOLS
    assert "Other save → loaded save" in SLOT_TOOLS
    assert "Copy Other Save Slot → Loaded Slot" in SLOT_TOOLS
    assert "Export Source Package" in SLOT_TOOLS
    assert "Restore Selected → Loaded" in SLOT_TOOLS
    assert "Restore Selected → Other Save…" in SLOT_TOOLS
    assert "Import Package → Loaded" in SLOT_TOOLS


def test_staged_transfer_uses_normal_save_review_language() -> None:
    assert "This is staged in memory. Use Save/Save As" in SLOT_TOOLS
    assert "This writes the target file immediately and creates a rollback .bak first" in SLOT_TOOLS


def test_slot_tools_has_package_label_and_explicit_other_save_slot_prompt() -> None:
    assert "Rename Package" in SLOT_TOOLS
    assert "Label slot package" in SLOT_TOOLS
    assert "Target slot in other save" in SLOT_TOOLS
    assert "Loaded target slot" in SLOT_TOOLS
    assert "This labels the .gow2018slot file only" in SLOT_TOOLS
