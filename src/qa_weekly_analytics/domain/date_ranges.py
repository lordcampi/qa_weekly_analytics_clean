from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import pandas as pd

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


class DateRangeError(Exception):
    """Error al calcular rangos de fechas."""


@dataclass(frozen=True, slots=True)
class DateRange:
    """Rango de fechas inclusivo.

    Args:
        start_date: Fecha inicio (incluida).
        end_date: Fecha fin (incluida).
    """

    start_date: date
    end_date: date


def _get_timezone(tz_name: str) -> timezone:
    """Obtiene la zona horaria solicitada.

    En Windows, `zoneinfo` puede no tener base de datos de zonas instalada.
    Para el MVP, incluimos fallback seguro para America/Bogota (UTC-5, sin DST).

    Args:
        tz_name: Nombre IANA de la zona horaria.

    Returns:
        tzinfo: Objeto de zona horaria.

    Raises:
        DateRangeError: Si no se puede resolver la zona horaria.
    """
    if ZoneInfo is not None:
        try:
            return ZoneInfo(tz_name)  # type: ignore[misc]
        except Exception:
            pass

    if tz_name == "America/Bogota":
        return timezone(timedelta(hours=-5))

    raise DateRangeError(
        f"No se pudo resolver la zona horaria '{tz_name}'. "
        "Instala 'tzdata' o usa una TZ soportada por el sistema."
    )


def previous_week_monday_friday(
    *,
    tz_name: str = "America/Bogota",
    now: Optional[datetime] = None,
) -> DateRange:
    """Calcula el rango de la semana anterior (lunes a viernes, inclusive).

    Definición:
      1) Tomar la fecha de referencia en tz_name.
      2) Hallar el lunes de la semana actual (weekday: lunes=0).
      3) Restar 7 días => lunes de la semana anterior.
      4) Sumar 4 días => viernes de la semana anterior.

    Args:
        tz_name: Zona horaria IANA (por defecto America/Bogota).
        now: Momento de referencia. Si None, usa datetime.now(tz).

    Returns:
        DateRange: start_date (lunes) y end_date (viernes) de la semana anterior.

    Raises:
        DateRangeError: Si hay problemas con la TZ o el cálculo.
    """
    tz = _get_timezone(tz_name)

    ref = now if now is not None else datetime.now(tz)

    # Si now es naive, asumimos que ya está en tz_name.
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=tz)
    else:
        ref = ref.astimezone(tz)

    today = ref.date()
    weekday = today.weekday()  # lunes=0 ... domingo=6

    current_monday = today - timedelta(days=weekday)
    prev_monday = current_monday - timedelta(days=7)
    prev_friday = prev_monday + timedelta(days=4)

    if prev_monday > prev_friday:  # defensivo
        raise DateRangeError("Rango calculado inválido (start_date > end_date)")

    logger.debug(
        "Rango 'Semana anterior (L-V)' calculado",
        extra={
            "tz_name": tz_name,
            "now": ref.isoformat(),
            "today": str(today),
            "start_date": str(prev_monday),
            "end_date": str(prev_friday),
        },
    )

    return DateRange(start_date=prev_monday, end_date=prev_friday)


def this_week_monday_friday(
    *,
    tz_name: str = "America/Bogota",
    now: Optional[datetime] = None,
) -> DateRange:
    """Calcula el rango de la semana actual (lunes a viernes, inclusive).

    Args:
        tz_name: Zona horaria IANA (por defecto America/Bogota).
        now: Momento de referencia. Si None, usa datetime.now(tz).

    Returns:
        DateRange: start_date (lunes) y end_date (viernes) de la semana actual.

    Raises:
        DateRangeError: Si hay problemas con la TZ o el cálculo.
    """
    tz = _get_timezone(tz_name)
    ref = now if now is not None else datetime.now(tz)

    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=tz)
    else:
        ref = ref.astimezone(tz)

    today = ref.date()
    weekday = today.weekday()  # lunes=0 ... domingo=6

    current_monday = today - timedelta(days=weekday)
    current_friday = current_monday + timedelta(days=4)

    return DateRange(start_date=current_monday, end_date=current_friday)


def week_id_from_range(start_date: date, end_date: date) -> str:
    """Identificador estable para una semana L-V: YYYY-MM-DD_YYYY-MM-DD."""
    return f"{start_date.isoformat()}_{end_date.isoformat()}"


def monday_friday_for_date(d: date) -> DateRange:
    """Devuelve el rango L-V de la semana que contiene la fecha d."""
    weekday = d.weekday()
    monday = d - timedelta(days=weekday)
    friday = monday + timedelta(days=4)
    return DateRange(start_date=monday, end_date=friday)


def list_monday_friday_weeks(
    df: pd.DataFrame,
    *,
    date_col: str = "date",
    min_rows: int = 1,
) -> list[DateRange]:
    """Lista semanas L-V con al menos min_rows registros, ordenadas de más reciente a antigua."""
    if df.empty or date_col not in df.columns:
        return []

    dates = pd.to_datetime(df[date_col], errors="coerce").dt.date.dropna()
    if dates.empty:
        return []

    week_starts: set[date] = set()
    for d in dates.unique():
        week_starts.add(monday_friday_for_date(d).start_date)

    weeks: list[DateRange] = []
    for monday in sorted(week_starts):
        friday = monday + timedelta(days=4)
        count = int(((dates >= monday) & (dates <= friday)).sum())
        if count >= min_rows:
            weeks.append(DateRange(start_date=monday, end_date=friday))

    weeks.sort(key=lambda w: w.start_date, reverse=True)
    return weeks


def week_label(week_range: DateRange) -> str:
    """Etiqueta legible para UI: '02/06/2026 – 06/06/2026 (L-V)'."""
    return f"{week_range.start_date.strftime('%d/%m/%Y')} – {week_range.end_date.strftime('%d/%m/%Y')} (L-V)"


def merge_week_ranges(ranges: list[DateRange]) -> DateRange:
    """Une varias semanas en un rango continuo (min start, max end)."""
    if not ranges:
        raise ValueError("Se requiere al menos una semana")
    starts = [r.start_date for r in ranges]
    ends = [r.end_date for r in ranges]
    return DateRange(start_date=min(starts), end_date=max(ends))
