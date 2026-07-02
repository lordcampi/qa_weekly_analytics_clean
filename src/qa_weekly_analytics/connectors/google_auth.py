from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Sequence

from google.auth.credentials import Credentials
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials as UserCredentials
from google_auth_oauthlib.flow import InstalledAppFlow

logger = logging.getLogger(__name__)


class GoogleAuthError(Exception):
    """Error durante el proceso de autenticación con Google APIs."""


def _safe_exc_message(exc: Exception) -> str:
    """Devuelve un mensaje útil sin exponer tokens."""
    msg = str(exc).strip()
    if not msg:
        msg = exc.__class__.__name__
    return msg


def _scopes_sufficient(creds: UserCredentials, scopes_list: list[str]) -> bool:
    """True si el token cubre todos los scopes pedidos."""
    if hasattr(creds, "has_scopes"):
        return bool(creds.has_scopes(scopes_list))
    required = set(scopes_list)
    granted = set(creds.scopes or [])
    return required.issubset(granted)


def clear_cached_token(token_path: Path) -> None:
    """Borra token OAuth cacheado (fuerza re-autorización en el próximo login)."""
    token_path.unlink(missing_ok=True)
    logger.info("Token OAuth eliminado", extra={"token_path": str(token_path)})


def _run_console_flow(flow: InstalledAppFlow) -> UserCredentials:
    """Ejecuta OAuth en modo consola compatible con varias versiones."""
    run_console = getattr(flow, "run_console", None)
    if callable(run_console):
        return run_console()

    auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline")
    print("\nAbre esta URL en tu navegador, autoriza la app y pega el código aquí:\n")
    print(auth_url)
    code = input("\nCódigo de autorización: ").strip()
    flow.fetch_token(code=code)
    return flow.credentials


def get_credentials(
    *,
    scopes: Sequence[str],
    credentials_path: Path,
    token_path: Path,
    force_reauth: bool = False,
) -> Credentials:
    """Obtiene credenciales OAuth2 cacheadas o inicia flujo Installed App."""
    creds: UserCredentials | None = None
    scopes_list = list(scopes)

    try:
        if force_reauth:
            clear_cached_token(token_path)

        if token_path.exists():
            logger.info("Cargando token OAuth desde caché", extra={"token_path": str(token_path)})
            try:
                creds = UserCredentials.from_authorized_user_file(str(token_path), scopes_list)
            except Exception as exc:
                logger.warning("Token OAuth corrupto o ilegible; se borrará", extra={"error": _safe_exc_message(exc)})
                clear_cached_token(token_path)
                creds = None

            if creds is not None and not _scopes_sufficient(creds, scopes_list):
                logger.info("Token existente no cubre scopes requeridos; se borrará y se forzará re-autorización")
                clear_cached_token(token_path)
                creds = None

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                logger.info("Refrescando token OAuth expirado")
                try:
                    creds.refresh(Request())
                except Exception as exc:
                    logger.warning("No se pudo refrescar token; se forzará re-autorización", extra={"error": _safe_exc_message(exc)})
                    clear_cached_token(token_path)
                    creds = None

            if not creds or not creds.valid:
                if not credentials_path.exists():
                    raise GoogleAuthError(
                        f"No se encontró credentials.json en: {credentials_path}. "
                        "Coloca el archivo en la raíz del proyecto o define GOOGLE_CREDENTIALS_PATH."
                    )

                mode = (os.getenv("GOOGLE_OAUTH_MODE", "localserver") or "localserver").strip().lower()
                logger.info("Iniciando flujo OAuth Installed App", extra={"mode": mode, "scopes": scopes_list})

                flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), scopes=scopes_list)

                if mode == "console":
                    creds = _run_console_flow(flow)
                else:
                    creds = flow.run_local_server(host="localhost", port=0, open_browser=True, prompt="consent")

            token_path.parent.mkdir(parents=True, exist_ok=True)
            token_path.write_text(creds.to_json(), encoding="utf-8")  # type: ignore[union-attr]
            logger.info("Token OAuth guardado", extra={"token_path": str(token_path)})

        if not creds or not creds.valid:
            raise GoogleAuthError("No se pudieron obtener credenciales OAuth válidas")

        if not _scopes_sufficient(creds, scopes_list):
            if not force_reauth:
                logger.info("Reintentando OAuth con scopes completos")
                return get_credentials(
                    scopes=scopes,
                    credentials_path=credentials_path,
                    token_path=token_path,
                    force_reauth=True,
                )
            raise GoogleAuthError(
                "El token de Google no tiene permiso de escritura en Sheets. "
                f"Borrá {token_path} y volvé a autorizar la app."
            )

        return creds

    except GoogleAuthError:
        raise
    except Exception as exc:
        logger.exception("Fallo inesperado en autenticación OAuth")
        raise GoogleAuthError(f"Fallo inesperado en autenticación OAuth: {_safe_exc_message(exc)}") from exc
