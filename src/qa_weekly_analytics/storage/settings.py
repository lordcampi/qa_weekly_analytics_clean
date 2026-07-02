from __future__ import annotations

import logging
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError, field_validator

logger = logging.getLogger(__name__)


class SettingsError(Exception):
    """Error de configuración de la aplicación."""


def _summarize_validation_error(exc: ValidationError) -> str:
    """Resume errores de validación sin incluir valores sensibles."""
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

    # Fuente de datos: URL pública de Google Sheets publicada como CSV
    DATA_URL: str = Field(..., min_length=10)

    # Timezone
    TIMEZONE: str = Field(default="America/Bogota")

    # Excel local (descarga opcional)
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
        """Valida formato básico de timezone IANA."""
        tz = (v or "").strip()
        if not re.match(r"^[A-Za-z_]+/[A-Za-z_]+$", tz):
            raise ValueError("TIMEZONE inválida (ej: America/Bogota)")
        return tz

    @field_validator("DATA_URL")
    @classmethod
    def validate_data_url(cls, v: str) -> str:
        """Acepta URL de Google Sheets publicado como CSV."""
        url = (v or "").strip()
        if not url:
            raise ValueError("DATA_URL es requerida")
        if not (url.startswith("http://") or url.startswith("https://")):
            raise ValueError("DATA_URL debe comenzar con http:// o https://")
        return url

    @classmethod
    def from_env(cls) -> "Settings":
        """Carga la configuración desde variables de entorno (incluye .env)."""
        load_dotenv()
        try:
            sched_enabled = (os.getenv("SCHEDULER_ENABLED", "false") or "false").strip().lower() in {"1", "true", "yes", "on"}
            settings = cls(
                DATA_URL=os.getenv("DATA_URL", ""),
                TIMEZONE=os.getenv("TIMEZONE", "America/Bogota"),
                HISTORIC_EXCEL_PATH=os.getenv("HISTORIC_EXCEL_PATH", "data/Registro_QA_Historico.xlsx"),
                SCHEDULER_ENABLED=sched_enabled,
                SCHEDULER_CRON_DAY=os.getenv("SCHEDULER_CRON_DAY", "mon"),
                SCHEDULER_CRON_HOUR=int(os.getenv("SCHEDULER_CRON_HOUR", "8")),
                SCHEDULER_CRON_MINUTE=int(os.getenv("SCHEDULER_CRON_MINUTE", "0")),
            )
            logger.info("Settings cargados correctamente desde .env")
            return settings
        except ValidationError as exc:
            summary = _summarize_validation_error(exc)
            logger.error("Error validando Settings", extra={"summary": summary})
            raise SettingsError(f"Configuración inválida: {summary}") from exc

    @classmethod
    def from_streamlit_secrets(cls) -> "Settings":
        """Carga la configuración desde st.secrets (Streamlit Cloud).

        Intenta primero st.secrets, luego variables de entorno (os.getenv).
        Streamlit Cloud exporta los secrets como variables de entorno
        automáticamente, así que os.getenv() es un fallback confiable.

        Cualquier error al acceder o usar st.secrets (incluyendo
        StreamlitSecretNotFoundError cuando no existe secrets.toml) hace
        fallback a os.getenv antes de lanzar SettingsError.
        """
        try:
            import streamlit as st  # type: ignore[import-untyped]
        except ImportError:
            raise SettingsError("Streamlit no está disponible") from None

        def _read_secret(key: str, default: str = "") -> str:
            """Lee un secreto probando: st.secrets → os.getenv → default."""
            # 1) Acceso como clave de dict (más común en Streamlit Cloud)
            try:
                val = st.secrets[key]
                if val is not None and str(val).strip():
                    return str(val)
            except (KeyError, TypeError, Exception):
                pass

            # 2) Acceso como atributo (AttrDict de Streamlit)
            try:
                val = getattr(st.secrets, key, None)
                if val is not None and str(val).strip():
                    return str(val)
            except Exception:
                pass

            # 3) .get() tradicional
            try:
                val = st.secrets.get(key)
                if val is not None and str(val).strip():
                    return str(val)
            except Exception:
                pass

            # 4) Fallback: variable de entorno (Streamlit Cloud las exporta)
            env_val = os.getenv(key)
            if env_val is not None and env_val.strip():
                logger.info("Leyendo %s desde os.getenv (fallback de secrets)", key)
                return env_val.strip()

            return default

        try:
            sched_enabled = _read_secret("SCHEDULER_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}

            settings = cls(
                DATA_URL=_read_secret("DATA_URL"),
                TIMEZONE=_read_secret("TIMEZONE", "America/Bogota"),
                HISTORIC_EXCEL_PATH=_read_secret("HISTORIC_EXCEL_PATH", "data/Registro_QA_Historico.xlsx"),
                SCHEDULER_ENABLED=sched_enabled,
                SCHEDULER_CRON_DAY=_read_secret("SCHEDULER_CRON_DAY", "mon"),
                SCHEDULER_CRON_HOUR=int(_read_secret("SCHEDULER_CRON_HOUR", "8")),
                SCHEDULER_CRON_MINUTE=int(_read_secret("SCHEDULER_CRON_MINUTE", "0")),
            )
            logger.info("Settings cargados desde st.secrets / env")
            return settings
        except ValidationError as exc:
            summary = _summarize_validation_error(exc)
            # Intenta mostrar las claves disponibles para diagnóstico
            available_keys = []
            env_data_url = os.getenv("DATA_URL", "(no definida)")
            try:
                secrets = st.secrets
                if hasattr(secrets, "keys"):
                    available_keys = list(secrets.keys())
                else:
                    available_keys = [k for k in dir(secrets) if not k.startswith("_")]
            except Exception:
                available_keys = ["(error al leer secrets)"]
            extra_info = (
                f" (claves st.secrets: {available_keys}, "
                f"os.getenv('DATA_URL'): {env_data_url!r})"
            )
            logger.error(
                "Error validando Settings desde secrets",
                extra={"summary": summary, "available_keys": available_keys, "env_DATA_URL": env_data_url},
            )
            raise SettingsError(f"Configuración inválida (secrets): {summary}{extra_info}") from exc
        except Exception as exc:
            raise SettingsError(f"No se pudieron leer st.secrets: {exc}") from exc
