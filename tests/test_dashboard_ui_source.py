from pathlib import Path


def test_dashboard_scroll_area_uses_themed_background_objects() -> None:
    stats_source = Path("app/ui/tabs/stats_tab.py").read_text(encoding="utf-8")
    theme_source = Path("app/ui/theme.py").read_text(encoding="utf-8")

    assert "DashboardScroll" in stats_source
    assert "DashboardViewport" in stats_source
    assert "DashboardBody" in stats_source
    assert "scroll.viewport().setAutoFillBackground(False)" in stats_source
    assert "QWidget#DashboardBody" in theme_source
    assert "QWidget#DashboardViewport" in theme_source
    assert "QScrollArea#DashboardScroll" in theme_source
