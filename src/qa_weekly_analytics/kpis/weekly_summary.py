from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable

import pandas as pd

from qa_weekly_analytics.kpis.by_agent import rank_by_agent
from qa_weekly_analytics.kpis.by_reason import rank_by_reason
from qa_weekly_analytics.kpis.recurrence import compute_recurrence
from qa_weekly_analytics.kpis.trends import daily_trend

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ParetoSlice:
    """Corte Pareto (80/20).

    Attributes:
        items: DataFrame con columnas de ranking y cumulative_share hasta cubrir threshold.
        threshold: Umbral (por defecto 0.8).
    """

    items: pd.DataFrame
    threshold: float = 0.8


@dataclass(frozen=True, slots=True)
class KPIResult:
    """Resultado completo del motor de KPIs para un rango.

    Attributes:
        start_date: Inicio (incluido).
        end_date: Fin (incluido).
        total_errors: Total de registros en rango y filtros.
        critical_count: Número de críticos.
        critical_pct: Porcentaje de críticos (0..1).
        by_agent: Ranking por agente.
        by_reason: Ranking por motivo.
        pareto_agents: Corte Pareto para agentes.
        pareto_reasons: Corte Pareto para motivos.
        trend_daily: Tendencia diaria.
        recurrence: Reincidencias (tickets y patrón agente+motivo).
        critical_table: Detalle de críticos.
        filtered_rows: Número de filas tras filtros/rango.
        filters: Dict con filtros aplicados (para trazabilidad).
    """

    start_date: date
    end_date: date
    total_errors: int
    critical_count: int
    critical_pct: float
    by_agent: pd.DataFrame
    by_reason: pd.DataFrame
    pareto_agents: ParetoSlice
    pareto_reasons: ParetoSlice
    trend_daily: pd.DataFrame
    recurrence: dict[str, Any]
    critical_table: pd.DataFrame
    filtered_rows: int
    filters: dict[str, Any]


def _apply_filters(
    df: pd.DataFrame,
    *,
    agents: list[str] | None = None,
    reasons: list[str] | None = None,
    critical: bool | None = None,
) -> pd.DataFrame:
    """Aplica filtros opcionales (agente, motivo, crítico)."""
    out = df

    if agents:
        agents_norm = [a.strip() for a in agents if a.strip()]
        if agents_norm:
            out = out[out["agent"].isin(agents_norm)]

    if reasons:
        reasons_norm = [r.strip() for r in reasons if r.strip()]
        if reasons_norm:
            out = out[out["reason"].isin(reasons_norm)]

    if critical is True:
        out = out[out["is_critical"] is True] if False else out[out["is_critical"] == True]  # noqa: E712
    elif critical is False:
        out = out[out["is_critical"] == False]  # noqa: E712

    return out


def _pareto(table: pd.DataFrame, key_col: str, *, threshold: float = 0.8) -> ParetoSlice:
    """Devuelve las filas del ranking hasta cubrir el umbral Pareto."""
    if table.empty:
        return ParetoSlice(items=table.copy(), threshold=threshold)

    if "cumulative_share" not in table.columns:
        raise ValueError("La tabla de ranking debe incluir cumulative_share")

    cut = table[table["cumulative_share"] <= threshold].copy()
    if cut.empty:
        # si el primer elemento ya supera threshold, incluirlo
        cut = table.head(1).copy()
    else:
        # incluir el primer elemento que cruza el umbral (para “cubrir” 80%)
        next_idx = int(cut.shape[0])
        if next_idx < int(table.shape[0]):
            cut = pd.concat([cut, table.iloc[[next_idx]]], ignore_index=True)

    return ParetoSlice(items=cut.reset_index(drop=True), threshold=threshold)


