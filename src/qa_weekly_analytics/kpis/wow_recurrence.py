from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd

from qa_weekly_analytics.domain.date_ranges import DateRange
from qa_weekly_analytics.kpis.recurrence import compute_recurrence

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class WoWRecurrenceResult:
    """Resultado del análisis de evolución de reincidencias Week-over-Week.

    Una reincidencia se define como un mismo agente cometiendo el mismo tipo de error
    (motivo) más de una vez en la semana.

    Attributes:
        corrected_agents: (🟢) Agentes que tenían reincidencias la semana pasada pero no esta.
        persistent_agents: (🔴) Agentes que tenían reincidencias en ambas semanas.
        new_alert_agents: (🟡) Agentes que no tenían reincidencias la semana pasada pero sí esta.
        correction_rate: Tasa de subsanación (0.0 a 1.0). Porcentaje de agentes con
                         reincidencias la semana pasada que fueron corregidos.
    """

    corrected_agents: list[str]
    persistent_agents: list[str]
    new_alert_agents: list[str]
    correction_rate: float


def _get_recurring_agents(df: pd.DataFrame, week_range: DateRange) -> set[str]:
    """Extrae el conjunto de agentes con reincidencias en un rango de fechas."""
    if df.empty:
        return set()

    week_df = df[(df["date"] >= week_range.start_date) & (df["date"] <= week_range.end_date)]
    if week_df.empty:
        return set()

    recurrence_report = compute_recurrence(week_df)
    recurring_pairs = recurrence_report.repeated_agent_reason

    if recurring_pairs.empty:
        return set()

    return set(recurring_pairs["agent"].unique())


def analyze_wow_recurrence(
    df: pd.DataFrame,
    *,
    current_week: DateRange,
    previous_week: DateRange,
) -> WoWRecurrenceResult:
    """
    Analiza la evolución de reincidencias de agentes entre la semana anterior y la actual.

    Args:
        df: DataFrame limpio y validado con todos los datos.
        current_week: Rango de fechas para la semana actual.
        previous_week: Rango de fechas para la semana anterior.

    Returns:
        Un objeto WoWRecurrenceResult con las listas de agentes clasificadas.
    """
    agents_last_week = _get_recurring_agents(df, previous_week)
    agents_this_week = _get_recurring_agents(df, current_week)

    # 🟢 Agentes Subsanados: Estaban en la lista anterior, pero no en la actual.
    corrected = sorted(list(agents_last_week - agents_this_week))

    # 🔴 Agentes Persistentes: Están en ambas listas (intersección).
    persistent = sorted(list(agents_last_week & agents_this_week))

    # 🟡 Nuevos en Alerta: Están en la lista actual, pero no en la anterior.
    new_alert = sorted(list(agents_this_week - agents_last_week))

    # Tasa de Subsanación: (Corregidos / Total que reincidían la semana pasada)
    total_to_correct = len(agents_last_week)
    correction_rate = len(corrected) / total_to_correct if total_to_correct > 0 else 0.0

    logger.info(
        "Análisis WoW de reincidencias completado",
        extra={
            "corrected": len(corrected),
            "persistent": len(persistent),
            "new_alert": len(new_alert),
            "correction_rate": correction_rate,
        },
    )

    return WoWRecurrenceResult(
        corrected_agents=corrected,
        persistent_agents=persistent,
        new_alert_agents=new_alert,
        correction_rate=correction_rate,
    )