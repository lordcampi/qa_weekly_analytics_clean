from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd

from qa_weekly_analytics.domain.date_ranges import DateRange, get_year_weeks

logger = logging.getLogger(__name__)


class DashboardLogicError(Exception):
    """Error en la lógica del dashboard (no-UI)."""


@dataclass(frozen=True, slots=True)
class FilterOptions:
    """Opciones disponibles para filtros.

    Attributes:
        agents: Lista ordenada y única de agentes.
        reasons: Lista ordenada y única de motivos.
    """

    agents: list[str]
    reasons: list[str]


def map_critical_choice(choice: str) -> bool | None:
    """Mapea el filtro UI de crítico a bool|None.

    Args:
        choice: Texto del selector.

    Returns:
        None para "Todos", True para "Sólo críticos", False para "Sólo no críticos".
    """
    c = (choice or "").strip().lower()
    if c in {"todos", "todas", "all"}:
        return None
    if c in {"sólo críticos", "solo críticos", "solo criticos", "críticos", "criticos"}:
        return True
    if c in {"sólo no críticos", "solo no críticos", "solo no criticos", "no críticos", "no criticos"}:
        return False
    return None


def get_filter_options(df: pd.DataFrame) -> FilterOptions:
    """Obtiene opciones de filtros (agentes y motivos) desde un df normalizado.

    Args:
        df: DataFrame con columnas 'agent' y 'reason'.

    Returns:
        FilterOptions con listas ordenadas.

    Raises:
        DashboardLogicError: Si faltan columnas requeridas.
    """
    for col in ("agent", "reason"):
        if col not in df.columns:
            raise DashboardLogicError(f"Falta columna requerida: {col}")

    agents = sorted({str(a).strip() for a in df["agent"].fillna("").tolist() if str(a).strip()})
    reasons = sorted({str(r).strip() for r in df["reason"].fillna("").tolist() if str(r).strip()})

    logger.debug("Opciones de filtros calculadas", extra={"agents": len(agents), "reasons": len(reasons)})
    return FilterOptions(agents=agents, reasons=reasons)


def resolve_selected_weeks(
    selected_labels: list[str],
    all_weeks: dict[str, DateRange],
) -> list[DateRange]:
    """Resuelve etiquetas de semana a DateRanges, en orden cronológico.

    Args:
        selected_labels: Lista de etiquetas ISO (ej: 'S27 — 30/06/2026 a 04/07/2026').
        all_weeks: Dict {label: DateRange} del año.

    Returns:
        Lista de DateRange en orden cronológico.
    """
    resolved = [all_weeks[label] for label in selected_labels if label in all_weeks]
    resolved.sort(key=lambda w: w.start_date)
    return resolved


def get_available_weeks(
    df: pd.DataFrame,
    year: int,
) -> dict[str, DateRange]:
    """Wrapper sobre get_year_weeks con manejo defensivo.

    Args:
        df: DataFrame normalizado.
        year: Año a consultar.

    Returns:
        Dict {label_iso: DateRange}.
    """
    return get_year_weeks(df, year, min_rows=1)