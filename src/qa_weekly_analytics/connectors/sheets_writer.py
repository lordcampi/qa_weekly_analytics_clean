from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd
from google.auth.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from qa_weekly_analytics.connectors.sheets_reader import SheetsReadError, read_range
from qa_weekly_analytics.storage.historic_schema import SCHEMA_BY_TAB, schema_columns_for_tab

logger = logging.getLogger(__name__)


class SheetsWriteError(Exception):
    """Error al escribir datos en Google Sheets."""


def _dataframe_to_values(df: pd.DataFrame) -> list[list[Any]]:
    if df.empty:
        return []
    return df.astype(object).where(pd.notna(df), "").values.tolist()


def read_historic_tab(
    *,
    credentials: Credentials,
    sheet_id: str,
    tab_name: str,
) -> pd.DataFrame:
    """Lee una pestaña de histórico completa (header + filas)."""
    schema_cols = list(schema_columns_for_tab(tab_name))
    try:
        sheet_data = read_range(
            credentials=credentials,
            sheet_id=sheet_id,
            sheet_tab=tab_name,
            sheet_range="A1:Z100000",
        )
        return sheet_data.df
    except SheetsReadError:
        return pd.DataFrame(columns=schema_cols)


def week_id_exists_in_resumen(
    *,
    credentials: Credentials,
    sheet_id: str,
    tab_name: str,
    week_id: str,
) -> bool:
    """Verifica si week_id ya fue publicado (idempotencia)."""
    df = read_historic_tab(credentials=credentials, sheet_id=sheet_id, tab_name=tab_name)
    if df.empty or "week_id" not in df.columns:
        return False
    return week_id in df["week_id"].astype(str).tolist()


def ensure_tab_with_headers(
    *,
    credentials: Credentials,
    sheet_id: str,
    tab_name: str,
) -> None:
    """Crea la pestaña si no existe y escribe headers si está vacía."""
    service = build("sheets", "v4", credentials=credentials, cache_discovery=False)
    spreadsheet = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
    sheets = spreadsheet.get("sheets", [])
    titles = {s["properties"]["title"] for s in sheets}

    if tab_name not in titles:
        body = {"requests": [{"addSheet": {"properties": {"title": tab_name}}}]}
        try:
            service.spreadsheets().batchUpdate(spreadsheetId=sheet_id, body=body).execute()
        except HttpError as exc:
            raise SheetsWriteError(f"Error creando pestaña {tab_name}: {exc}") from exc
        logger.info("Pestaña creada", extra={"tab": tab_name})

    existing = read_historic_tab(credentials=credentials, sheet_id=sheet_id, tab_name=tab_name)
    if existing.empty:
        headers = list(schema_columns_for_tab(tab_name))
        service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=f"{tab_name}!A1",
            valueInputOption="RAW",
            body={"values": [headers]},
        ).execute()


def append_rows(
    *,
    credentials: Credentials,
    sheet_id: str,
    tab_name: str,
    df: pd.DataFrame,
) -> int:
    """Append filas al final de una pestaña (sin headers)."""
    if df.empty:
        return 0

    ensure_tab_with_headers(credentials=credentials, sheet_id=sheet_id, tab_name=tab_name)
    service = build("sheets", "v4", credentials=credentials, cache_discovery=False)
    values = _dataframe_to_values(df)

    try:
        service.spreadsheets().values().append(
            spreadsheetId=sheet_id,
            range=f"{tab_name}!A1",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": values},
        ).execute()
    except HttpError as exc:
        raise SheetsWriteError(f"Error append en {tab_name}: {exc}") from exc

    logger.info("Filas append OK", extra={"tab": tab_name, "rows": len(values)})
    return len(values)


def publish_snapshot_to_sheets(
    *,
    credentials: Credentials,
    sheet_id: str,
    tab_resumen: str,
    tab_por_agente: str,
    tab_por_motivo: str,
    tab_wow: str,
    resumen: pd.DataFrame,
    por_agente: pd.DataFrame,
    por_motivo: pd.DataFrame,
    wow: pd.DataFrame,
    week_id: str,
    skip_if_exists: bool = True,
) -> dict[str, int]:
    """Publica snapshot en las 4 pestañas histórico. Idempotente por week_id."""
    if skip_if_exists and week_id_exists_in_resumen(
        credentials=credentials,
        sheet_id=sheet_id,
        tab_name=tab_resumen,
        week_id=week_id,
    ):
        raise SheetsWriteError(f"La semana {week_id} ya está publicada en {tab_resumen}")

    counts: dict[str, int] = {}
    for tab, frame in [
        (tab_resumen, resumen),
        (tab_por_agente, por_agente),
        (tab_por_motivo, por_motivo),
        (tab_wow, wow),
    ]:
        counts[tab] = append_rows(
            credentials=credentials,
            sheet_id=sheet_id,
            tab_name=tab,
            df=frame,
        )
    return counts
