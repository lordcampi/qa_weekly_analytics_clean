from __future__ import annotations

import pandas as pd

from qa_weekly_analytics.domain.validation import clean_and_validate_rows


def test_clean_and_validate_rows_filters_invalid_minimum_fields() -> None:
    df = pd.DataFrame(
        {
            "Fecha": ["04/06/2026", "31/02/2026", "", "4 de junio 2026"],
            "Agente": ["Juan", "Ana", "Pedro", ""],
            "Caso/Ticket": ["T1", "T2", "T3", "T4"],
            "Motivo": ["Login", "Pago", "", "Search"],
            "Error Critico?": ["SI", "NO", "MAYBE", ""],
            "Visto en 1:1": [True, False, True, False],
            "Observaciones": ["ok", "bad date", "missing reason", "missing agent"],
        }
    )

    valid_df, report = clean_and_validate_rows(df, source_row_start=2, max_examples=10)

    # Total filas
    assert report.total_rows == 4

    # Válidas: fila 0 (ok) únicamente.
    # fila 1: fecha inválida
    # fila 2: fecha vacía + motivo vacío
    # fila 3: agente vacío
    assert report.valid_rows == 1
    assert report.invalid_rows == 3

    # Validación de contenido normalizado
    assert list(valid_df.columns) == ["row_number", "date", "agent", "ticket_id", "reason", "is_critical", "notes"]
    assert valid_df.iloc[0]["agent"] == "Juan"
    assert valid_df.iloc[0]["reason"] == "Login"
    assert valid_df.iloc[0]["is_critical"] is True
    assert valid_df.iloc[0]["row_number"] == 2  # primera fila de datos

    # Reportes esperados (QA-003 / QA-004)
    assert report.invalid_date_count == 1  # "31/02/2026"
    assert report.empty_date_count == 1    # ""

    # Crítico: "MAYBE" inválido, "" vacío
    assert report.invalid_critical_count == 1
    assert report.empty_critical_count == 1

    # Conteos de requeridos por campo (Agente/Motivo)
    assert report.missing_required_counts["Agente"] == 1  # fila 3
    assert report.missing_required_counts["Motivo"] == 1  # fila 2

    # Ejemplos incluyen razones
    assert len(report.examples) == 3
    reasons_flat = [r for ex in report.examples for r in ex.reasons]
    assert "Fecha inválida/no parseable" in reasons_flat
    assert "Fecha vacía" in reasons_flat
    assert "Agente vacío" in reasons_flat
    assert "Motivo vacío" in reasons_flat


def test_clean_and_validate_rows_missing_required_columns_returns_empty() -> None:
    df = pd.DataFrame({"Fecha": ["04/06/2026"]})  # faltan Agente y Motivo

    valid_df, report = clean_and_validate_rows(df)

    assert report.total_rows == 1
    assert report.valid_rows == 0
    assert report.invalid_rows == 1
    assert set(report.missing_columns) == {"Agente", "Motivo"}
    assert valid_df.empty