from __future__ import annotations

from qa_weekly_analytics.viz.catalog import get_dashboard_charts


def test_dashboard_catalog_contains_expected_charts() -> None:
    charts = get_dashboard_charts()

    keys = {chart.key for chart in charts}

    assert "kpi_cards" in keys
    assert "trend_lv" in keys
    assert "top_agents" in keys
    assert "top_reasons" in keys
    assert "pareto_agents" in keys
    assert "critical_vs_non_critical" in keys
