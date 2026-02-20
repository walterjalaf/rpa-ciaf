"""
Cliente de auto-actualización del ejecutable .exe.

Por qué existe: Permite actualizar la app de escritorio sin intervención
del contador. Compara la versión local con la del servidor y descarga el
nuevo .exe si hay una versión más reciente.

Cuando USE_MOCK = True, siempre retorna que no hay actualizaciones disponibles.

Uso:
    updater = UpdaterClient()
    version_info = updater.check()
    if version_info:
        exe_path = updater.download(version_info, dest_folder)
"""

from __future__ import annotations

import logging
from pathlib import Path

import semver

from config import settings

logger = logging.getLogger(__name__)


class UpdaterClient:
    """
    Verifica y descarga actualizaciones del .exe desde el servidor.

    Por qué existe: El contador no va a reinstalar manualmente. Este módulo
    compara versiones semver y descarga el nuevo binario en background para
    que la UI muestre un aviso de "actualización disponible".

    Uso:
        updater = UpdaterClient()
        info = updater.check()  # None si no hay update
        if info:
            path = updater.download(info, Path("./updates"))
    """

    def check(self) -> dict | None:
        """
        Consulta si hay una versión más nueva del .exe disponible.

        Returns:
            Dict con version_info si hay update, None si estamos al día.
            El dict contiene: latest_version, download_url, release_notes.
        """
        if settings.USE_MOCK:
            logger.info(
                "Modo mock: no hay actualizaciones (versión actual: %s)",
                settings.APP_VERSION
            )
            return None

        return self._check_real()

    def download(self, version_info: dict, dest_folder: Path) -> Path:
        """
        Descarga el nuevo .exe desde el servidor.

        Args:
            version_info: Dict retornado por check() con download_url.
            dest_folder: Carpeta donde guardar el .exe descargado.

        Returns:
            Path al archivo .exe descargado.
        """
        if settings.USE_MOCK:
            logger.info("Modo mock: descarga de actualización simulada")
            return dest_folder / f"rpa_conciliaciones_{version_info['latest_version']}.exe"

        return self._download_real(version_info, dest_folder)

    def _check_real(self) -> dict | None:
        """Consulta GET /rpa/version y compara con APP_VERSION."""
        try:
            import httpx
            client = httpx.Client(
                base_url=settings.SERVER_URL,
                timeout=settings.HTTP_TIMEOUT_SECONDS,
            )
            response = client.get("/rpa/version")
            response.raise_for_status()
            info = response.json()

            local = semver.Version.parse(settings.APP_VERSION)
            remote = semver.Version.parse(info["latest_version"])

            if remote > local:
                logger.info(
                    "Actualización disponible: %s → %s",
                    settings.APP_VERSION, info["latest_version"]
                )
                return info

            logger.info("App al día (versión %s)", settings.APP_VERSION)
            return None
        except Exception as e:
            logger.warning(
                "No se pudo verificar actualizaciones: %s", e
            )
            return None

    def _download_real(self, version_info: dict,
                       dest_folder: Path) -> Path:
        """Descarga el .exe desde GET /rpa/download/{version}."""
        import httpx

        dest_folder.mkdir(parents=True, exist_ok=True)
        version = version_info["latest_version"]
        dest_path = dest_folder / f"rpa_conciliaciones_{version}.exe"

        try:
            client = httpx.Client(
                base_url=settings.SERVER_URL,
                timeout=300,  # 5 min para descarga de binario
            )
            url = f"/rpa/download/{version}"
            logger.info("Descargando actualización desde %s", url)

            with client.stream("GET", url) as response:
                response.raise_for_status()
                with open(dest_path, "wb") as f:
                    for chunk in response.iter_bytes(chunk_size=8192):
                        f.write(chunk)

            logger.info(
                "Actualización descargada: %s (%.1f MB)",
                dest_path, dest_path.stat().st_size / (1024 * 1024)
            )
            return dest_path
        except Exception as e:
            logger.error("Error descargando actualización: %s", e)
            raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    updater = UpdaterClient()
    result = updater.check()
    print(f"Actualización disponible: {result}")
