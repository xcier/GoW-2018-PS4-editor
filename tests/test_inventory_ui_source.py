from pathlib import Path


def test_inventory_ids_are_hidden_by_default_in_ui_source() -> None:
    source = Path("app/ui/tabs/inventory_tab.py").read_text(encoding="utf-8")
    assert "self._show_item_ids = False" in source
    assert "Show technical IDs" in source
    assert "setColumnHidden(2, hidden)" in source
    assert "Technical IDs are hidden by default" in source


def test_inventory_tab_has_real_editor_controls() -> None:
    source = Path("app/ui/tabs/inventory_tab.py").read_text(encoding="utf-8")
    assert "Filter current inventory" in source
    assert "selected_qty_edit" in source
    assert "_on_set_qty_clicked" in source
    assert "+ Amount" not in source
    assert "− Amount" not in source
    assert "_on_max_qty_clicked" in source
    assert "Max Selected" in source
    assert "Max All" in source
    assert "999,999,999" in source
    assert "Clear" in source
    assert "Discard" in source
    assert "Stack existing" in source
    assert "Inventory table is full" in source


def test_inventory_has_type_tabs_for_cleaner_navigation() -> None:
    source = Path("app/ui/tabs/inventory_tab.py").read_text(encoding="utf-8")
    assert "QTabBar" in source
    assert "INVENTORY_TYPE_GROUPS" in source
    assert "Resources" in source
    assert "Armor" in source
    assert "Runic / Weapon" in source
    assert "Exact Type" in source
    assert "_row_in_type_group" in source


def test_inventory_workspace_is_not_crowded_split_view() -> None:
    source = Path("app/ui/tabs/inventory_tab.py").read_text(encoding="utf-8")
    assert "QTabWidget" in source
    assert "InventoryWorkspace" in source
    assert "Current Slot" in source
    assert "Add Items" in source
    assert "QSplitter(" not in source
    assert "setStretchFactor" not in source


def test_inventory_tabs_hide_native_tab_baseline_and_actions_are_single_row() -> None:
    source = Path("app/ui/tabs/inventory_tab.py").read_text(encoding="utf-8")
    assert "setDrawBase(False)" in source
    assert "edit_layout = QHBoxLayout(edit_panel)" in source
    assert "+ Amount" not in source
    assert "− Amount" not in source


def test_inventory_has_advanced_unlock_for_manual_locked_row_edits() -> None:
    source = Path("app/ui/tabs/inventory_tab.py").read_text(encoding="utf-8")
    assert "self._unlock_locked_rows = False" in source
    assert "Advanced unlock" in source
    assert "_on_unlock_locked_toggled" in source
    assert "return not bool(row.get(\"protected\", False)) or bool(self._unlock_locked_rows)" in source
    assert "return \"Unlocked\" if self._unlock_locked_rows else \"Locked\"" in source
    assert "still cannot be removed" in source


def test_inventory_max_all_stays_safe_when_advanced_unlock_is_enabled() -> None:
    source = Path("app/ui/tabs/inventory_tab.py").read_text(encoding="utf-8")
    assert "def _row_bulk_editable" in source
    assert "editable_rows = [row for row in self._items_in_save if self._row_bulk_editable(row)]" in source
    assert "Locked/system rows will not be changed by Max All" in source
    assert "Max Selected" in source


def test_advanced_unlock_quantity_edits_are_not_blocked_by_protected_flag() -> None:
    source = Path("app/ui/tabs/inventory_tab.py").read_text(encoding="utf-8")
    assert "if not self._row_editable(row):\n            return" in source
    assert "if not self._row_editable(self._items_in_save[src_idx]):\n            return" in source
    assert "if bool(row.get(\"protected\", False)):\n            return\n        new_qty" not in source


def test_inventory_click_lag_reduction_avoids_full_repopulate_after_single_qty_edit() -> None:
    source = Path("app/ui/tabs/inventory_tab.py").read_text(encoding="utf-8")
    assert "def _refresh_visible_save_row" in source
    assert "blockSignals(True)" in source
    assert "setUpdatesEnabled(False)" in source
    assert "if not self._refresh_visible_save_row(src_idx):\n            self._populate_save_table()" in source
    assert "self._save_table_populating" in source


def test_inventory_hides_raw_unknown_rows_by_default_but_keeps_inferred_categories() -> None:
    source = Path("app/ui/tabs/inventory_tab.py").read_text(encoding="utf-8")
    assert "self._hide_unknowns = True" in source
    assert "Hide unknown/system rows" in source
    assert "Technical / Unclassified" in source
    assert "Weapon / Upgrade" in source
    assert "Perk / Enchantment" in source


def test_add_items_page_shows_owned_quantities_and_open_slot_capacity() -> None:
    source = Path("app/ui/tabs/inventory_tab.py").read_text(encoding="utf-8")
    assert 'self.available_capacity_chip = QLabel("0 open slots"' in source
    assert 'self.table_available.setHorizontalHeaderLabels(["Name", "You Have", "Type", "Add Action", "ID"])' in source
    assert "def _owned_text_for_item_id" in source
    assert "self._current_qty_by_item_id" in source
    assert "Open item slots" in source
    assert "You Have column" in source
    assert "Add Action" in source
    assert "self.table_available.setColumnHidden(4, hidden)" in source


def test_add_items_selected_detail_shows_current_quantity_before_adding() -> None:
    source = Path("app/ui/tabs/inventory_tab.py").read_text(encoding="utf-8")
    assert "You have {self._format_qty(owned_qty)}" in source
    assert "Open item slots {open_slots:,}" in source
    assert "def _add_action_text_for_item_id" in source


def test_inventory_has_experimental_append_and_add_all_visible() -> None:
    source = Path("app/ui/tabs/inventory_tab.py").read_text(encoding="utf-8")
    assert "self._experimental_append_rows = False" in source
    assert "Experimental append" in source
    assert "Add All Visible" in source
    assert "_on_add_all_visible_clicked" in source
    assert "allow_overflow_append=self._experimental_append_rows" in source
    assert "This may overwrite unknown slot data" in source
