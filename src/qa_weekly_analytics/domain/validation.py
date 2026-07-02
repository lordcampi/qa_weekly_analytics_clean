from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Any

import pandas as pd

from qa_weekly_analytics.domain.normalization import (
    normalize_critical_flags,
    normalize_dates,
)

logger = logging.getLogger(__name__)


class DataValidationError(Exception):
    """Error de validación/limpieza a nivel de pipeline (no de fila individual)."""


@dataclass(frozen=True, slots=True)
class RowIssue:
    """Representa un problema de calidad de datos asociado a una fila.

    Attributes:
        row_number: Número de fila de la fuente (Google Sheets) para trazabilidad.
        reasons: Lista de razones por las que la fila se considera inválida.
        sample: Muestra de campos relevantes de la fila (sin transformación).
    """

    row_number: int
    reasons: list[str]
    sample: dict[str, Any]


@dataclass(frozen=True, slots=True)
class DataQualityReport:
    """Reporte agregado de calidad de datos.

    Attributes:
        total_rows: Total de filas recibidas (sin header).
        valid_rows: Filas válidas tras limpieza/validación mínima.
        invalid_rows: Filas descartadas por fallar requisitos mínimos.
        missing_columns: Columnas requeridas que no existen en el DataFrame.
        invalid_date_count: Cantidad de filas con fecha no parseable (no vacía).
        empty_date_count: Cantidad de filas con fecha vacía.
        invalid_critical_count: Cantidad de filas con crítico irreconocible (no vacía).
        empty_critical_count: Cantidad de filas con crítico vacío.
        missing_required_counts: Conteos por campo requerido vacío (Agente/Motivo).
        examples: Lista de ejemplos de filas inválidas con razones.
    """

    total_rows: int
    valid_rows: int
    invalid_rows: int
    missing_columns: list[str]
    invalid_date_count: int
    empty_date_count: int
    invalid_critical_count: int
    empty_critical_count: int
    missing_required_counts: dict[str, int]
    examples: list[RowIssue]


_REQUIRED_SOURCE_COLS: tuple[str, ...] = ("Fecha", "Agente", "Motivo")
_OPTIONAL_SOURCE_COLS: tuple[str, ...] = ("Caso/Ticket", "Error Critico?", "Observaciones", "Visto en 1:1")


def _safe_get_col(df: pd.DataFrame, name: str) -> pd.Series:
    """Devuelve una columna si existe; si no, devuelve una serie vacía del largo del df."""
    if name in df.columns:
        return df[name]
    return pd.Series([None] * len(df), index=df.index, dtype="object")


