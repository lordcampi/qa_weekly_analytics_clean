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
        table: DataFrame con columnas: key, count, share (0..1), cumulative_share (0..1).
    """

    table: pd.DataFrame


def rank_by_agent(df: pd.DataFrame, *, sort: Literal["desc", "asc"] = "desc") -> RankingResult:
    """Calcula ranking por agente con participación y acumulado.

    Args:
        df: DataFrame normalizado (requiere columna 'agent').
        sort: Orden del ranking.

    Returns:
        RankingResult con tabla.

    Raises:
        ValueError: Si falta la columna requerida.
    """
    if "agent" not in df.columns:
        raise ValueError("Falta columna requerida: agent")

    if df.empty:
        table = pd.DataFrame(columns=["agent", "count", "share", "cumulative_share"])
        return RankingResult(table=table)

    counts = df.groupby("agent", dropna=False).size().reset_index(name="count")
    counts["agent"] = counts["agent"].fillna("").astype(str)

    ascending = sort == "asc"
    counts = counts.sort_values(["count", "agent"], ascending=[ascending, True], kind="mergesort").reset_index(drop=True)

    total = float(counts["count"].sum()) if counts["count"].sum() else 0.0
    counts["share"] = counts["count"] / total if total else 0.0
    counts["cumulative_share"] = counts["share"].cumsum()

    logger.debug("Ranking por agente calculado", extra={"agents": int(counts.shape[0]), "total": int(total)})
    return RankingResult(table=counts)