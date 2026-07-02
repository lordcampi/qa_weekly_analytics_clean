from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RankingResult:
    """Resultado de ranking por dimensión.

    Attributes:
        table: DataFrame con columnas: reason, count, share (0..1), cumulative_share (0..1).
    """

    table: pd.DataFrame


def rank_by_reason(df: pd.DataFrame, *, sort: Literal["desc", "asc"] = "desc") -> RankingResult:
    """Calcula ranking por motivo con participación y acumulado.

    Args:
        df: DataFrame normalizado (requiere columna 'reason').
        sort: Orden del ranking ('desc' o 'asc').

    Returns:
        RankingResult con tabla.

    Raises:
        ValueError: Si falta la columna requerida.
    """
    if "reason" not in df.columns:
        raise ValueError("Falta columna requerida: reason")

    if df.empty:
        table = pd.DataFrame(columns=["reason", "count", "share", "cumulative_share"])
        return RankingResult(table=table)

    counts = df.groupby("reason", dropna=False).size().reset_index(name="count")
    counts["reason"] = counts["reason"].fillna("").astype(str)

    ascending = sort == "asc"
    counts = counts.sort_values(
        ["count", "reason"],
        ascending=[ascending, True],
        kind="mergesort",
    ).reset_index(drop=True)

    total = float(counts["count"].sum()) if counts["count"].sum() else 0.0
    counts["share"] = (counts["count"] / total) if total else 0.0
    counts["cumulative_share"] = counts["share"].cumsum()

    logger.debug("Ranking por motivo calculado", extra={"reasons": int(counts.shape[0]), "total": int(total)})
    return RankingResult(table=counts)