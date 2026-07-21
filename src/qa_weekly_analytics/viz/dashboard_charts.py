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
    """Construye una figura vacía con mensaje."""
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


# ---------------------------------------------------------------------------
# Gráficos existentes (conservados)
# ---------------------------------------------------------------------------

def trend_lv_bar(kpis: Any) -> go.Figure:
    """Construye gráfico de tendencia diaria L-V."""
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
    """Construye gráfico horizontal de Top agentes."""
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
    """Construye gráfico horizontal de Top motivos."""
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
    """Construye gráfico Pareto de agentes."""
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
    """Construye gráfico stacked de críticos vs no críticos por día."""
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


# ---------------------------------------------------------------------------
# NUEVOS gráficos para dashboard por semanas
# ---------------------------------------------------------------------------

def weekly_trend_bar(
    weekly_kpis: list[tuple[str, int, int]],
    *,
    title: str = "Tendencia Semanal",
) -> go.Figure:
    """Gráfico de barras stacked con una barra por semana.

    Args:
        weekly_kpis: Lista de (label, total_errors, critical_count) por semana.
        title: Título del gráfico.

    Returns:
        Figura Plotly stacked bar.
    """
    if not weekly_kpis:
        return _empty_figure(title)

    labels = [w[0] for w in weekly_kpis]
    totals = [w[1] for w in weekly_kpis]
    criticals = [w[2] for w in weekly_kpis]
    non_critical = [t - c for t, c in zip(totals, criticals)]

    fig = go.Figure()
    fig.add_bar(name="No críticos", x=labels, y=non_critical, marker_color="#3498db")
    fig.add_bar(name="Críticos", x=labels, y=criticals, marker_color="#e74c3c")

    fig.update_layout(
        title=title,
        barmode="stack",
        xaxis_title="Semana",
        yaxis_title="Errores",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02},
    )
    return fig


def comparison_side_by_side(
    week_a_label: str,
    week_b_label: str,
    kpis_a: Any,
    kpis_b: Any,
    *,
    top_n: int = 10,
) -> go.Figure:
    """Barras horizontales lado a lado comparando errores por agente entre dos semanas."""
    agents_a_df = kpis_a.by_agent if hasattr(kpis_a, "by_agent") and not kpis_a.by_agent.empty else pd.DataFrame(columns=["agent", "count"])
    agents_b_df = kpis_b.by_agent if hasattr(kpis_b, "by_agent") and not kpis_b.by_agent.empty else pd.DataFrame(columns=["agent", "count"])

    all_agents: set[str] = set()
    counts_a: dict[str, int] = {}
    counts_b: dict[str, int] = {}

    if not agents_a_df.empty:
        for _, row in agents_a_df.iterrows():
            a = str(row["agent"])
            all_agents.add(a)
            counts_a[a] = int(row["count"])
    if not agents_b_df.empty:
        for _, row in agents_b_df.iterrows():
            a = str(row["agent"])
            all_agents.add(a)
            counts_b[a] = int(row["count"])

    if not all_agents:
        return _empty_figure("Comparación por agente")

    agent_list = sorted(all_agents, key=lambda a: counts_a.get(a, 0) + counts_b.get(a, 0), reverse=True)[:top_n]

    vals_a = [counts_a.get(a, 0) for a in agent_list]
    vals_b = [counts_b.get(a, 0) for a in agent_list]

    fig = go.Figure()
    fig.add_bar(name=week_a_label, y=agent_list, x=vals_a, orientation="h", marker_color="#7fb3d8")
    fig.add_bar(name=week_b_label, y=agent_list, x=vals_b, orientation="h", marker_color="#2c3e50")

    fig.update_layout(
        title=f"Comparación: {week_a_label} vs {week_b_label}",
        barmode="group",
        xaxis_title="Errores",
        yaxis_title="Agente",
        legend={"orientation": "h"},
    )
    return fig


def agent_trend_line(
    weekly_data: list[tuple[str, int]],
    agent_name: str,
) -> go.Figure:
    """Línea de tendencia de errores de un agente a lo largo de semanas."""
    if not weekly_data:
        return _empty_figure(f"Tendencia — {agent_name}")

    labels = [w[0] for w in weekly_data]
    counts = [w[1] for w in weekly_data]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=labels,
            y=counts,
            mode="lines+markers",
            name=agent_name,
            line={"width": 2},
            marker={"size": 8},
        )
    )
    fig.update_layout(
        title=f"Tendencia semanal — {agent_name}",
        xaxis_title="Semana",
        yaxis_title="Errores",
    )
    return fig


def agents_errors_heatmap(
    week_labels: list[str],
    series: dict[str, list[int]],
    *,
    title: str = "Errores por agente (semanal)",
) -> go.Figure:
    """Heatmap agente × semana con conteo de errores absolutos."""
    if not week_labels or not series:
        return _empty_figure(title)

    agents = list(series.keys())
    z = [series[agent] for agent in agents]
    text = [[str(v) for v in row] for row in z]

    fig = go.Figure(
        data=[
            go.Heatmap(
                x=week_labels,
                y=agents,
                z=z,
                text=text,
                texttemplate="%{text}",
                textfont={"size": 12},
                colorscale="YlOrRd",
                colorbar={"title": "Errores"},
                hovertemplate="Agente: %{y}<br>Semana: %{x}<br>Errores: %{z}<extra></extra>",
            )
        ]
    )
    fig.update_layout(
        title=title,
        xaxis_title="Semana",
        yaxis_title="Agente",
        yaxis={"autorange": "reversed"},
    )
    return fig