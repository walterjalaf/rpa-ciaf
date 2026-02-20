"""
Cliente HTTP para comunicación con el servidor Laravel.

Por qué existe: Centraliza toda la comunicación HTTP en un solo módulo para
que el resto del sistema (uploader, reporter) no tenga que conocer detalles
de red, autenticación ni manejo de errores HTTP.

Cuando USE_MOCK = True, todas las operaciones se simulan localmente con datos
de mock_data.py. Cuando USE_MOCK = False, usa httpx contra SERVER_URL.

Uso:
    client = ApiClient()
    client.load_token()  # Carga token desde Windows Credential Vault
    client.upload_file(task_id, filepath, metadata)
"""

from __future__ import annotations

import logging
import platform
from datetime import date
from pathlib import Path

from config import settings
from sync.exceptions import ApiAuthError, ServerUnreachableError, UploadError

logger = logging.getLogger(__name__)


class ApiClient:
    """
    Cliente HTTP para el servidor Laravel de conciliaciones.

    Por qué existe: Es la única puerta de salida HTTP del sistema. Ningún otro
    módulo hace peticiones al servidor directamente. Esto permite cambiar de
    httpx a otra librería o agregar retry logic en un solo lugar.
    """

    def __init__(self) -> None:
        self._token: str | None = None
        self._base_url: str = settings.SERVER_URL
        self._client = None  # httpx.Client, inicializado solo en modo real

    def authenticate(self, token: str) -> None:
        """Configura el token de autenticación Bearer."""
        self._token = token
        logger.info("Token de autenticación configurado")

        if not settings.USE_MOCK and self._client is not None:
            self._client.headers["Authorization"] = f"Bearer {token}"

    def load_token(self) -> bool:
        """
        Carga el token desde Windows Credential Vault via keyring.

        Returns:
            True si se encontró y configuró un token, False si no hay token guardado.
        """
        if settings.USE_MOCK:
            self._token = "mock_token_dev"
            logger.info("Modo mock: token simulado cargado")
            return True

        import keyring
        token = keyring.get_password("rpa_conciliaciones", "api_token")
        if token:
            self.authenticate(token)
            return True

        logger.warning("No se encontró token en el vault de credenciales")
        return False

    def upload_file(self, task_id: str, filepath: Path,
                    metadata: dict) -> bool:
        """
        Sube un archivo Excel al servidor via POST /rpa/upload.

        Args:
            task_id: Identificador de la tarea.
            filepath: Ruta al archivo .xlsx o .csv descargado.
            metadata: Dict con date_from, date_to y otros campos del upload.

        Returns:
            True si el servidor aceptó el archivo.

        Raises:
            ApiAuthError: Si el token es inválido (HTTP 401).
            UploadError: Si el servidor rechazó el archivo (HTTP 422).
            ServerUnreachableError: Si no se pudo conectar al servidor.
        """
        if settings.USE_MOCK:
            from sync.mock_data import mock_upload_response
            response = mock_upload_response(task_id, filepath.name)
            logger.info(
                "Mock upload: %s → %s (%s)",
                filepath.name, task_id, response["message"]
            )
            return True

        return self._upload_file_real(task_id, filepath, metadata)

    def report_failure(self, task_id: str, error: str,
                       screenshot_path: Path | None = None) -> None:
        """
        Reporta un fallo de bot al servidor via POST /rpa/failure.

        No propaga excepciones: el reporte de error no debe causar otro error.
        """
        if settings.USE_MOCK:
            logger.info(
                "Mock report_failure: task=%s error='%s' screenshot=%s",
                task_id, error[:80], screenshot_path
            )
            return

        self._report_failure_real(task_id, error, screenshot_path)

    def report_telemetry(self, task_id: str, date_from: date,
                         date_to: date, row_count: int,
                         file_size_kb: float,
                         duration_seconds: float) -> None:
        """
        Envía métricas de una tarea exitosa via POST /rpa/telemetry.

        No propaga excepciones: la telemetría no debe bloquear el flujo.
        """
        if settings.USE_MOCK:
            logger.info(
                "Mock telemetría: task=%s periodo=%s→%s filas=%d "
                "tamaño=%.1fKB duración=%.1fs",
                task_id, date_from, date_to, row_count,
                file_size_kb, duration_seconds
            )
            return

        self._report_telemetry_real(
            task_id, date_from, date_to, row_count,
            file_size_kb, duration_seconds
        )

    def report_session_check(self, results: list) -> None:
        """
        Envía resultados del health check via POST /rpa/session_check.

        No propaga excepciones: el reporte de sesiones no debe bloquear el flujo.

        Args:
            results: Lista de SessionStatus (de core/health_checker.py).
        """
        if settings.USE_MOCK:
            logger.info(
                "Mock session_check: %d resultados reportados",
                len(results)
            )
            return

        self._report_session_check_real(results)

    # ── Métodos privados: implementación HTTP real (Feature 11) ──

    def _ensure_client(self) -> None:
        """Inicializa el cliente httpx si no existe."""
        if self._client is not None:
            return

        import httpx
        self._client = httpx.Client(
            base_url=self._base_url,
            timeout=settings.HTTP_TIMEOUT_SECONDS,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self._token}" if self._token else "",
            },
        )

    def _handle_response_errors(self, response) -> None:
        """Maneja errores HTTP comunes según la política del proyecto."""
        if response.status_code == 401:
            raise ApiAuthError(
                "Token de autenticación inválido o expirado. "
                "Reconfigurar el token en la app."
            )
        if response.status_code == 422:
            detail = response.json() if response.content else {}
            raise UploadError(
                f"El servidor rechazó los datos: {detail}"
            )
        if response.status_code >= 500:
            logger.error(
                "Error del servidor (HTTP %d): %s",
                response.status_code, response.text[:200]
            )

    def _upload_file_real(self, task_id: str, filepath: Path,
                          metadata: dict) -> bool:
        """Implementación real de upload_file con httpx."""
        self._ensure_client()
        try:
            with open(filepath, "rb") as f:
                response = self._client.post(
                    "/rpa/upload",
                    files={"file": (filepath.name, f)},
                    data={
                        "task_id": task_id,
                        "date_from": metadata["date_from"].isoformat(),
                        "date_to": metadata["date_to"].isoformat(),
                        "machine_id": platform.node(),
                    },
                )
            self._handle_response_errors(response)
            return response.status_code in (200, 201)
        except (ApiAuthError, UploadError):
            raise
        except Exception as e:
            raise ServerUnreachableError(
                f"No se pudo conectar al servidor para subir el archivo: {e}"
            ) from e

    def _report_failure_real(self, task_id: str, error: str,
                             screenshot_path: Path | None) -> None:
        """Implementación real de report_failure con httpx."""
        try:
            self._ensure_client()
            files = None
            if screenshot_path and screenshot_path.exists():
                files = {
                    "screenshot": (screenshot_path.name,
                                   open(screenshot_path, "rb"))
                }
            self._client.post(
                "/rpa/failure",
                data={"task_id": task_id, "error": error},
                files=files,
            )
        except Exception as e:
            logger.warning("No se pudo reportar el fallo al servidor: %s", e)

    def _report_telemetry_real(self, task_id: str, date_from: date,
                               date_to: date, row_count: int,
                               file_size_kb: float,
                               duration_seconds: float) -> None:
        """Implementación real de report_telemetry con httpx."""
        try:
            self._ensure_client()
            self._client.post(
                "/rpa/telemetry",
                json={
                    "task_id": task_id,
                    "date_from": date_from.isoformat(),
                    "date_to": date_to.isoformat(),
                    "row_count": row_count,
                    "file_size_kb": file_size_kb,
                    "duration_seconds": duration_seconds,
                    "machine_id": platform.node(),
                },
            )
        except Exception as e:
            logger.warning("Telemetría no enviada: %s", e)

    def _report_session_check_real(self, results: list) -> None:
        """Implementación real de report_session_check con httpx."""
        try:
            self._ensure_client()
            payload = [
                {
                    "task_id": r.task_id,
                    "task_name": r.task_name,
                    "is_logged_in": r.is_logged_in,
                    "checked_at": r.checked_at.isoformat(),
                    "error": r.error,
                }
                for r in results
            ]
            self._client.post("/rpa/session_check", json=payload)
        except Exception as e:
            logger.warning(
                "No se pudo reportar estado de sesiones: %s", e
            )


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    client = ApiClient()
    client.load_token()
    print(f"Token cargado: {client._token is not None}")
    print(f"Modo mock: {settings.USE_MOCK}")

    # Probar upload mock
    from pathlib import Path as P
    result = client.upload_file(
        "mercadopago_movimientos",
        P("test.xlsx"),
        {"date_from": date(2026, 2, 17), "date_to": date(2026, 2, 17)},
    )
    print(f"Upload resultado: {result}")
