from __future__ import annotations

import logging
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError, field_validator

from qa_weekly_analytics.storage.historic_schema import (
    TAB_POR_AGENTE,
    TAB_POR_MOTIVO,
    TAB_RESUMEN,
    TAB_WOW,
)

logger = logging.getLogger(__name__)


class SettingsError(Exception):
    """Error de configuración de la aplicación."""


def _summarize_validation_error(exc: ValidationError) -> str:
    """Resume errores de validación sin incluir valores sensibles.

    Args:
        exc: ValidationError de Pydantic.

    Returns:
        Mensaje resumido con campos y errores (sin incluir el valor inválido).
    """
    chunks: list[str] = []
    for err in exc.errors():
        loc = err.get("loc", ())
        msg = err.get("msg", "invalid")

        field = "unknown"
        if isinstance(loc, (list, tuple)) and loc:
            field = str(loc[0])
            if len(loc) > 1 and isinstance(loc[1], int):
                field = f"{field}[{loc[1]}]"

        chunks.append(f"{field}: {msg}")

    return "; ".join(chunks)


class Settings(BaseModel):
    """Configuración central del proyecto QA Weekly Analytics."""

    # Sheets
    SHEET_ID: str = Field(..., min_length=5)
    SHEET_TAB: str = Field(default="Operativa 2026")
    SHEET_RANGE: str = Field(default="A1:G1619")

    # Timezone
    TIMEZONE: str = Field(default="America/Bogota")

    # Histórico — pestañas en Google Sheets
    HIST_TAB_RESUMEN: str = Field(default=TAB_RESUMEN)
    HIST_TAB_POR_AGENTE: str = Field(default=TAB_POR_AGENTE)
    HIST_TAB_POR_MOTIVO: str = Field(default=TAB_POR_MOTIVO)
    HIST_TAB_WOW: str = Field(default=TAB_WOW)

    # Histórico — Excel local
    HISTORIC_EXCEL_PATH: str = Field(default="data/Registro_QA_Historico.xlsx")

    # Scheduler (APScheduler)
    SCHEDULER_ENABLED: bool = Field(default=False)
    SCHEDULER_CRON_DAY: str = Field(default="mon")
    SCHEDULER_CRON_HOUR: int = Field(default=8, ge=0, le=23)
    SCHEDULER_CRON_MINUTE: int = Field(default=0, ge=0, le=59)

    def historic_excel_path_resolved(self, repo_root: Path | None = None) -> Path:
        """Ruta absoluta al Excel de histórico."""
        p = Path(self.HISTORIC_EXCEL_PATH)
        if p.is_absolute():
            return p
        root = repo_root or Path(__file__).resolve().parents[3]
        return (root / p).resolve()

    @field_validator("TIMEZONE")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        """Valida formato básico de timezone IANA (ej: America/Bogota).

        Args:
            v: Timezone.

        Returns:
            Timezone normalizada.

        Raises:
            ValueError: Si no tiene el formato esperado.
        """
        tz = (v or "").strip()
        if not re.match(r"^[A-Za-z_]+/[A-Za-z_]+$", tz):
            raise ValueError("TIMEZONE inválida (ej: America/Bogota)")
        return tz

    @classmethod
    def from_env(cls) -> "Settings":
        """Carga la configuración desde variables de entorno (incluye .env).

        Returns:
            Settings: Instancia validada.

        Raises:
            SettingsError: Si faltan variables requeridas o hay valores inválidos.
        """
        load_dotenv()

        try:
            sched_enabled = (os.getenv("SCHEDULER_ENABLED", "false") or "false").strip().lower() in {"1", "true", "yes", "on"}
            settings = cls(
                SHEET_ID=os.getenv("SHEET_ID", ""),
                SHEET_TAB=os.getenv("SHEET_TAB", "Operativa 2026"),
                SHEET_RANGE=os.getenv("SHEET_RANGE", "A1:G1619"),
                TIMEZONE=os.getenv("TIMEZONE", "America/Bogota"),
                HIST_TAB_RESUMEN=os.getenv("HIST_TAB_RESUMEN", TAB_RESUMEN),
                HIST_TAB_POR_AGENTE=os.getenv("HIST_TAB_POR_AGENTE", TAB_POR_AGENTE),
                HIST_TAB_POR_MOTIVO=os.getenv("HIST_TAB_POR_MOTIVO", TAB_POR_MOTIVO),
                HIST_TAB_WOW=os.getenv("HIST_TAB_WOW", TAB_WOW),
                HISTORIC_EXCEL_PATH=os.getenv("HISTORIC_EXCEL_PATH", "data/Registro_QA_Historico.xlsx"),
                SCHEDULER_ENABLED=sched_enabled,
                SCHEDULER_CRON_DAY=os.getenv("SCHEDULER_CRON_DAY", "mon"),
                SCHEDULER_CRON_HOUR=int(os.getenv("SCHEDULER_CRON_HOUR", "8")),
                SCHEDULER_CRON_MINUTE=int(os.getenv("SCHEDULER_CRON_MINUTE", "0")),
            )
            logger.info("Settings cargados correctamente")
            return settings
        except ValidationError as exc:
            summary = _summarize_validation_error(exc)
            logger.error("Error validando Settings", extra={"summary": summary})
            raise SettingsError(f"Configuración inválida: {summary}") from exc
