from __future__ import annotations

import logging
from typing import Iterable

import pandas as pd
from pandas.io.formats.style import Styler

logger = logging.getLogger(__name__)


class TableStyleError(Exception):
    """Error aplicando formato visual a tablas."""


def _existing_columns(df: pd.DataFrame, columns: Iterable[str]) -> list[str]:
    """Devuelve solo las columnas que existen en el DataFrame.

    Args:
        df: DataFrame objetivo.
        columns: Columnas candidatas.

    Returns:
        Lista de columnas existentes.
    """
    return [col for col in columns if col in df.columns]


def style_ranking_table(
    df: pd.DataFrame,
    *,
    count_col: str = "count",
    pct_cols: tuple[str, ...] = ("share", "cumulative_share"),
) -> Styler:
    """Aplica formato condicional a tablas de ranking.

    Args:
        df: DataFrame de ranking, por ejemplo by_agent o by_reason.
        count_col: Columna numérica principal para gradiente.
        pct_cols: Columnas proporción 0..1 a formatear como porcentaje.

    Returns:
        Styler con gradiente y formatos aplicados.

    Raises:
        TableStyleError: Si df no es un DataFrame válido.
    """
    if not isinstance(df, pd.DataFrame):
        raise TableStyleError("df debe ser un pandas.DataFrame")

    if df.empty:
        return df.style

    styled = df.style

    if count_col in df.columns:
        styled = styled.background_gradient(subset=[count_col])

    existing_pct_cols = _existing_columns(df, pct_cols)
    if existing_pct_cols:
        styled = styled.format({col: "{:.1%}" for col in existing_pct_cols})

    logger.debug(
        "Estilo aplicado a tabla ranking",
        extra={"rows": int(df.shape[0]), "columns": list(df.columns)},
    )

    return styled


def style_critical_table(df: pd.DataFrame) -> Styler:
    """Aplica formato visual a tabla de críticos.

    Resalta todas las filas para mejorar lectura rápida.

    Args:
        df: DataFrame de críticos.

    Returns:
        Styler con resaltado aplicado.

    Raises:
        TableStyleError: Si df no es un DataFrame válido.
    """
    if not isinstance(df, pd.DataFrame):
        raise TableStyleError("df debe ser un pandas.DataFrame")

    if df.empty:
        return df.style

    def highlight_row(_: pd.Series) -> list[str]:
        return [
            "background-color: #fff3cd; color: #3b2f00; font-weight: 500;"
            for _ in range(len(df.columns))
        ]

    styled = df.style.apply(highlight_row, axis=1)

    logger.debug(
        "Estilo aplicado a tabla de críticos",
        extra={"rows": int(df.shape[0]), "columns": list(df.columns)},
    )

    return styled


def style_recurrence_table(df: pd.DataFrame, *, count_col: str = "count") -> Styler:
    """Aplica formato visual a tablas de reincidencia.

    Args:
        df: DataFrame de reincidencias.
        count_col: Columna de conteo.

    Returns:
        Styler con gradiente si existe count_col.

    Raises:
        TableStyleError: Si df no es DataFrame.
    """
    if not isinstance(df, pd.DataFrame):
        raise TableStyleError("df debe ser un pandas.DataFrame")

    if df.empty:
        return df.style

    styled = df.style
    if count_col in df.columns:
        styled = styled.background_gradient(subset=[count_col])

    logger.debug(
        "Estilo aplicado a tabla reincidencia",
        extra={"rows": int(df.shape[0]), "columns": list(df.columns)},
    )

    return styled