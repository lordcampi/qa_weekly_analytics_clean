from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable, Optional

import pandas as pd

from qa_weekly_analytics.domain.date_ranges import DateRange, previous_week_monday_friday, week_label

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


def compute_default_range(tz_name: str, now: datetime | None = None) -> tuple[date, date]:
    """Devuelve el rango por defecto: semana anterior (L–V) en tz_name.

    Args:
        tz_name: Zona horaria IANA (ej. 'America/Bogota').
        now: Momento de referencia (opcional).

    Returns:
        (start_date, end_date) inclusive.
    """
    rng = previous_week_monday_friday(tz_name=tz_name, now=now)
    return rng.start_date, rng.end_date


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


def week_options_for_ui(weeks: list[DateRange]) -> dict[str, DateRange]:
    """Mapa etiqueta legible -> DateRange para multiselect."""
    return {week_label(w): w for w in weeks}


def resolve_selected_weeks(selected_labels: list[str], options: dict[str, DateRange]) -> list[DateRange]:
    """Resuelve semanas seleccionadas desde etiquetas UI."""
    return [options[label] for label in selected_labels if label in options]


def quincena_preset_labels(options: dict[str, DateRange], count: int = 2) -> list[str]:
    """Devuelve las N semanas más recientes (default quincena = 2)."""
    labels = list(options.keys())
    return labels[:count]
