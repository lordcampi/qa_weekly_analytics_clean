from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pandas as pd


@dataclass(frozen=True, slots=True)
class SheetMeta:
    """Metadata de una lectura de Google Sheets.

    Attributes:
        sheet_id: ID del spreadsheet.
        sheet_tab: Nombre de la pestaña/hoja.
        a1_range: Rango A1 solicitado (sin el nombre de la hoja).
        full_range: Rango completo solicitado (hoja!rango).
        rows: Número de filas de datos (excluye header).
        columns: Número de columnas del DataFrame.
        fetched_at: Timestamp de la lectura (UTC).
        raw: Payload mínimo útil devuelto por la API (si aplica).
    """

    sheet_id: str
    sheet_tab: str
    a1_range: str
    full_range: str
    rows: int
    columns: int
    fetched_at: datetime
    raw: dict[str, Any]


@dataclass(frozen=True, slots=True)
class SheetData:
    """Resultado de lectura: DataFrame + metadata."""

    df: pd.DataFrame
    meta: SheetMeta