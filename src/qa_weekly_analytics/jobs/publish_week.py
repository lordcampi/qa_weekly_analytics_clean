from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SRC_PATH = _REPO_ROOT / "src"
if str(_SRC_PATH) not in sys.path:
    sys.path.insert(0, str(_SRC_PATH))

from qa_weekly_analytics.connectors.google_auth import GoogleAuthError, get_credentials  # noqa: E402
from qa_weekly_analytics.connectors.sheets_reader import SheetsReadError, read_range  # noqa: E402
from qa_weekly_analytics.domain.date_ranges import DateRange, previous_week_monday_friday  # noqa: E402
from qa_weekly_analytics.domain.validation import clean_and_validate_rows  # noqa: E402
from qa_weekly_analytics.storage.publish_weekly_snapshot import PublishSnapshotError, publish_weekly_snapshot  # noqa: E402
from qa_weekly_analytics.storage.settings import Settings, SettingsError  # noqa: E402

logger = logging.getLogger(__name__)

GOOGLE_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def _setup_logging() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


def _load_data(settings: Settings):
    credentials_path = Path(os.getenv("GOOGLE_CREDENTIALS_PATH", ".secrets/credentials.json")).resolve()
    token_path = Path(os.getenv("GOOGLE_TOKEN_PATH", ".secrets/token.json")).resolve()
    creds = get_credentials(scopes=GOOGLE_SCOPES, credentials_path=credentials_path, token_path=token_path)
    sheet_data = read_range(
        credentials=creds,
        sheet_id=settings.SHEET_ID,
        sheet_tab=settings.SHEET_TAB,
        sheet_range=settings.SHEET_RANGE,
    )
    valid_df, _ = clean_and_validate_rows(sheet_data.df, source_row_start=2, max_examples=10)
    return valid_df, creds


def run_publish_week(
    *,
    settings: Settings | None = None,
    week_range: DateRange | None = None,
    to_sheets: bool = True,
    to_excel: bool = True,
    force: bool = False,
) -> int:
    """Publica la semana indicada (o la anterior L-V) en Sheets y Excel."""
    _setup_logging()
    settings = settings or Settings.from_env()

    try:
        df, _read_creds = _load_data(settings)
    except (SettingsError, GoogleAuthError, SheetsReadError) as exc:
        logger.error("No se pudo cargar datos: %s", exc)
        return 1

    if df.empty:
        logger.error("No hay filas válidas para publicar")
        return 1

    if week_range is None:
        week_range = previous_week_monday_friday(tz_name=settings.TIMEZONE)

    write_creds = None
    if to_sheets:
        credentials_path = Path(os.getenv("GOOGLE_CREDENTIALS_PATH", ".secrets/credentials.json")).resolve()
        token_path = Path(os.getenv("GOOGLE_TOKEN_PATH", ".secrets/token.json")).resolve()
        try:
            write_creds = get_credentials(scopes=GOOGLE_SCOPES, credentials_path=credentials_path, token_path=token_path)
        except GoogleAuthError as exc:
            logger.error("OAuth write falló: %s", exc)
            return 1

    try:
        result = publish_weekly_snapshot(
            df,
            week_range=week_range,
            settings=settings,
            credentials=write_creds,
            to_sheets=to_sheets,
            to_excel=to_excel,
            force=force,
        )
    except PublishSnapshotError as exc:
        logger.error("Publicación falló: %s", exc)
        return 1

    if result.skipped:
        logger.info("Semana %s ya publicada — omitida", result.week_id)
    else:
        logger.info(
            "Semana %s publicada OK (sheets=%s, excel=%s)",
            result.week_id,
            result.sheets_counts,
            result.excel_path,
        )
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Publica snapshot semanal QA en Sheets y Excel")
    parser.add_argument("--excel-only", action="store_true", help="Solo escribir Excel local")
    parser.add_argument("--sheets-only", action="store_true", help="Solo escribir Google Sheets")
    parser.add_argument("--force", action="store_true", help="Intentar republicar (Excel)")
    args = parser.parse_args()

    to_sheets = not args.excel_only
    to_excel = not args.sheets_only
    raise SystemExit(run_publish_week(to_sheets=to_sheets, to_excel=to_excel, force=args.force))


if __name__ == "__main__":
    main()
