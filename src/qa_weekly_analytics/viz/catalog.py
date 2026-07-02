from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ChartLocation(str, Enum):
    """Ubicación donde se renderiza un gráfico."""

    DASHBOARD = "dashboard"


class ChartKind(str, Enum):
    """Tipo lógico de gráfico."""

    KPI_CARDS = "kpi_cards"
    BAR = "bar"
    HORIZONTAL_BAR = "horizontal_bar"
    PARETO = "pareto"
    STACKED_BAR = "stacked_bar"


@dataclass(frozen=True, slots=True)
class ChartSpec:
    """Especificación declarativa de un gráfico.

    Args:
        key: Identificador lógico interno.
        title: Título visible.
        description: Descripción funcional.
        kind: Tipo lógico del gráfico.
        location: Ubicación donde se renderiza.
        input_name: Nombre lógico del dato de entrada desde KPIResult.
        width_px: Ancho objetivo para render estático.
        height_px: Alto objetivo para render estático.
        max_items: Límite de elementos visibles. None si no aplica.
        enabled: Indica si el gráfico está activo en el MVP visual.
    """

    key: str
    title: str
    description: str
    kind: ChartKind
    location: ChartLocation
    input_name: str
    width_px: int
    height_px: int
    max_items: int | None
    enabled: bool = True


DASHBOARD_CHARTS: tuple[ChartSpec, ...] = (
    ChartSpec(
        key="kpi_cards",
        title="Tarjetas KPI",
        description="Total de errores, errores críticos y porcentaje de críticos.",
        kind=ChartKind.KPI_CARDS,
        location=ChartLocation.DASHBOARD,
        input_name="summary_metrics",
        width_px=900,
        height_px=160,
        max_items=None,
    ),
    ChartSpec(
        key="trend_lv",
        title="Tendencia diaria L–V",
        description="Conteo diario de errores en el rango seleccionado.",
        kind=ChartKind.BAR,
        location=ChartLocation.DASHBOARD,
        input_name="trend_daily",
        width_px=760,
        height_px=360,
        max_items=5,
    ),
    ChartSpec(
        key="top_agents",
        title="Top agentes",
        description="Ranking de agentes con mayor número de errores.",
        kind=ChartKind.HORIZONTAL_BAR,
        location=ChartLocation.DASHBOARD,
        input_name="by_agent",
        width_px=760,
        height_px=420,
        max_items=10,
    ),
    ChartSpec(
        key="top_reasons",
        title="Top motivos",
        description="Ranking de motivos con mayor número de errores.",
        kind=ChartKind.HORIZONTAL_BAR,
        location=ChartLocation.DASHBOARD,
        input_name="by_reason",
        width_px=760,
        height_px=420,
        max_items=10,
    ),
    ChartSpec(
        key="pareto_agents",
        title="Pareto 80/20 — Agentes",
        description="Barras por agente con línea de participación acumulada.",
        kind=ChartKind.PARETO,
        location=ChartLocation.DASHBOARD,
        input_name="by_agent",
        width_px=900,
        height_px=460,
        max_items=10,
    ),
    ChartSpec(
        key="critical_vs_non_critical",
        title="Críticos vs no críticos",
        description="Distribución diaria entre errores críticos y no críticos.",
        kind=ChartKind.STACKED_BAR,
        location=ChartLocation.DASHBOARD,
        input_name="clean_rows",
        width_px=900,
        height_px=420,
        max_items=5,
    ),
)


def get_dashboard_charts() -> tuple[ChartSpec, ...]:
    """Devuelve el catálogo de gráficos del dashboard.

    Returns:
        Tupla de ChartSpec habilitados para dashboard.
    """
    charts = tuple(chart for chart in DASHBOARD_CHARTS if chart.enabled)
    logger.debug("Catálogo dashboard cargado", extra={"count": len(charts)})
    return charts
