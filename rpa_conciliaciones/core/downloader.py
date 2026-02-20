"""
Detecta y captura archivos descargados por Chrome durante la ejecución de bots.

Por qué existe: Cuando PyAutoGUI hace clic en un botón de descarga, Chrome
guarda el archivo en la carpeta Downloads del usuario. El sistema no sabe de
antemano el nombre exacto del archivo porque muchas plataformas lo generan
con timestamp o hash. Este módulo monitorea la carpeta Downloads y detecta
archivos nuevos con la extensión correcta.

Estrategia de detección:
    1. Tomar snapshot de archivos existentes ANTES de que el bot haga clic
    2. Polling cada 500ms buscando archivos nuevos
    3. Ignorar .crdownload (descarga parcial de Chrome)
    4. Verificar que el archivo tenga tamaño > 0 y no esté siendo escrito
    5. Timeout configurable (default 60s) para evitar loops infinitos

Uso:
    watcher = DownloadWatcher()
    watcher.take_snapshot()
    # ... bot hace clic en descargar ...
    filepath = watcher.wait_for_download()
    final_path = watcher.cleanup(filepath)
"""

from __future__ import annotations

import logging
import shutil
import time
from pathlib import Path

from config.settings import DOWNLOAD_TIMEOUT_SECONDS
from core.exceptions import DownloadTimeoutError

logger = logging.getLogger(__name__)

DEFAULT_EXTENSIONS = [".xlsx", ".csv"]
POLL_INTERVAL_SECONDS = 0.5
FILE_STABLE_SECONDS = 0.5


class DownloadWatcher:
    """
    Monitorea la carpeta Downloads y detecta archivos nuevos descargados.

    Por qué existe: El nombre del archivo descargado no es predecible.
    Plataformas como Mercado Pago generan nombres con timestamp, Galicia
    usa nombres genéricos. Este watcher detecta cualquier archivo nuevo
    con extensión válida sin importar su nombre.

    Uso:
        watcher = DownloadWatcher()
        watcher.take_snapshot()
        # ... trigger_download() del bot ...
        filepath = watcher.wait_for_download()
    """

    def __init__(self, timeout_seconds: int | None = None) -> None:
        """
        Args:
            timeout_seconds: Segundos máximos de espera. Si None, usa
                DOWNLOAD_TIMEOUT_SECONDS de config/settings.py.
        """
        self._timeout = timeout_seconds or DOWNLOAD_TIMEOUT_SECONDS
        self._downloads_dir = Path.home() / "Downloads"
        self._snapshot: set[Path] = set()

    def take_snapshot(self, extensions: list[str] | None = None) -> None:
        """
        Registra los archivos existentes en Downloads antes de la descarga.

        Debe llamarse ANTES de que el bot haga clic en descargar.
        Así wait_for_download() puede distinguir archivos nuevos de existentes.

        Args:
            extensions: Extensiones a monitorear. Default: ['.xlsx', '.csv'].
        """
        exts = extensions or DEFAULT_EXTENSIONS
        self._snapshot = self._scan_files(exts)
        logger.info(
            f"Snapshot tomado: {len(self._snapshot)} archivos existentes en "
            f"{self._downloads_dir}"
        )

    def wait_for_download(self, extensions: list[str] | None = None) -> Path:
        """
        Espera a que aparezca un archivo nuevo en Downloads.

        Hace polling cada 500ms buscando archivos que:
        - No estaban en el snapshot previo
        - Tienen extensión válida (.xlsx o .csv, sin .xls)
        - Tienen tamaño > 0 bytes
        - No fueron modificados en los últimos 500ms (escritura terminada)

        Args:
            extensions: Extensiones válidas. Default: ['.xlsx', '.csv'].

        Returns:
            Path del archivo descargado.

        Raises:
            DownloadTimeoutError: Si no se detecta un archivo nuevo dentro
                del timeout configurado.
        """
        exts = extensions or DEFAULT_EXTENSIONS
        logger.info(
            f"Esperando descarga en {self._downloads_dir} "
            f"(extensiones: {exts}, timeout: {self._timeout}s)..."
        )

        deadline = time.monotonic() + self._timeout

        while time.monotonic() < deadline:
            current_files = self._scan_files(exts)
            new_files = current_files - self._snapshot

            for filepath in new_files:
                if self._is_file_ready(filepath):
                    size_bytes = filepath.stat().st_size
                    logger.info(
                        f"Archivo detectado: {filepath.name} ({size_bytes} bytes)"
                    )
                    return filepath

            time.sleep(POLL_INTERVAL_SECONDS)

        logger.error(
            f"Timeout: no se detecto archivo nuevo en {self._timeout} segundos"
        )
        raise DownloadTimeoutError(
            f"El archivo no se descargo en {self._timeout} segundos. "
            f"La plataforma puede haber enviado el archivo por email "
            f"o el boton de descarga no funciono."
        )

    def cleanup(self, filepath: Path, dest_folder: Path | None = None) -> Path:
        """
        Mueve el archivo descargado a una carpeta de trabajo.

        Args:
            filepath: Path del archivo en Downloads.
            dest_folder: Carpeta destino. Si None, usa rpa_conciliaciones/temp/.

        Returns:
            Path del archivo en su ubicación final.
        """
        if dest_folder is None:
            dest_folder = Path(__file__).resolve().parent.parent / "temp"

        dest_folder.mkdir(parents=True, exist_ok=True)
        destination = dest_folder / filepath.name

        # Si ya existe un archivo con el mismo nombre, agregar sufijo
        if destination.exists():
            stem = filepath.stem
            suffix = filepath.suffix
            counter = 1
            while destination.exists():
                destination = dest_folder / f"{stem}_{counter}{suffix}"
                counter += 1

        shutil.move(str(filepath), str(destination))
        logger.info(f"Archivo movido a: {destination}")
        return destination

    def _scan_files(self, extensions: list[str]) -> set[Path]:
        """Retorna set de archivos en Downloads con las extensiones dadas."""
        files: set[Path] = set()
        for ext in extensions:
            files.update(self._downloads_dir.glob(f"*{ext}"))
        return files

    def _is_file_ready(self, filepath: Path) -> bool:
        """
        Verifica que el archivo esté completo (no en proceso de escritura).

        Condiciones:
        - Existe (no fue eliminado entre el scan y esta verificación)
        - Tamaño > 0 bytes
        - No fue modificado en los últimos 500ms (la escritura terminó)
        """
        try:
            if not filepath.exists():
                return False

            if filepath.stat().st_size == 0:
                return False

            last_modified = filepath.stat().st_mtime
            elapsed = time.time() - last_modified
            if elapsed < FILE_STABLE_SECONDS:
                return False

            return True
        except OSError:
            return False


if __name__ == "__main__":
    print("=== Prueba manual de DownloadWatcher ===")
    print("Descarga un archivo .xlsx o .csv en tu carpeta Downloads")
    print("dentro de los proximos 30 segundos.")
    print()

    watcher = DownloadWatcher(timeout_seconds=30)
    watcher.take_snapshot()

    try:
        filepath = watcher.wait_for_download()
        print(f"Archivo detectado: {filepath}")
        print(f"Tamanio: {filepath.stat().st_size} bytes")
    except DownloadTimeoutError as e:
        print(f"Timeout: {e}")

    print("=== Fin ===")
