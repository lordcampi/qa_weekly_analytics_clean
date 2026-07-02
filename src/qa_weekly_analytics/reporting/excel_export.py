from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from qa_weekly_analytics.storage.historic_schema import (
    HISTORIC_TABS,
    SCHEMA_BY_TAB,
    TAB_POR_AGENTE,
    TAB_POR_MOTIVO,
    TAB_RESUMEN,
    TAB_WOW,
)
from qa_weekly_analytics.storage.weekly_snapshot import WeeklySnapshot

logger = logging.getLogger(__name__)


class ExcelExportError(Exception):
    """Error exportando histórico a Excel."""


def _ensure_headers(path: Path, tab: str, df_new: pd.DataFrame) -> pd.DataFrame:
    """Carga histórico existente o crea DataFrame vacío con headers."""
    schema = SCHEMA_BY_TAB[tab]
    if not path.exists():
        return pd.DataFrame(columns=list(schema.columns))

    try:
        existing = pd.read_excel(path, sheet_name=tab, engine="openpyxl")
    except ValueError:
        return pd.DataFrame(columns=list(schema.columns))

    if existing.empty:
        return pd.DataFrame(columns=list(schema.columns))
    return existing


def append_snapshot_to_excel(
    snapshot: WeeklySnapshot,
    excel_path: Path,
    *,
    skip_if_exists: bool = True,
) -> Path:
    """Append snapshot a Registro_QA_Historico.xlsx (idempotente por week_id)."""
    excel_path = Path(excel_path)
    excel_path.parent.mkdir(parents=True, exist_ok=True)

    frames: dict[str, pd.DataFrame] = {
        TAB_RESUMEN: snapshot.resumen,
        TAB_POR_AGENTE: snapshot.por_agente,
        TAB_POR_MOTIVO: snapshot.por_motivo,
        TAB_WOW: snapshot.wow,
    }

    if excel_path.exists() and skip_if_exists:
        resumen_existing = _ensure_headers(excel_path, TAB_RESUMEN, snapshot.resumen)
        if not resumen_existing.empty and "week_id" in resumen_existing.columns:
            if snapshot.week_id in resumen_existing["week_id"].astype(str).tolist():
                raise ExcelExportError(f"La semana {snapshot.week_id} ya existe en {excel_path}")

    combined: dict[str, pd.DataFrame] = {}
    for tab in HISTORIC_TABS:
        existing = _ensure_headers(excel_path, tab, frames[tab]) if excel_path.exists() else pd.DataFrame(columns=list(SCHEMA_BY_TAB[tab].columns))
        new_rows = frames[tab]
        if existing.empty:
            combined[tab] = new_rows
        elif new_rows.empty:
            combined[tab] = existing
        else:
            combined[tab] = pd.concat([existing, new_rows], ignore_index=True)

    try:
        with pd.ExcelWriter(excel_path, engine="openpyxl", mode="w") as writer:
            for tab in HISTORIC_TABS:
                combined[tab].to_excel(writer, sheet_name=tab, index=False)
    except Exception as exc:
        raise ExcelExportError(f"No se pudo escribir {excel_path}: {exc}") from exc

    logger.info("Snapshot append en Excel", extra={"path": str(excel_path), "week_id": snapshot.week_id})
    return excel_path


def export_snapshot_workbook(snapshot: WeeklySnapshot, output_path: Path) -> Path:
    """Exporta un snapshot a un archivo Excel nuevo (una sola semana)."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with pd.ExcelWriter(output_path, engine="openpyxl", mode="w") as writer:
            snapshot.resumen.to_excel(writer, sheet_name=TAB_RESUMEN, index=False)
            snapshot.por_agente.to_excel(writer, sheet_name=TAB_POR_AGENTE, index=False)
            snapshot.por_motivo.to_excel(writer, sheet_name=TAB_POR_MOTIVO, index=False)
            snapshot.wow.to_excel(writer, sheet_name=TAB_WOW, index=False)
    except Exception as exc:
        raise ExcelExportError(f"No se pudo exportar snapshot: {exc}") from exc
    return output_path
