from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Sequence

logger = logging.getLogger(__name__)

# ----------------------------
# QA-003: Normalización de fechas mixtas
# ----------------------------

# Meses en español (normalizados sin tildes). Incluye variante "setiembre".
_SPANISH_MONTHS: dict[str, int] = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}

_RE_DDMMYYYY = re.compile(r"^\s*(\d{1,2})/(\d{1,2})/(\d{4})\s*$")
_RE_SPANISH_LONG = re.compile(
    r"^\s*(\d{1,2})\s+de\s+([A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+)\s+(\d{4})\s*$",
    flags=re.IGNORECASE,
)


def _strip_accents(text: str) -> str:
    """Elimina tildes/diacríticos de un texto.

    Args:
        text: Texto de entrada.

    Returns:
        Texto sin diacríticos.
    """
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def parse_mixed_date(value: Any) -> date | None:
    """Parsea fechas con dos formatos coexistentes.

    Soporta:
      - 'dd/mm/yyyy' (ej: '04/06/2026')
      - 'd de <mes> yyyy' en español (ej: '4 de junio 2026')

    Reglas:
      - Devuelve `datetime.date` (sin hora).
      - Si no se puede parsear o es inválida, devuelve `None`.
      - Función pura: no hace I/O.

    Args:
        value: Valor a parsear (str, date, datetime o None).

    Returns:
        Fecha normalizada o None si inválida/no soportada.
    """
    if value is None:
        return None

    if isinstance(value, date) and not isinstance(value, datetime):
        return value

    if isinstance(value, datetime):
        return value.date()

    text = str(value).strip()
    if not text:
        return None

    m = _RE_DDMMYYYY.match(text)
    if m:
        day_s, month_s, year_s = m.groups()
        try:
            return date(int(year_s), int(month_s), int(day_s))
        except ValueError:
            return None

    m = _RE_SPANISH_LONG.match(text)
    if m:
        day_s, month_name, year_s = m.groups()
        month_key = _strip_accents(month_name).lower().strip()
        month_num = _SPANISH_MONTHS.get(month_key)
        if month_num is None:
            return None
        try:
            return date(int(year_s), int(month_num), int(day_s))
        except ValueError:
            return None

    return None


@dataclass(frozen=True, slots=True)
class DateNormalizationReport:
    """Reporte de normalización de fechas.

    Attributes:
        parsed: Lista de fechas parseadas (None si inválida/no parseable).
        invalid_indices: Índices de entradas no vacías que no se pudieron parsear.
        empty_indices: Índices de entradas vacías (None, '', espacios).
    """

    parsed: list[date | None]
    invalid_indices: list[int]
    empty_indices: list[int]


def normalize_dates(values: Sequence[Any]) -> DateNormalizationReport:
    """Normaliza una secuencia de valores a fechas, reportando inválidos sin romper.

    Considera:
      - Empty: None o string vacío/espacios → empty_indices.
      - Invalid: no vacío pero no parseable/fecha inválida → invalid_indices.

    Args:
        values: Secuencia de valores con posibles formatos mezclados.

    Returns:
        DateNormalizationReport con parsed + índices de empty/invalid.
    """
    parsed: list[date | None] = []
    invalid: list[int] = []
    empty: list[int] = []

    for idx, v in enumerate(values):
        if v is None:
            parsed.append(None)
            empty.append(idx)
            continue

        s = str(v).strip()
        if not s:
            parsed.append(None)
            empty.append(idx)
            continue

        d = parse_mixed_date(v)
        parsed.append(d)
        if d is None:
            invalid.append(idx)

    logger.debug(
        "Reporte normalización fechas",
        extra={
            "total": len(values),
            "parsed_ok": len(values) - len(invalid) - len(empty),
            "invalid": len(invalid),
            "empty": len(empty),
        },
    )

    return DateNormalizationReport(parsed=parsed, invalid_indices=invalid, empty_indices=empty)


# ----------------------------
# QA-004: Normalización "Error Critico?" (SI/NO -> bool)
# ----------------------------

_TRUE_TOKENS: set[str] = {"si", "sí", "s", "true", "1", "y", "yes"}
_FALSE_TOKENS: set[str] = {"no", "n", "false", "0"}


def parse_critical_flag(value: Any) -> bool | None:
    """Normaliza el campo "Error Critico?" a booleano.

    Soporta:
      - "SI"/"NO" (tolerante a mayúsculas, espacios, tildes en "sí")
      - Variantes comunes: "S", "N", "true/false", "1/0", "yes/no"
      - bool nativo

    Reglas:
      - Reconocible -> True/False
      - None o vacío -> None
      - Irreconocible -> None

    Args:
        value: Valor crudo de la celda.

    Returns:
        True/False si reconocible; None si vacío/irreconocible.
    """
    if value is None:
        return None

    if isinstance(value, bool):
        return value

    text = str(value).strip()
    if not text:
        return None

    token = text.casefold()
    # Normaliza "sí" y "si" (acepta ambos)
    token = token.replace("í", "i")

    if token in _TRUE_TOKENS:
        return True
    if token in _FALSE_TOKENS:
        return False

    return None


@dataclass(frozen=True, slots=True)
class CriticalNormalizationReport:
    """Reporte de normalización del flag crítico.

    Attributes:
        parsed: Lista de valores normalizados (True/False/None).
        invalid_indices: Índices donde el valor no era vacío pero fue irreconocible.
        empty_indices: Índices donde el valor era None o vacío/espacios.
    """

    parsed: list[bool | None]
    invalid_indices: list[int]
    empty_indices: list[int]


def normalize_critical_flags(values: Sequence[Any]) -> CriticalNormalizationReport:
    """Normaliza una secuencia de valores de "Error Critico?" y reporta incidencias.

    Considera:
      - Empty: None o string vacío/espacios → empty_indices
      - Invalid: no vacío pero no reconocible → invalid_indices

    Args:
        values: Secuencia de valores crudos.

    Returns:
        CriticalNormalizationReport con parsed + índices de empty/invalid.
    """
    parsed: list[bool | None] = []
    invalid: list[int] = []
    empty: list[int] = []

    for idx, v in enumerate(values):
        if v is None:
            parsed.append(None)
            empty.append(idx)
            continue

        s = str(v).strip()
        if not s:
            parsed.append(None)
            empty.append(idx)
            continue

        b = parse_critical_flag(v)
        parsed.append(b)
        if b is None:
            invalid.append(idx)

    logger.debug(
        "Reporte normalización crítico",
        extra={
            "total": len(values),
            "parsed_ok": len(values) - len(invalid) - len(empty),
            "invalid": len(invalid),
            "empty": len(empty),
        },
    )

    return CriticalNormalizationReport(parsed=parsed, invalid_indices=invalid, empty_indices=empty)
