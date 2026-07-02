from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

import pandas as pd

from qa_weekly_analytics.domain.date_ranges import DateRange, week_id_from_range
from qa_weekly_analytics.kpis.weekly_summary import KPIResult
from qa_weekly_analytics.kpis.wow_recurrence import WoWRecurrenceResult
from qa_weekly_analytics.storage.historic_schema import (
    POR_AGENTE_SCHEMA,
    POR_MOTIVO_SCHEMA,
    RESUMEN_SCHEMA,
    WOW_SCHEMA,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class WeeklySnapshot:
    """Snapshot semanal listo para persistir en Sheets o Excel."""

    week_range: DateRange
    resumen: pd.DataFrame
    por_agente: pd.DataFrame
    por_motivo: pd.DataFrame
    wow: pd.DataFrame

    @property
    def week_id(self) -> str:
        return week_id_from_range(self.week_range.start_date, self.week_range.end_date)


def build_weekly_snapshot(
    *,
    week_range: DateRange,
    kpis: KPIResult,
    wow: WoWRecurrenceResult,
    previous_week_id: str | None = None,
    published_at: datetime | None = None,
) -> WeeklySnapshot:
    """Serializa KPIResult y WoWRecurrenceResult al esquema de histórico."""
    ts = published_at or datetime.now(timezone.utc)
    week_id = week_id_from_range(week_range.start_date, week_range.end_date)
    start_s = week_range.start_date.isoformat()
    end_s = week_range.end_date.isoformat()
    published_s = ts.astimezone(timezone.utc).replace(microsecond=0).isoformat()

    recurring_count = int(kpis.recurrence.get("repeated_agent_reason_count", 0) or 0)

    resumen = pd.DataFrame(
        [
            {
                "week_id": week_id,
                "start_date": start_s,
                "end_date": end_s,
                "published_at": published_s,
                "total_errors": kpis.total_errors,
                "critical_count": kpis.critical_count,
                "critical_pct": round(kpis.critical_pct, 4),
                "recurring_agents_count": recurring_count,
                "corrected_agents_count": len(wow.corrected_agents),
                "persistent_agents_count": len(wow.persistent_agents),
                "new_alert_agents_count": len(wow.new_alert_agents),
                "correction_rate": round(wow.correction_rate, 4),
            }
        ],
        columns=list(RESUMEN_SCHEMA.columns),
    )

    por_agente_rows: list[dict] = []
    for rank, (_, row) in enumerate(kpis.by_agent.iterrows(), start=1):
        agent = str(row["agent"])
        por_agente_rows.append(
            {
                "week_id": week_id,
                "start_date": start_s,
                "end_date": end_s,
                "agent": agent,
                "errors": int(row["count"]),
                "critical_errors": 0,  # filled below if critical_table available
                "share": round(float(row["share"]), 4),
                "rank": rank,
            }
        )

    # Enrich critical_errors from critical_table
    if not kpis.critical_table.empty and "agent" in kpis.critical_table.columns:
        crit_by_agent = kpis.critical_table.groupby("agent").size().to_dict()
        for r in por_agente_rows:
            r["critical_errors"] = int(crit_by_agent.get(r["agent"], 0))

    por_agente = pd.DataFrame(por_agente_rows, columns=list(POR_AGENTE_SCHEMA.columns))

    por_motivo_rows: list[dict] = []
    for rank, (_, row) in enumerate(kpis.by_reason.iterrows(), start=1):
        por_motivo_rows.append(
            {
                "week_id": week_id,
                "start_date": start_s,
                "end_date": end_s,
                "reason": str(row["reason"]),
                "count": int(row["count"]),
                "share": round(float(row["share"]), 4),
                "rank": rank,
            }
        )
    por_motivo = pd.DataFrame(por_motivo_rows, columns=list(POR_MOTIVO_SCHEMA.columns))

    wow_rows: list[dict] = []
    for agent in wow.corrected_agents:
        wow_rows.append(
            {
                "week_id": week_id,
                "start_date": start_s,
                "end_date": end_s,
                "agent": agent,
                "wow_status": "subsanado",
                "previous_week_id": previous_week_id or "",
            }
        )
    for agent in wow.persistent_agents:
        wow_rows.append(
            {
                "week_id": week_id,
                "start_date": start_s,
                "end_date": end_s,
                "agent": agent,
                "wow_status": "persistente",
                "previous_week_id": previous_week_id or "",
            }
        )
    for agent in wow.new_alert_agents:
        wow_rows.append(
            {
                "week_id": week_id,
                "start_date": start_s,
                "end_date": end_s,
                "agent": agent,
                "wow_status": "nuevo_alerta",
                "previous_week_id": previous_week_id or "",
            }
        )
    wow_df = pd.DataFrame(wow_rows, columns=list(WOW_SCHEMA.columns))

    logger.info("Snapshot semanal construido", extra={"week_id": week_id, "total_errors": kpis.total_errors})
    return WeeklySnapshot(
        week_range=week_range,
        resumen=resumen,
        por_agente=por_agente,
        por_motivo=por_motivo,
        wow=wow_df,
    )
