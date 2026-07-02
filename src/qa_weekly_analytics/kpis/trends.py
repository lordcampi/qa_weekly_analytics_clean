from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TrendResult:
    """Resultado de tendencia diaria.

    Attributes:
        daily: DataFrame con columnas: date, count.
    """

    daily: pd.DataFrame


def daily_trend(df: pd.DataFrame) -> TrendResult:
    """Calcula tendencia diaria (conteo por fecha).

    Args:
        df: DataFrame normalizado (requiere columna 'date' con datetime.date).

    Returns:
        TrendResult con tabla diaria ordenada por fecha.

    Raises:
        ValueError: Si falta la columna requerida.
    """
    if "date" not in df.columns:
        raise ValueError("Falta columna requerida: date")

    if df.empty:
        return TrendResult(daily=pd.DataFrame(columns=["date", "count"]))

    tmp = df.copy()
    tmp = tmp.dropna(subset=["date"])
    if tmp.empty:
        return TrendResult(daily=pd.DataFrame(columns=["date", "count"]))

    # Mantener como date (no datetime)
    tmp["date"] = tmp["date"].apply(lambda x: x if isinstance(x, date) else x)  # type: ignore[misc]

    daily = tmp.groupby("date").size().reset_index(name="count").sort_values("date").reset_index(drop=True)
    logger.debug("Tendencia diaria calculada", extra={"days": int(daily.shape[0])})
    return TrendResult(daily=daily)