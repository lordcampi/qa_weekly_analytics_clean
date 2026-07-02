from __future__ import annotations

"""Esquema estable para pestañas de histórico semanal (Sheets / Excel)."""

from dataclasses import dataclass

TAB_RESUMEN = "Hist_Resumen_Semanal"
TAB_POR_AGENTE = "Hist_Por_Agente"
TAB_POR_MOTIVO = "Hist_Por_Motivo"
TAB_WOW = "Hist_WoW"

HISTORIC_TABS: tuple[str, ...] = (TAB_RESUMEN, TAB_POR_AGENTE, TAB_POR_MOTIVO, TAB_WOW)


@dataclass(frozen=True, slots=True)
class HistoricTabSchema:
    """Contrato de columnas para una pestaña de histórico."""

    tab_name: str
    columns: tuple[str, ...]


RESUMEN_SCHEMA = HistoricTabSchema(
    tab_name=TAB_RESUMEN,
    columns=(
        "week_id",
        "start_date",
        "end_date",
        "published_at",
        "total_errors",
        "critical_count",
        "critical_pct",
        "recurring_agents_count",
        "corrected_agents_count",
        "persistent_agents_count",
        "new_alert_agents_count",
        "correction_rate",
    ),
)

POR_AGENTE_SCHEMA = HistoricTabSchema(
    tab_name=TAB_POR_AGENTE,
    columns=(
        "week_id",
        "start_date",
        "end_date",
        "agent",
        "errors",
        "critical_errors",
        "share",
        "rank",
    ),
)

POR_MOTIVO_SCHEMA = HistoricTabSchema(
    tab_name=TAB_POR_MOTIVO,
    columns=(
        "week_id",
        "start_date",
        "end_date",
        "reason",
        "count",
        "share",
        "rank",
    ),
)

WOW_SCHEMA = HistoricTabSchema(
    tab_name=TAB_WOW,
    columns=(
        "week_id",
        "start_date",
        "end_date",
        "agent",
        "wow_status",
        "previous_week_id",
    ),
)

SCHEMA_BY_TAB: dict[str, HistoricTabSchema] = {
    TAB_RESUMEN: RESUMEN_SCHEMA,
    TAB_POR_AGENTE: POR_AGENTE_SCHEMA,
    TAB_POR_MOTIVO: POR_MOTIVO_SCHEMA,
    TAB_WOW: WOW_SCHEMA,
}


def schema_columns_for_tab(tab_name: str) -> tuple[str, ...]:
    """Columnas del esquema; acepta nombres custom si coinciden con defaults."""
    if tab_name in SCHEMA_BY_TAB:
        return SCHEMA_BY_TAB[tab_name].columns
    for default_tab, schema in SCHEMA_BY_TAB.items():
        if tab_name.lower().replace(" ", "_") == default_tab.lower():
            return schema.columns
    return SCHEMA_BY_TAB[TAB_RESUMEN].columns
