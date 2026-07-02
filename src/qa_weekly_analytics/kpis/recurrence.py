from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RecurrenceResult:
    """Resultado de reincidencias.

    Attributes:
        repeated_tickets: DataFrame con columnas: ticket_id, count.
        repeated_agent_reason: DataFrame con columnas: agent, reason, count.
        repeated_ticket_count: Número de tickets con count > 1.
        repeated_agent_reason_count: Número de pares (agent, reason) con count > 1.
    """

    repeated_tickets: pd.DataFrame
    repeated_agent_reason: pd.DataFrame
    repeated_ticket_count: int
    repeated_agent_reason_count: int


def compute_recurrence(df: pd.DataFrame) -> RecurrenceResult:
    """Calcula reincidencias por ticket y por patrón (agent, reason).

    Reglas:
      - ticket_id vacío ("" o solo espacios) se ignora para repetición de tickets.

    Args:
        df: DataFrame normalizado (requiere agent, reason, ticket_id).

    Returns:
        RecurrenceResult con tablas y conteos.

    Raises:
        ValueError: Si faltan columnas requeridas.
    """
    for col in ("agent", "reason", "ticket_id"):
        if col not in df.columns:
            raise ValueError(f"Falta columna requerida: {col}")

    if df.empty:
        empty_tickets = pd.DataFrame(columns=["ticket_id", "count"])
        empty_pairs = pd.DataFrame(columns=["agent", "reason", "count"])
        return RecurrenceResult(
            repeated_tickets=empty_tickets,
            repeated_agent_reason=empty_pairs,
            repeated_ticket_count=0,
            repeated_agent_reason_count=0,
        )

    tmp = df.copy()
    tmp["ticket_id"] = tmp["ticket_id"].fillna("").astype(str).str.strip()
    tmp["agent"] = tmp["agent"].fillna("").astype(str)
    tmp["reason"] = tmp["reason"].fillna("").astype(str)

    # Repetición por ticket_id (ignorar vacíos)
    t = tmp[tmp["ticket_id"] != ""]
    ticket_counts = t.groupby("ticket_id").size().reset_index(name="count")
    repeated_tickets = ticket_counts[ticket_counts["count"] > 1].sort_values(
        ["count", "ticket_id"], ascending=[False, True], kind="mergesort"
    ).reset_index(drop=True)

    # Repetición por patrón (agent, reason)
    pair_counts = tmp.groupby(["agent", "reason"]).size().reset_index(name="count")
    repeated_pairs = pair_counts[pair_counts["count"] > 1].sort_values(
        ["count", "agent", "reason"], ascending=[False, True, True], kind="mergesort"
    ).reset_index(drop=True)

    logger.debug(
        "Reincidencias calculadas",
        extra={
            "repeated_ticket_count": int(repeated_tickets.shape[0]),
            "repeated_agent_reason_count": int(repeated_pairs.shape[0]),
        },
    )

    return RecurrenceResult(
        repeated_tickets=repeated_tickets,
        repeated_agent_reason=repeated_pairs,
        repeated_ticket_count=int(repeated_tickets.shape[0]),
        repeated_agent_reason_count=int(repeated_pairs.shape[0]),
    )