def clean_and_validate_rows(
    df: pd.DataFrame,
    *,
    source_row_start: int = 2,
    max_examples: int = 10,
) -> tuple[pd.DataFrame, DataQualityReport]:
    """Limpia y valida mínimamente filas provenientes de Google Sheets.

    Normaliza:
      - Fecha -> columna `date` (datetime.date) usando QA-003
      - Error Critico? -> columna `is_critical` (bool|None) usando QA-004
      - Agente/Motivo/Caso/Ticket/Observaciones -> strings recortados

    Valida (mínimo):
      - Requeridos: Fecha, Agente, Motivo
      - La fila se descarta si falta/está inválido cualquiera de esos tres.

    No detiene el pipeline: genera un reporte y devuelve solo filas válidas.

    Args:
        df: DataFrame crudo (sin header en filas; header ya aplicado).
        source_row_start: Número de fila en la fuente donde empieza el primer dato (por defecto 2).
        max_examples: Máximo de ejemplos de filas inválidas a incluir en reporte.

    Returns:
        Tuple: (clean_df, report)
            - clean_df: DataFrame con columnas normalizadas mínimas.
            - report: DataQualityReport con conteos y ejemplos.

    Raises:
        DataValidationError: Si df no es un DataFrame válido.
    """
    if not isinstance(df, pd.DataFrame):
        raise DataValidationError("df debe ser un pandas.DataFrame")

    total = int(df.shape[0])
    if total == 0:
        report = DataQualityReport(
            total_rows=0,
            valid_rows=0,
            invalid_rows=0,
            missing_columns=list(_REQUIRED_SOURCE_COLS),
            invalid_date_count=0,
            empty_date_count=0,
            invalid_critical_count=0,
            empty_critical_count=0,
            missing_required_counts={"Agente": 0, "Motivo": 0},
            examples=[],
        )
        return pd.DataFrame(), report

    missing_cols = [c for c in _REQUIRED_SOURCE_COLS if c not in df.columns]
    # Si faltan requeridas, no podemos validar correctamente; devolvemos vacío + reporte accionable.
    if missing_cols:
        logger.error(
            "Faltan columnas requeridas en el DataFrame",
            extra={"missing_columns": missing_cols, "available_columns": list(df.columns)},
        )
        report = DataQualityReport(
            total_rows=total,
            valid_rows=0,
            invalid_rows=total,
            missing_columns=missing_cols,
            invalid_date_count=0,
            empty_date_count=0,
            invalid_critical_count=0,
            empty_critical_count=0,
            missing_required_counts={"Agente": total if "Agente" in missing_cols else 0, "Motivo": total if "Motivo" in missing_cols else 0},
            examples=[],
        )
        return pd.DataFrame(), report

    # Trazabilidad: fila real en Google Sheets
    row_numbers = [source_row_start + int(i) for i in range(total)]

    # --- Normalización Fecha (QA-003)
    fecha_col = _safe_get_col(df, "Fecha")
    date_report = normalize_dates(fecha_col.tolist())
    normalized_dates: list[date | None] = date_report.parsed

    # --- Normalización crítico (QA-004) (no es requerido)
    crit_col = _safe_get_col(df, "Error Critico?")
    crit_report = normalize_critical_flags(crit_col.tolist())
    normalized_critical = crit_report.parsed

    # --- Strings básicos
    agent_raw = _safe_get_col(df, "Agente").astype("object")
    reason_raw = _safe_get_col(df, "Motivo").astype("object")
    ticket_raw = _safe_get_col(df, "Caso/Ticket").astype("object")
    notes_raw = _safe_get_col(df, "Observaciones").astype("object")

    agent = agent_raw.map(lambda x: str(x).strip() if x is not None else "")
    reason = reason_raw.map(lambda x: str(x).strip() if x is not None else "")
    ticket_id = ticket_raw.map(lambda x: str(x).strip() if x is not None else "")
    notes = notes_raw.map(lambda x: str(x).strip() if x is not None else "")

    # --- Validación mínima
    invalid_indices: list[int] = []
    examples: list[RowIssue] = []
    missing_required_counts = {"Agente": 0, "Motivo": 0}

    for idx in range(total):
        reasons: list[str] = []

        # Fecha requerida
        if normalized_dates[idx] is None:
            # distinguir vacío vs inválido
            s = str(fecha_col.iloc[idx]).strip() if fecha_col.iloc[idx] is not None else ""
            if not s:
                reasons.append("Fecha vacía")
            else:
                reasons.append("Fecha inválida/no parseable")

        # Agente requerido
        if agent.iloc[idx] == "":
            reasons.append("Agente vacío")
            missing_required_counts["Agente"] += 1

        # Motivo requerido
        if reason.iloc[idx] == "":
            reasons.append("Motivo vacío")
            missing_required_counts["Motivo"] += 1

        if reasons:
            invalid_indices.append(idx)
            if len(examples) < max_examples:
                sample = {
                    "Fecha": fecha_col.iloc[idx],
                    "Agente": agent_raw.iloc[idx],
                    "Motivo": reason_raw.iloc[idx],
                    "Caso/Ticket": ticket_raw.iloc[idx] if "Caso/Ticket" in df.columns else None,
                    "Error Critico?": crit_col.iloc[idx] if "Error Critico?" in df.columns else None,
                }
                examples.append(
                    RowIssue(
                        row_number=row_numbers[idx],
                        reasons=reasons,
                        sample=sample,
                    )
                )

    valid_mask = pd.Series([True] * total, index=df.index)
    if invalid_indices:
        valid_mask.iloc[invalid_indices] = False

    clean_df = pd.DataFrame(
        {
            "row_number": row_numbers,
            "date": normalized_dates,
            "agent": agent.tolist(),
            "ticket_id": ticket_id.tolist(),
            "reason": reason.tolist(),
            "is_critical": normalized_critical,
            "notes": notes.tolist(),
        }
    )

    valid_df = clean_df.loc[valid_mask.values].reset_index(drop=True)

    report = DataQualityReport(
        total_rows=total,
        valid_rows=int(valid_df.shape[0]),
        invalid_rows=int(total - valid_df.shape[0]),
        missing_columns=[],
        invalid_date_count=len(date_report.invalid_indices),
        empty_date_count=len(date_report.empty_indices),
        invalid_critical_count=len(crit_report.invalid_indices),
        empty_critical_count=len(crit_report.empty_indices),
        missing_required_counts=missing_required_counts,
        examples=examples,
    )

    logger.info(
        "Limpieza/validación completada",
        extra={
            "total_rows": report.total_rows,
            "valid_rows": report.valid_rows,
            "invalid_rows": report.invalid_rows,
            "invalid_date_count": report.invalid_date_count,
            "invalid_critical_count": report.invalid_critical_count,
        },
    )

    return valid_df, report