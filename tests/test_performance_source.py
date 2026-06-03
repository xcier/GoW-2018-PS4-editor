from pathlib import Path


def test_inventory_filters_are_debounced_and_add_table_is_lazy() -> None:
    source = Path("app/ui/tabs/inventory_tab.py").read_text(encoding="utf-8")
    assert "QTimer" in source
    assert "_filter_timer.setInterval(120)" in source
    assert "_save_filter_timer.setInterval(120)" in source
    assert "_schedule_filter_refresh" in source
    assert "_flush_pending_filter_refreshes" in source
    assert "_available_table_dirty" in source
    assert "_should_populate_available_table" in source
    assert "self.inventory_workspace.currentChanged.connect(self._on_inventory_workspace_changed)" in source


def test_main_window_defers_heavy_page_refreshes_until_page_is_opened() -> None:
    source = Path("app/ui/main_window.py").read_text(encoding="utf-8")
    assert "self._stale_pages" in source
    assert "_refresh_current_page_if_stale" in source
    assert "_mark_pages_stale" in source
    assert "Opening/switching saves used to eagerly rebuild every page" in source
    assert "self.stack.currentChanged.connect(self._on_stack_page_changed)" in source
