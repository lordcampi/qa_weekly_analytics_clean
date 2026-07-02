from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

import pandas as pd
from google.auth.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from qa_weekly_analytics.domain.models import SheetData, SheetMeta

logger = logging.getLogger(__name__)


class SheetsReadError(Exception):
    """Error al leer datos desde Google Sheets."""


def _make_unique_headers(headers: list[str]) -> list[str]:
    """Normaliza headers: rellena vacíos y hace únicos duplicados.

    Reglas:
      - header vacío -> col_{idx}
      - duplicado -> {name}_{n}

    Args:
        headers: Lista de headers crudos (pueden incluir vacíos/duplicados).

    Returns:
        Lista de headers normalizados y únicos.
    """
    seen: dict[str, int] = {}
    normalized: list[str] = []

    for idx, raw in enumerate(headers):
        base = (raw or "").strip() or f"col_{idx}"
        count = seen.get(base, 0)
        name = f"{base}_{count}" if count > 0 else base
        seen[base] = count + 1
        normalized.append(name)

    return normalized


def _http_error_details(exc: HttpError) -> tuple[int | None, str]:
    """Extrae status y detalle legible de un HttpError de Google."""
    status = getattr(exc.resp, "status", None)
    raw = ""
    try:
        raw = exc.content.decode("utf-8", errors="replace") if getattr(exc, "content", None) else str(exc)
        # Intenta pretty-print si viene JSON
        try:
            raw_json = json.loads(raw)
            raw = json.dumps(raw_json, ensure_ascii=False, indent=2)
        except Exception:
            pass
    except Exception:
        raw = str(exc)
    return status, raw


def read_range(
    *,
    credentials: Credentials,
    sheet_id: str,
    sheet_tab: str,
    sheet_range: str,
) -> SheetData:
    """Lee un rango fijo de Google Sheets y lo devuelve como DataFrame.

    Implementación:
      - Sheets API v4: spreadsheets.values.get
      - Primera fila = headers
      - Maneja headers vacíos/duplicados
      - Padding de filas a número máximo de columnas observado

    Args:
        credentials: Credenciales OAuth2 válidas.
        sheet_id: ID del Google Sheet (NO URL).
        sheet_tab: Nombre del tab/hoja.
        sheet_range: Rango A1 (ej: A1:G1619).

    Returns:
        SheetData con df y meta.

    Raises:
        SheetsReadError: Si el rango está vacío o hay errores de API/formato.
    """
    full_range = f"{sheet_tab}!{sheet_range}"
    fetched_at = datetime.now(timezone.utc)

    try:
        service = build("sheets", "v4", credentials=credentials, cache_discovery=False)

        logger.info("Leyendo rango", extra={"sheet_id": sheet_id, "range": full_range})

        payload: dict[str, Any] = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId=sheet_id, range=full_range)
            .execute()
        )

        values: list[list[Any]] = payload.get("values", [])
        if not values:
            raise SheetsReadError("El rango está vacío o no contiene datos")

        header_row = [str(x) for x in (values[0] if values else [])]
        data_rows = values[1:] if len(values) > 1 else []

        max_len = max([len(header_row)] + [len(r) for r in data_rows] + [0])
        padded_header = header_row + [""] * (max_len - len(header_row))
        headers = _make_unique_headers(padded_header)

        padded_rows: list[list[str]] = []
        for r in data_rows:
            row = [str(x) for x in r] + [""] * (max_len - len(r))
            padded_rows.append(row)

        df = pd.DataFrame(padded_rows, columns=headers)

        meta = SheetMeta(
            sheet_id=sheet_id,
            sheet_tab=sheet_tab,
            a1_range=sheet_range,
            full_range=full_range,
            rows=int(df.shape[0]),
            columns=int(df.shape[1]),
            fetched_at=fetched_at,
            raw={
                "range": payload.get("range"),
                "majorDimension": payload.get("majorDimension"),
            },
        )

        logger.info("Lectura OK", extra={"rows": meta.rows, "cols": meta.columns})
        return SheetData(df=df, meta=meta)

    except SheetsReadError:
        raise
    except HttpError as exc:
        status, details = _http_error_details(exc)
        logger.error("HttpError Sheets", extra={"status": status, "range": full_range, "details": details[:1000]})
        raise SheetsReadError(f"Error de API de Google Sheets (HTTP {status}) al leer {full_range}:\n{details}") from exc
    except Exception as exc:  # pragma: no cover
        logger.exception("Error inesperado leyendo Google Sheets")
        raise SheetsReadError(f"Error inesperado leyendo Google Sheets: {exc}") from exc