def compute_kpis(
    df: pd.DataFrame,
    *,
    start_date: date,
    end_date: date,
    agents: list[str] | None = None,
    reasons: list[str] | None = None,
    critical: bool | None = None,
) -> KPIResult:
    """Motor de KPIs base para un rango arbitrario.

    Requiere DataFrame normalizado (salida de QA-005):
      - date: datetime.date
      - agent: str
      - ticket_id: str
      - reason: str
      - is_critical: bool|None
      - notes: str

    Args:
        df: DataFrame normalizado.
        start_date: Fecha inicio (incluida).
        end_date: Fecha fin (incluida).
        agents: Filtro opcional por agentes.
        reasons: Filtro opcional por motivos.
        critical: Filtro opcional por criticidad.

    Returns:
        KPIResult con métricas y tablas.

    Raises:
        ValueError: Si faltan columnas requeridas o rango inválido.
    """
    if start_date > end_date:
        raise ValueError("start_date no puede ser mayor que end_date")

    required = {"date", "agent", "ticket_id", "reason", "is_critical", "notes"}
    missing = sorted(list(required - set(df.columns)))
    if missing:
        raise ValueError(f"Faltan columnas requeridas: {missing}")

    if df.empty:
        empty_rank_agent = pd.DataFrame(columns=["agent", "count", "share", "cumulative_share"])
        empty_rank_reason = pd.DataFrame(columns=["reason", "count", "share", "cumulative_share"])
        empty_trend = pd.DataFrame(columns=["date", "count"])
        empty_crit = pd.DataFrame(columns=["row_number", "date", "agent", "ticket_id", "reason", "notes"])
        return KPIResult(
            start_date=start_date,
            end_date=end_date,
            total_errors=0,
            critical_count=0,
            critical_pct=0.0,
            by_agent=empty_rank_agent,
            by_reason=empty_rank_reason,
            pareto_agents=ParetoSlice(items=empty_rank_agent),
            pareto_reasons=ParetoSlice(items=empty_rank_reason),
            trend_daily=empty_trend,
            recurrence={
                "repeated_tickets": pd.DataFrame(columns=["ticket_id", "count"]),
                "repeated_agent_reason": pd.DataFrame(columns=["agent", "reason", "count"]),
                "repeated_ticket_count": 0,
                "repeated_agent_reason_count": 0,
            },
            critical_table=empty_crit,
            filtered_rows=0,
            filters={"agents": agents, "reasons": reasons, "critical": critical},
        )

    # Filtrado por rango
    in_range = df[(df["date"] >= start_date) & (df["date"] <= end_date)].copy()

    # Filtros opcionales
    filtered = _apply_filters(in_range, agents=agents, reasons=reasons, critical=critical)

    total = int(filtered.shape[0])
    crit_count = int((filtered["is_critical"] == True).sum())  # noqa: E712
    crit_pct = float(crit_count / total) if total else 0.0

    by_agent_tbl = rank_by_agent(filtered).table
    by_reason_tbl = rank_by_reason(filtered).table

    pareto_agents = _pareto(by_agent_tbl, "agent", threshold=0.8)
    pareto_reasons = _pareto(by_reason_tbl, "reason", threshold=0.8)

    trend_tbl = daily_trend(filtered).daily

    rec = compute_recurrence(filtered)
    rec_dict: dict[str, Any] = {
        "repeated_tickets": rec.repeated_tickets,
        "repeated_agent_reason": rec.repeated_agent_reason,
        "repeated_ticket_count": rec.repeated_ticket_count,
        "repeated_agent_reason_count": rec.repeated_agent_reason_count,
    }

    crit_table_cols = ["row_number", "date", "agent", "ticket_id", "reason", "notes"]
    if "row_number" in filtered.columns:
        crit_detail = filtered[filtered["is_critical"] == True][crit_table_cols].copy()  # noqa: E712
    else:
        # Si el df no trae row_number, lo omitimos (pero QA-005 sí lo trae).
        crit_table_cols = ["date", "agent", "ticket_id", "reason", "notes"]
        crit_detail = filtered[filtered["is_critical"] == True][crit_table_cols].copy()  # noqa: E712

    crit_detail = crit_detail.sort_values(["date", "agent"], kind="mergesort").reset_index(drop=True)

    logger.info(
        "KPIs calculados",
        extra={
            "start_date": str(start_date),
            "end_date": str(end_date),
            "total": total,
            "critical_count": crit_count,
            "filters": {"agents": agents, "reasons": reasons, "critical": critical},
        },
    )

    return KPIResult(
        start_date=start_date,
        end_date=end_date,
        total_errors=total,
        critical_count=crit_count,
        critical_pct=crit_pct,
        by_agent=by_agent_tbl,
        by_reason=by_reason_tbl,
        pareto_agents=pareto_agents,
        pareto_reasons=pareto_reasons,
        trend_daily=trend_tbl,
        recurrence=rec_dict,
        critical_table=crit_detail,
        filtered_rows=total,
        filters={"agents": agents, "reasons": reasons, "critical": critical},
    )