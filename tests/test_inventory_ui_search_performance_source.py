from __future__ import annotations

from pathlib import Path

SOURCE = Path("app/ui/tabs/inventory_tab.py").read_text(encoding="utf-8")


def _function_body(name: str) -> str:
    marker = f"    def {name}("
    start = SOURCE.index(marker)
    next_start = SOURCE.find("\n    def ", start + 1)
    if next_start == -1:
        return SOURCE[start:]
    return SOURCE[start:next_start]


def test_database_search_is_inside_add_items_page() -> None:
    assert 'database_search_row = QHBoxLayout()' in SOURCE
    assert 'Search Database' in SOURCE
    # The main filter strip should not have a global database search that looks
    # broken while the Current Slot page is visible.
    top_strip = SOURCE[SOURCE.index('refine_row = QHBoxLayout()'):SOURCE.index('self.inventory_workspace = QTabWidget')]
    assert 'Database Search' not in top_strip


def test_database_search_no_longer_rebuilds_current_inventory_table() -> None:
    body = _function_body("_run_deferred_filter_refresh")
    assert "self._apply_filters()" in body
    assert "self._populate_save_table()" not in body


def test_current_inventory_actions_do_not_flush_database_search() -> None:
    for name in ("_on_set_qty_clicked", "_on_max_qty_clicked", "_on_max_all_clicked", "_on_remove_clicked", "_on_clear_clicked"):
        body = _function_body(name)
        assert "_flush_pending_save_filter_refresh" in body
        assert "_flush_pending_filter_refreshes" not in body


def test_available_selection_only_runs_when_add_items_page_is_visible() -> None:
    body = _function_body("_selected_available_item")
    assert "if not self._should_populate_available_table():" in body
    assert "return None" in body
    assert "_flush_pending_database_filter_refresh" in body


def test_inventory_tables_avoid_resize_to_contents() -> None:
    assert "ResizeToContents" not in SOURCE
    assert "Interactive" in _function_body("_configure_headers")


def test_database_search_uses_indexed_multi_term_matching() -> None:
    assert 'row["_search_text"] = self._build_search_text(row)' in SOURCE
    assert "def _search_matches" in SOURCE
    assert "return all(term in haystack for term in terms)" in SOURCE
