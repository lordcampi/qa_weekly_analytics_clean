from __future__ import annotations

from datetime import date

import pandas as pd

from qa_weekly_analytics.kpis.weekly_summary import compute_kpis


def _sample_df() -> pd.DataFrame:
    # 7 registros repartidos en una semana laboral
    return pd.DataFrame(
        {
            "row_number": [2, 3, 4, 5, 6, 7, 8],
            "date": [
                date(2026, 6, 1),  # L
                date(2026, 6, 1),  # L
                date(2026, 6, 2),  # M
                date(2026, 6, 3),  # X
                date(2026, 6, 4),  # J
                date(2026, 6, 5),  # V
                date(2026, 6, 5),  # V
            ],
            "agent": ["Ana", "Ana", "Juan", "Ana", "Juan", "Pedro", "Pedro"],
            "ticket_id": ["T1", "T1", "T2", "T3", "T2", "T4", ""],  # T1 repetido, T2 repetido, uno vacío
            "reason": ["Pago", "Pago", "Login", "Pago", "Login", "Search", "Search"],
            "is_critical": [True, False, True, None, False, True, False],
            "notes": ["a", "b", "c", "d", "e", "f", "g"],
        }
    )


def test_compute_kpis_basic_counts_and_critical() -> None:
    df = _sample_df()
    res = compute_kpis(df, start_date=date(2026, 6, 1), end_date=date(2026, 6, 5))

    assert res.total_errors == 7
    assert res.critical_count == 3  # True en filas 0,2,5
    assert abs(res.critical_pct - (3 / 7)) < 1e-9

    # Top agente: Ana tiene 3, Juan 2, Pedro 2
    assert res.by_agent.iloc[0]["agent"] == "Ana"
    assert int(res.by_agent.iloc[0]["count"]) == 3

    # Top motivo: Pago 3, Login 2, Search 2
    assert res.by_reason.iloc[0]["reason"] == "Pago"
    assert int(res.by_reason.iloc[0]["count"]) == 3

    # Tendencia diaria
    daily = {row["date"]: int(row["count"]) for _, row in res.trend_daily.iterrows()}
    assert daily[date(2026, 6, 1)] == 2
    assert daily[date(2026, 6, 2)] == 1
    assert daily[date(2026, 6, 5)] == 2

    # Críticos detalle
    assert int(res.critical_table.shape[0]) == 3
    assert set(res.critical_table.columns).issuperset({"date", "agent", "ticket_id", "reason"})


def test_compute_kpis_pareto_slices() -> None:
    df = _sample_df()
    res = compute_kpis(df, start_date=date(2026, 6, 1), end_date=date(2026, 6, 5))

    # Pareto agentes: Ana (3/7=0.428), luego Juan o Pedro (2/7=0.285) -> acumulado 0.714
    # Incluye el siguiente para "cubrir" 0.8 -> debe incluir 3 filas en total.
    assert int(res.pareto_agents.items.shape[0]) == 3

    # Pareto motivos: Pago (3/7=0.428) + Login (2/7=0.285) -> 0.714, incluir siguiente -> 3 filas
    assert int(res.pareto_reasons.items.shape[0]) == 3


def test_compute_kpis_recurrence() -> None:
    df = _sample_df()
    res = compute_kpis(df, start_date=date(2026, 6, 1), end_date=date(2026, 6, 5))

    rep_tickets = res.recurrence["repeated_tickets"]
    assert set(rep_tickets["ticket_id"].tolist()) == {"T1", "T2"}
    assert res.recurrence["repeated_ticket_count"] == 2

    rep_pairs = res.recurrence["repeated_agent_reason"]
    # (Ana, Pago) aparece 3 veces; (Juan, Login) aparece 2 veces; (Pedro, Search) aparece 2 veces
    pairs = {(r["agent"], r["reason"]) for _, r in rep_pairs.iterrows()}
    assert ("Ana", "Pago") in pairs
    assert ("Juan", "Login") in pairs
    assert ("Pedro", "Search") in pairs
    assert res.recurrence["repeated_agent_reason_count"] == 3


def test_compute_kpis_with_filters() -> None:
    df = _sample_df()
    res = compute_kpis(
        df,
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 5),
        agents=["Ana"],
        reasons=["Pago"],
        critical=None,
    )

    assert res.total_errors == 3  # Ana+Pago: filas 0,1,3
    assert res.critical_count == 1  # solo fila 0 es True