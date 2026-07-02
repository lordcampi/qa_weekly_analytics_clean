from __future__ import annotations

import pandas as pd
import pytest

from qa_weekly_analytics.connectors.sheets_reader import SheetsReadError, read_range


class _DummyGet:
    def __init__(self, values: list[list[str]]):
        self._values = values

    def execute(self) -> dict[str, object]:
        return {"values": self._values, "range": "Hoja!A1:D3", "majorDimension": "ROWS"}


class _DummyValues:
    def __init__(self, values: list[list[str]]):
        self._values = values

    def get(self, *, spreadsheetId: str, range: str) -> _DummyGet:  # noqa: A002
        return _DummyGet(self._values)


class _DummySpreadsheets:
    def __init__(self, values: list[list[str]]):
        self._values = values

    def values(self) -> _DummyValues:
        return _DummyValues(self._values)


class _DummyService:
    def __init__(self, values: list[list[str]]):
        self._values = values

    def spreadsheets(self) -> _DummySpreadsheets:
        return _DummySpreadsheets(self._values)


@pytest.fixture
def patch_build(monkeypatch: pytest.MonkeyPatch):
    def _apply(values: list[list[str]]) -> None:
        monkeypatch.setattr(
            "qa_weekly_analytics.connectors.sheets_reader.build",
            lambda *args, **kwargs: _DummyService(values),
        )

    return _apply


def test_read_range_normalizes_headers_and_padding(patch_build) -> None:
    values = [
        ["Fecha", "Agente", "", "Agente"],  # header con vacío y duplicado
        ["01/01/2026", "Juan", "X", "Pedro"],
        ["02/01/2026", "Ana"],  # fila corta que debe paddearse
    ]
    patch_build(values)

    data = read_range(
        credentials=object(),  # no se usa por el mock
        sheet_id="sheet123",
        sheet_tab="Hoja Operativa 2026",
        sheet_range="A1:D3",
    )

    assert isinstance(data.df, pd.DataFrame)
    assert list(data.df.columns) == ["Fecha", "Agente", "col_2", "Agente_1"]
    assert data.df.shape == (2, 4)
    assert data.df.iloc[1, 2] == ""  # padding
    assert data.meta.sheet_id == "sheet123"
    assert data.meta.full_range == "Hoja Operativa 2026!A1:D3"


def test_read_range_extends_headers_if_data_wider_than_header(patch_build) -> None:
    values = [
        ["A", "B"],  # header corto
        ["1", "2", "3"],  # fila más ancha
    ]
    patch_build(values)

    data = read_range(
        credentials=object(),
        sheet_id="sheet123",
        sheet_tab="Hoja",
        sheet_range="A1:C2",
    )

    assert list(data.df.columns) == ["A", "B", "col_2"]
    assert data.df.shape == (1, 3)
    assert data.df.iloc[0, 2] == "3"


def test_read_range_empty_raises(patch_build) -> None:
    patch_build([])

    with pytest.raises(SheetsReadError):
        read_range(
            credentials=object(),
            sheet_id="sheet123",
            sheet_tab="Hoja",
            sheet_range="A1:B2",
        )
