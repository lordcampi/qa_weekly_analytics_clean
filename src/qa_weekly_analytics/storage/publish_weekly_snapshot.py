from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from qa_weekly_analytics.connectors.sheets_writer import SheetsWriteError, publish_snapshot_to_sheets
from qa_weekly_analytics.domain.date_ranges import DateRange, week_id_from_range
from qa_weekly_analytics.domain.period_comparison import comparison_ranges_for_period
from qa_weekly_analytics.kpis.weekly_summary import compute_kpis
from qa_weekly_analytics.kpis.wow_recurrence import analyze_wow_recurrence
from qa_weekly_analytics.reporting.excel_export import ExcelExportError, append_snapshot_to_excel
from qa_weekly_analytics.storage.settings import Settings
from qa_weekly_analytics.storage.weekly_snapshot import WeeklySnapshot, build_weekly_snapshot

logger = logging.getLogger(__name__)


class PublishSnapshotError(Exception):
    """Error publicando snapshot semanal."""


@dataclass(frozen=True, slots=True)
class PublishResult:
    """Resultado de publicación semanal."""

    week_id: str
    week_range: DateRange
    snapshot: WeeklySnapshot
    sheets_counts: dict[str, int] | None
    excel_path: Path | None
    skipped: bool = False


def _previous_week_id(week_range: DateRange) -> str | None:
    _, previous = comparison_ranges_for_period(week_range.start_date, week_range.end_date)
    return week_id_from_range(previous.start_date, previous.end_date)


def compute_snapshot_for_week(
    df: pd.DataFrame,
    week_range: DateRange,
) -> WeeklySnapshot:
    """Calcula snapshot para una semana L-V."""
    kpis = compute_kpis(df, start_date=week_range.start_date, end_date=week_range.end_date)
    current, previous = comparison_ranges_for_period(week_range.start_date, week_range.end_date)
    wow = analyze_wow_recurrence(df, current_week=current, previous_week=previous)
    prev_id = _previous_week_id(week_range)
    return build_weekly_snapshot(
        week_range=week_range,
        kpis=kpis,
        wow=wow,
        previous_week_id=prev_id,
    )


def publish_weekly_snapshot(
    df: pd.DataFrame,
    *,
    week_range: DateRange | None = None,
    settings: Settings,
    credentials=None,
    to_sheets: bool = True,
    to_excel: bool = True,
    skip_if_exists: bool = True,
    force: bool = False,
) -> PublishResult:
    """Publica snapshot semanal en Sheets y/o Excel (idempotente).

    Args:
        df: DataFrame normalizado completo.
        week_range: Semana a publicar. Si None, usa semana anterior L-V.
        settings: Configuración de la app.
        credentials: Credenciales Google (requeridas si to_sheets=True).
        to_sheets: Escribir en pestañas histórico de Google Sheets.
        to_excel: Append en archivo Excel local.
        skip_if_exists: No duplicar week_id.
        force: Republicar aunque exista (solo Excel; Sheets sigue bloqueando duplicados).
    """
    if week_range is None:
        from qa_weekly_analytics.domain.date_ranges import previous_week_monday_friday

        week_range = previous_week_monday_friday(tz_name=settings.TIMEZONE)

    snapshot = compute_snapshot_for_week(df, week_range)
    week_id = snapshot.week_id

    sheets_counts: dict[str, int] | None = None
    excel_path: Path | None = None

    if to_sheets:
        if credentials is None:
            raise PublishSnapshotError("Se requieren credenciales Google para publicar en Sheets")
        try:
            sheets_counts = publish_snapshot_to_sheets(
                credentials=credentials,
                sheet_id=settings.SHEET_ID,
                tab_resumen=settings.HIST_TAB_RESUMEN,
                tab_por_agente=settings.HIST_TAB_POR_AGENTE,
                tab_por_motivo=settings.HIST_TAB_POR_MOTIVO,
                tab_wow=settings.HIST_TAB_WOW,
                resumen=snapshot.resumen,
                por_agente=snapshot.por_agente,
                por_motivo=snapshot.por_motivo,
                wow=snapshot.wow,
                week_id=week_id,
                skip_if_exists=skip_if_exists and not force,
            )
        except SheetsWriteError as exc:
            msg = str(exc)
            if "insufficient authentication scopes" in msg.lower() or "scope" in msg.lower():
                msg = (
                    f"{msg}\n\nEl token de Google solo tiene permiso de lectura. "
                    "En el dashboard usá «Re-autorizar Google» o borrá .secrets/token.json y volvé a entrar."
                )
            if skip_if_exists and not force and "ya está publicada" in msg:
                return PublishResult(
                    week_id=week_id,
                    week_range=week_range,
                    snapshot=snapshot,
                    sheets_counts=None,
                    excel_path=None,
                    skipped=True,
                )
            raise PublishSnapshotError(msg) from exc

    if to_excel:
        path = settings.historic_excel_path_resolved()
        try:
            excel_path = append_snapshot_to_excel(
                snapshot,
                path,
                skip_if_exists=skip_if_exists and not force,
            )
        except ExcelExportError as exc:
            if skip_if_exists and not force and "ya existe" in str(exc):
                if sheets_counts is None:
                    return PublishResult(
                        week_id=week_id,
                        week_range=week_range,
                        snapshot=snapshot,
                        sheets_counts=sheets_counts,
                        excel_path=None,
                        skipped=True,
                    )
            else:
                raise PublishSnapshotError(str(exc)) from exc

    logger.info("Snapshot publicado", extra={"week_id": week_id, "sheets": bool(sheets_counts), "excel": str(excel_path)})
    return PublishResult(
        week_id=week_id,
        week_range=week_range,
        snapshot=snapshot,
        sheets_counts=sheets_counts,
        excel_path=excel_path,
        skipped=False,
    )
