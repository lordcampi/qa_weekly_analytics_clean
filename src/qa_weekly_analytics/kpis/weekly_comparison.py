from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date

import pandas as pd

from qa_weekly_analytics.domain.date_ranges import DateRange, iso_week_label
from qa_weekly_analytics.kpis.weekly_summary import KPIResult, compute_kpis

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class WeekComparisonResult:
    """Comparación de KPIs entre dos semanas.

    Attributes:
        week_a_label: Etiqueta ISO de la semana A.
        week_b_label: Etiqueta ISO de la semana B.
        kpis_a: KPIResult de la semana A.
        kpis_b: KPIResult de la semana B.
        delta_errors: Diferencia absoluta de errores (B - A).
        delta_pct: Diferencia porcentual (positivo = aumentó B vs A).
        delta_critical: Diferencia de críticos.
        agents_improved: Agentes con menos errores en B vs A.
        agents_declined: Agentes con más errores en B vs A.
        agents_new: Agentes sin errores en A pero con errores en B.
        agents_resolved: Agentes con errores en A pero sin errores en B.
    """

    week_a_label: str
    week_b_label: str
    kpis_a: KPIResult
    kpis_b: KPIResult
    delta_errors: int
    delta_pct: float
    delta_critical: int
    agents_improved: list[str] = field(default_factory=list)
    agents_declined: list[str] = field(default_factory=list)
    agents_new: list[str] = field(default_factory=list)
    agents_resolved: list[str] = field(default_factory=list)


def compare_weeks(
    df: pd.DataFrame,
    *,
    week_a: DateRange,
    week_b: DateRange,
    agents: list[str] | None = None,
    critical_only: bool = False,
) -> WeekComparisonResult:
    """Compara KPIs entre dos semanas.

    Args:
        df: DataFrame normalizado QA-005.
        week_a: Semana base (más antigua).
        week_b: Semana a comparar (más reciente).
        agents: Filtro opcional de agentes.
        critical_only: Si True, solo considera errores críticos.

    Returns:
        WeekComparisonResult con métricas comparativas.
    """
    critical_filter: bool | None = True if critical_only else None

    kpis_a = compute_kpis(
        df,
        start_date=week_a.start_date,
        end_date=week_a.end_date,
        agents=agents,
        critical=critical_filter,
    )
    kpis_b = compute_kpis(
        df,
        start_date=week_b.start_date,
        end_date=week_b.end_date,
        agents=agents,
        critical=critical_filter,
    )

    delta_errors = kpis_b.total_errors - kpis_a.total_errors
    delta_pct = (delta_errors / kpis_a.total_errors) if kpis_a.total_errors else (1.0 if kpis_b.total_errors else 0.0)
    delta_critical = kpis_b.critical_count - kpis_a.critical_count

    # Agentes por semana
    agents_a = set(kpis_a.by_agent["agent"].tolist()) if not kpis_a.by_agent.empty else set()
    agents_b = set(kpis_b.by_agent["agent"].tolist()) if not kpis_b.by_agent.empty else set()

    # Counts por agente
    counts_a: dict[str, int] = {}
    if not kpis_a.by_agent.empty:
        for _, row in kpis_a.by_agent.iterrows():
            counts_a[str(row["agent"])] = int(row["count"])

    counts_b: dict[str, int] = {}
    if not kpis_b.by_agent.empty:
        for _, row in kpis_b.by_agent.iterrows():
            counts_b[str(row["agent"])] = int(row["count"])

    all_agents = agents_a | agents_b

    improved: list[str] = []
    declined: list[str] = []
    new_agents: list[str] = []
    resolved: list[str] = []

    for agent in sorted(all_agents):
        ca = counts_a.get(agent, 0)
        cb = counts_b.get(agent, 0)
        if ca == 0 and cb > 0:
            new_agents.append(agent)
        elif ca > 0 and cb == 0:
            resolved.append(agent)
        elif cb < ca:
            improved.append(agent)
        elif cb > ca:
            declined.append(agent)

    logger.info(
        "Comparación semanal completada",
        extra={
            "week_a": iso_week_label(week_a),
            "week_b": iso_week_label(week_b),
            "delta": delta_errors,
            "improved": len(improved),
            "declined": len(declined),
        },
    )

    return WeekComparisonResult(
        week_a_label=iso_week_label(week_a),
        week_b_label=iso_week_label(week_b),
        kpis_a=kpis_a,
        kpis_b=kpis_b,
        delta_errors=delta_errors,
        delta_pct=delta_pct,
        delta_critical=delta_critical,
        agents_improved=improved,
        agents_declined=declined,
        agents_new=new_agents,
        agents_resolved=resolved,
    )