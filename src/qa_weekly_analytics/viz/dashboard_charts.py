from __future__ import annotations

import logging
from datetime import date
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

logger = logging.getLogger(__name__)


class DashboardChartError(Exception):
    """Error construyendo gráficos Plotly para el dashboard."""


def _empty_figure(title: str, message: str = "Sin datos para mostrar") -> go.Figure:
    """Construye una figura vacía con mensaje.

    Args:
        title: Título del gráfico.
        message: Mensaje visible.

    Returns:
        Figura Plotly vacía.
    """
    fig = go.Figure()
    fig.update_layout(
        title=title,
        xaxis={"visible": False},
        yaxis={"visible": False},
        annotations=[
            {
                "text": message,
                "xref": "paper",
                "yref": "paper",
                "showarrow": False,
                "font": {"size": 14},
            }
        ],
    )
    return fig


def trend_lv_bar(kpis: Any) -> go.Figure:
    """Construye gráfico de tendencia diaria L-V.

    Args:
        kpis: KPIResult con atributo trend_daily.

    Returns:
        Figura Plotly de barras.

    Raises:
        DashboardChartError: Si falta información requerida.
    """
    if not hasattr(kpis, "trend_daily"):
        raise DashboardChartError("KPIResult no contiene trend_daily")

    df = kpis.trend_daily
    if df is None or df.empty:
        return _empty_figure("Tendencia diaria L-V")

    fig = px.bar(
        df,
        x="date",
        y="count",
        text="count",
        title="Tendencia diaria L-V",
        labels={"date": "Fecha", "count": "Errores"},
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(yaxis_title="Errores", xaxis_title="Fecha")
    return fig


def top_agents_bar(kpis: Any, *, top_n: int = 10) -> go.Figure:
    """Construye gráfico horizontal de Top agentes.

    Args:
        kpis: KPIResult con atributo by_agent.
        top_n: Máximo de agentes a mostrar.

    Returns:
        Figura Plotly.

    Raises:
        DashboardChartError: Si falta información requerida.
    """
    if not hasattr(kpis, "by_agent"):
        raise DashboardChartError("KPIResult no contiene by_agent")

    df = kpis.by_agent
    if df is None or df.empty:
        return _empty_figure("Top agentes")

    data = df.head(top_n).copy().sort_values("count", ascending=True)

    fig = px.bar(
        data,
        x="count",
        y="agent",
        orientation="h",
        text="count",
        title=f"Top {min(top_n, len(df))} agentes",
        labels={"count": "Errores", "agent": "Agente"},
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(xaxis_title="Errores", yaxis_title="Agente")
    return fig


def top_reasons_bar(kpis: Any, *, top_n: int = 10) -> go.Figure:
    """Construye gráfico horizontal de Top motivos.

    Args:
        kpis: KPIResult con atributo by_reason.
        top_n: Máximo de motivos a mostrar.

    Returns:
        Figura Plotly.

    Raises:
        DashboardChartError: Si falta información requerida.
    """
    if not hasattr(kpis, "by_reason"):
        raise DashboardChartError("KPIResult no contiene by_reason")

    df = kpis.by_reason
    if df is None or df.empty:
        return _empty_figure("Top motivos")

    data = df.head(top_n).copy().sort_values("count", ascending=True)

    fig = px.bar(
        data,
        x="count",
        y="reason",
        orientation="h",
        text="count",
        title=f"Top {min(top_n, len(df))} motivos",
        labels={"count": "Errores", "reason": "Motivo"},
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(xaxis_title="Errores", yaxis_title="Motivo")
    return fig


def pareto_agents_chart(kpis: Any, *, top_n: int = 10) -> go.Figure:
    """Construye gráfico Pareto de agentes.

    Args:
        kpis: KPIResult con atributo by_agent.
        top_n: Máximo de agentes a mostrar.

    Returns:
        Figura Plotly con barras y línea acumulada.

    Raises:
        DashboardChartError: Si falta información requerida.
    """
    if not hasattr(kpis, "by_agent"):
        raise DashboardChartError("KPIResult no contiene by_agent")

    df = kpis.by_agent
    if df is None or df.empty:
        return _empty_figure("Pareto 80/20 — Agentes")

    required = {"agent", "count", "cumulative_share"}
    missing = required - set(df.columns)
    if missing:
        raise DashboardChartError(f"Faltan columnas para Pareto agentes: {sorted(missing)}")

    data = df.head(top_n).copy()
    data["cumulative_pct"] = data["cumulative_share"].astype(float) * 100

    fig = go.Figure()

    fig.add_bar(
        x=data["agent"],
        y=data["count"],
        name="Errores",
        text=data["count"],
        textposition="outside",
    )
    fig.add_trace(
        go.Scatter(
            x=data["agent"],
            y=data["cumulative_pct"],
            name="% acumulado",
            mode="lines+markers",
            yaxis="y2",
        )
    )

    fig.add_hline(
        y=80,
        line_dash="dash",
        line_width=1,
        annotation_text="80%",
        annotation_position="top right",
        yref="y2",
    )

    fig.update_layout(
        title="Pareto 80/20 — Agentes",
        xaxis_title="Agente",
        yaxis_title="Errores",
        yaxis2={
            "title": "% acumulado",
            "overlaying": "y",
            "side": "right",
            "range": [0, 105],
        },
        legend={"orientation": "h"},
    )

    return fig


def critical_vs_non_critical_stacked(
    df: pd.DataFrame,
    *,
    start_date: date,
    end_date: date,
    agents: list[str] | None = None,
    reasons: list[str] | None = None,
) -> go.Figure:
    """Construye gráfico stacked de críticos vs no críticos por día.

    Este gráfico usa el DataFrame limpio QA-005, no KPIResult, para poder
    recalcular distribución diaria sin depender de tablas derivadas.

    Args:
        df: DataFrame normalizado con columnas date, agent, reason, is_critical.
        start_date: Fecha inicio inclusiva.
        end_date: Fecha fin inclusiva.
        agents: Filtro opcional de agentes.
        reasons: Filtro opcional de motivos.

    Returns:
        Figura Plotly stacked.

    Raises:
        DashboardChartError: Si faltan columnas requeridas.
    """
    required = {"date", "agent", "reason", "is_critical"}
    missing = required - set(df.columns)
    if missing:
        raise DashboardChartError(f"Faltan columnas para críticos vs no críticos: {sorted(missing)}")

    filtered = df[(df["date"] >= start_date) & (df["date"] <= end_date)].copy()

    if agents:
        filtered = filtered[filtered["agent"].isin(agents)]

    if reasons:
        filtered = filtered[filtered["reason"].isin(reasons)]

    if filtered.empty:
        return _empty_figure("Críticos vs no críticos")

    filtered["critical_label"] = filtered["is_critical"].map(
        lambda value: "Crítico" if value is True else "No crítico"
    )

    grouped = (
        filtered.groupby(["date", "critical_label"])
        .size()
        .reset_index(name="count")
        .sort_values("date")
    )

    fig = px.bar(
        grouped,
        x="date",
        y="count",
        color="critical_label",
        title="Críticos vs no críticos por día",
        labels={"date": "Fecha", "count": "Errores", "critical_label": "Tipo"},
    )
    fig.update_layout(barmode="stack", yaxis_title="Errores", xaxis_title="Fecha")
    return fig