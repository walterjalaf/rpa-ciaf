"""
Lanzador de Chrome mediante subprocess.

Por qué existe: Encapsula la apertura y cierre de Chrome como proceso del OS,
manteniendo este módulo completamente separado de PyAutoGUI. ChromeLauncher
no sabe nada de automatización visual; solo sabe abrir y cerrar un proceso.

Limitaciones conocidas:
- time.sleep(2) tras launch es el único sleep fijo del proyecto (espera arranque de OS)
- El proceso Chrome hereda el perfil de usuario activo. Si hay una ventana previa de
  Chrome abierta, Chrome puede ignorar la URL y abrir una pestaña en la ventana existente.
- En equipos con DPI != 100% puede ser necesario configurar CHROME_EXECUTABLE_PATH
  manualmente en settings.py si la autodetección no lo ubica.

Uso:
    launcher = ChromeLauncher()
    launcher.launch("https://www.mercadopago.com.ar/activities")
    # ... automatización con PyAutoExecutor ...
    launcher.close()
"""

import logging
import os
import subprocess
import tempfile
import time
from pathlib import Path

import pyautogui

from config import settings
from core.exceptions import ChromeNotFoundError

logger = logging.getLogger(__name__)

# Paths de instalación de Chrome más comunes en Windows.
# Se prueban en orden; el primero que existe se usa.
_CHROME_PATHS_WINDOWS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(
        r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"
    ),
]


def _find_chrome_executable() -> str:
    """
    Retorna la ruta al ejecutable de Chrome.

    Orden de búsqueda:
    1. settings.CHROME_EXECUTABLE_PATH si está definido
    2. Paths comunes de Windows (_CHROME_PATHS_WINDOWS)

    Raises:
        ChromeNotFoundError: si no se encuentra en ningún path.
    """
    if settings.CHROME_EXECUTABLE_PATH:
        path = settings.CHROME_EXECUTABLE_PATH
        if Path(path).is_file():
            return path
        raise ChromeNotFoundError(
            f"CHROME_EXECUTABLE_PATH está configurado pero el archivo no existe: {path}"
        )

    for candidate in _CHROME_PATHS_WINDOWS:
        if Path(candidate).is_file():
            logger.debug(f"Chrome encontrado en: {candidate}")
            return candidate

    raise ChromeNotFoundError(
        "Chrome no encontrado en los paths estándar de Windows. "
        "Configurá CHROME_EXECUTABLE_PATH en config/settings.py con la ruta correcta."
    )


class ChromeLauncher:
    """
    Abre Chrome apuntando a una URL, toma screenshots y lo cierra.

    Responsabilidad única: gestión del proceso Chrome (subprocess). No conoce
    PyAutoGUI ni la lógica de las tareas de automatización.

    Uso típico:
        launcher = ChromeLauncher()
        try:
            launcher.launch("https://www.mercadopago.com.ar/activities")
            # ... acciones con PyAutoExecutor ...
        finally:
            launcher.close()
    """

    def __init__(self) -> None:
        self._process: subprocess.Popen | None = None
        self._screenshot_dir = Path(tempfile.gettempdir()) / "rpa_screenshots"
        self._screenshot_dir.mkdir(exist_ok=True)

    def launch(self, url: str) -> None:
        """
        Abre Chrome navegando a la URL indicada.

        El método cierra cualquier proceso Chrome previo gestionado por esta instancia
        antes de abrir uno nuevo.

        Args:
            url: URL completa a la que Chrome debe navegar al abrirse.

        Raises:
            ChromeNotFoundError: si Chrome no está instalado o CHROME_EXECUTABLE_PATH
                apunta a un archivo inexistente.
        """
        if self._process is not None:
            logger.warning("ChromeLauncher.launch() llamado con un proceso activo. Cerrando el anterior.")
            self.close()

        chrome_exe = _find_chrome_executable()
        logger.info(f"Lanzando Chrome: {chrome_exe} → {url}")

        self._process = subprocess.Popen(
            [chrome_exe, url, "--start-maximized"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Único sleep fijo del proyecto: espera arranque del proceso del OS.
        # No hay evento DOM ni imagen que capturar; el proceso simplemente necesita tiempo.
        time.sleep(2)
        logger.info(f"Chrome lanzado (PID {self._process.pid})")

    def close(self) -> None:
        """
        Cierra Chrome de forma limpia.

        Intenta terminate() (SIGTERM) con timeout de 5 segundos. Si el proceso
        sigue activo, usa kill() (SIGKILL). Siempre limpia self._process.
        """
        if self._process is None:
            return

        pid = self._process.pid
        try:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
                logger.info(f"Chrome (PID {pid}) cerrado normalmente")
            except subprocess.TimeoutExpired:
                logger.warning(f"Chrome (PID {pid}) no respondió a terminate(), usando kill()")
                self._process.kill()
                self._process.wait()
                logger.info(f"Chrome (PID {pid}) forzado a cerrar con kill()")
        except Exception as e:
            logger.warning(f"Error al cerrar Chrome (PID {pid}): {e}")
        finally:
            self._process = None

    def take_screenshot(self, region: tuple | None = None) -> Path:
        """
        Captura la pantalla actual (o una región) y guarda el PNG en un tempdir.

        Args:
            region: Tupla (x, y, width, height) para capturar solo esa región.
                    None captura toda la pantalla.

        Returns:
            Path al archivo PNG guardado.
        """
        timestamp = int(time.time() * 1000)
        filepath = self._screenshot_dir / f"chrome_screenshot_{timestamp}.png"
        screenshot = pyautogui.screenshot(region=region)
        screenshot.save(str(filepath))
        logger.debug(f"Screenshot guardado en: {filepath}")
        return filepath
