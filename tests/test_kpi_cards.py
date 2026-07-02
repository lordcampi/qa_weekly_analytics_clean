from __future__ import annotations

from dataclasses import dataclass

import pytest

from qa_weekly_analytics.app.kpi_cards import KpiCardsError, build_kpi_cards


@dataclass(frozen=True)
class _DummyKpis:
    total_errors: int
    critical_count: int
    critical_pct: float


def test_build_kpi_cards_formats_values() -> None:
    kpis = _DummyKpis(total_errors=25, critical_count=5, critical_pct=0.2)

    cards = build_kpi_cards(kpis)

    assert len(cards) == 3
    assert cards[0].label == "Total de errores"
    assert cards[0].value == "25"
    assert cards[1].label == "Errores críticos"
    assert cards[1].value == "5"
    assert cards[2].label == "% críticos"
    assert cards[2].value == "20.0%"


def test_build_kpi_cards_requires_attributes() -> None:
    with pytest.raises(KpiCardsError):
        build_kpi_cards(object())