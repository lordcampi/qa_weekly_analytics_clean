from __future__ import annotations

from datetime import date, timedelta

from qa_weekly_analytics.domain.date_ranges import DateRange


def period_length_days(start_date: date, end_date: date) -> int:
    """Cantidad de días inclusivos en un rango."""
    if start_date > end_date:
        raise ValueError("start_date no puede ser mayor que end_date")
    return (end_date - start_date).days + 1


def comparison_ranges_for_period(start_date: date, end_date: date) -> tuple[DateRange, DateRange]:
    """Compara un periodo contra el periodo anterior de igual duración.

    Ejemplo quincena (10 días): compara contra los 10 días inmediatamente anteriores.
    Ejemplo semana L-V (5 días): compara contra la semana previa de 5 días.
    """
    length = period_length_days(start_date, end_date)
    current_range = DateRange(start_date=start_date, end_date=end_date)
    previous_end = start_date - timedelta(days=1)
    previous_start = previous_end - timedelta(days=length - 1)
    previous_range = DateRange(start_date=previous_start, end_date=previous_end)
    return current_range, previous_range


def comparison_label(current_range: DateRange, previous_range: DateRange) -> str:
    return (
        f"Periodo analizado: {current_range.start_date} → {current_range.end_date} | "
        f"Comparado contra: {previous_range.start_date} → {previous_range.end_date}"
    )
