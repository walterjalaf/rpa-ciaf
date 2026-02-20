"""
Abstraccion del navegador Chrome usando Playwright con perfil persistente.

Por que existe: Los bots necesitan acceder a las sesiones bancarias reales
del usuario. Playwright no puede usar el directorio User Data por defecto
de Chrome (Chrome bloquea DevTools remote debugging en ese directorio).

Solucion: Se crea un perfil RPA separado en ~/.rpa_conciliaciones/chrome_profile
y se copian las cookies y sesiones del perfil real de Chrome antes de lanzar.
Asi el bot tiene acceso a las sesiones bancarias sin conflicto con Chrome.

Decisiones clave:
    - headless=False: El contador ve el navegador mientras el bot opera.
    - channel="chrome": Usa el Chrome instalado en el sistema.
    - Perfil RPA separado: Evita el error "DevTools remote debugging
      requires a non-default data directory".
    - Sync de sesiones: Copia Cookies, Login Data y Local State del
      perfil real antes de cada ejecucion.

Uso:
    manager = BrowserManager()
    manager.launch()
    page = manager.new_page()
    page.goto("https://www.mercadopago.com.ar")
    # ... operaciones del bot ...
    manager.close()
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path

from playwright.sync_api import BrowserContext, Page, sync_playwright

from config.settings import DOWNLOAD_TIMEOUT_SECONDS
from core.exceptions import BrowserNotFoundError

logger = logging.getLogger(__name__)

# ── Stealth: args que ocultan indicadores de automatizacion ────
_STEALTH_ARGS = [
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-blink-features=AutomationControlled",
    "--disable-features=AutomationControlled",
    "--disable-automation",
]

# Script JS inyectado en cada pagina para ocultar huellas de Playwright.
# Los sistemas antifraude bancarios verifican estas propiedades.
_STEALTH_INIT_SCRIPT = """
// Ocultar navigator.webdriver (principal flag de deteccion)
Object.defineProperty(navigator, 'webdriver', {
    get: () => undefined,
});

// Restaurar navigator.plugins (Playwright los vacia)
Object.defineProperty(navigator, 'plugins', {
    get: () => [1, 2, 3, 4, 5],
});

// Restaurar navigator.languages
Object.defineProperty(navigator, 'languages', {
    get: () => ['es-AR', 'es', 'en-US', 'en'],
});

// Ocultar la propiedad chrome.runtime que Playwright modifica
if (!window.chrome) {
    window.chrome = {};
}
if (!window.chrome.runtime) {
    window.chrome.runtime = {};
}

// Prevenir deteccion por permisos de Notification
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) =>
    parameters.name === 'notifications'
        ? Promise.resolve({ state: Notification.permission })
        : originalQuery(parameters);
"""

# Archivos de sesion a copiar del perfil real de Chrome
_SESSION_FILES = [
    "Cookies",
    "Cookies-journal",
    "Login Data",
    "Login Data-journal",
    "Web Data",
    "Web Data-journal",
]

# Archivos a nivel de User Data (no dentro de Default/)
_ROOT_SESSION_FILES = [
    "Local State",
]


def _detect_chrome_profile_path() -> Path:
    """
    Detecta automaticamente la ruta del perfil de Chrome en Windows.

    Returns:
        Path al directorio 'User Data' del perfil de Chrome.

    Raises:
        BrowserNotFoundError: Si la ruta no existe en el sistema.
    """
    home = os.path.expanduser("~")
    chrome_path = Path(home) / "AppData" / "Local" / "Google" / "Chrome" / "User Data"

    if not chrome_path.exists():
        raise BrowserNotFoundError(
            f"No se encontro el perfil de Chrome en {chrome_path}. "
            f"Asegurate de tener Google Chrome instalado y haberlo abierto al menos una vez."
        )

    return chrome_path


def _get_rpa_profile_path() -> Path:
    """Retorna la ruta del perfil RPA dedicado para Playwright."""
    home = os.path.expanduser("~")
    return Path(home) / ".rpa_conciliaciones" / "chrome_profile"


def _sync_sessions_to_rpa_profile(chrome_user_data: Path, rpa_profile: Path) -> None:
    """
    Copia cookies y sesiones del perfil real de Chrome al perfil RPA.

    Esto permite que el bot tenga acceso a las sesiones bancarias
    sin usar el directorio por defecto de Chrome (que bloquea DevTools).
    """
    chrome_default = chrome_user_data / "Default"
    rpa_default = rpa_profile / "Default"
    rpa_default.mkdir(parents=True, exist_ok=True)

    # Copiar archivos de sesion desde Default/
    for filename in _SESSION_FILES:
        src = chrome_default / filename
        if src.exists():
            try:
                shutil.copy2(src, rpa_default / filename)
            except Exception as e:
                logger.debug(f"No se pudo copiar {filename}: {e}")

    # Copiar archivos a nivel raiz (Local State)
    for filename in _ROOT_SESSION_FILES:
        src = chrome_user_data / filename
        if src.exists():
            try:
                shutil.copy2(src, rpa_profile / filename)
            except Exception as e:
                logger.debug(f"No se pudo copiar {filename}: {e}")

    logger.info("Sesiones de Chrome sincronizadas al perfil RPA")


def _detect_downloads_path() -> Path:
    """Retorna la carpeta Downloads del usuario."""
    home = os.path.expanduser("~")
    return Path(home) / "Downloads"


def _is_chrome_running() -> bool:
    """Detecta si Chrome esta corriendo usando tasklist de Windows."""
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq chrome.exe", "/NH"],
            capture_output=True, text=True, timeout=5,
        )
        return "chrome.exe" in result.stdout.lower()
    except Exception:
        return False


class BrowserManager:
    """
    Administra el ciclo de vida del navegador Chrome con perfil persistente.

    Por que existe: El sistema RPA necesita reutilizar las sesiones bancarias
    que el contador ya tiene activas en su Chrome. Usa un perfil RPA separado
    con las sesiones copiadas del perfil real para evitar conflictos.

    Uso:
        manager = BrowserManager()
        manager.launch()
        page = manager.new_page()
        # ... usar page ...
        manager.close()
    """

    def __init__(self) -> None:
        self._playwright = None
        self._context: BrowserContext | None = None

    def launch(self) -> None:
        """
        Inicia el contexto persistente del navegador Chrome.

        Copia las sesiones del perfil real de Chrome a un perfil RPA
        dedicado y lanza Chrome con ese perfil.

        Raises:
            BrowserNotFoundError: Si Chrome no esta instalado o el perfil
                no existe en la ruta esperada.
        """
        if _is_chrome_running():
            raise BrowserNotFoundError(
                "Google Chrome esta abierto. Cerra todas las ventanas de Chrome "
                "(incluyendo la bandeja del sistema) y volve a intentar. "
                "El bot necesita acceso exclusivo al perfil de Chrome."
            )

        chrome_user_data = _detect_chrome_profile_path()
        rpa_profile = _get_rpa_profile_path()
        downloads_path = _detect_downloads_path()

        # Sincronizar sesiones del perfil real al perfil RPA
        _sync_sessions_to_rpa_profile(chrome_user_data, rpa_profile)

        logger.info(f"Lanzando Chrome con perfil RPA: {rpa_profile}")

        self._playwright = sync_playwright().start()
        try:
            self._context = self._playwright.chromium.launch_persistent_context(
                user_data_dir=str(rpa_profile),
                channel="chrome",
                headless=False,
                args=_STEALTH_ARGS,
                ignore_default_args=["--enable-automation"],
                downloads_path=str(downloads_path),
                timeout=30_000,
            )
        except Exception as e:
            self._playwright.stop()
            self._playwright = None
            error_msg = str(e)
            if "Target page, context or browser has been closed" in error_msg:
                raise BrowserNotFoundError(
                    "No se pudo abrir Chrome. Verifica que Chrome este "
                    "completamente cerrado y volve a intentar."
                ) from e
            raise

        # Inyectar script stealth en todas las paginas (actuales y futuras)
        self._context.add_init_script(_STEALTH_INIT_SCRIPT)

        logger.info("Chrome iniciado en modo stealth con perfil RPA")

    def new_page(self) -> Page:
        """
        Abre una nueva pestana en el navegador.

        Returns:
            Instancia de Page de Playwright para operar.

        Raises:
            RuntimeError: Si se llama antes de launch().
        """
        if self._context is None:
            raise RuntimeError(
                "BrowserManager.launch() debe llamarse antes de new_page(). "
                "El navegador no fue iniciado."
            )

        page = self._context.new_page()
        logger.debug("Nueva pestana abierta")
        return page

    def close(self) -> None:
        """
        Cierra el contexto del navegador y libera recursos de Playwright.

        Cierra solo las pestanas que abrio el bot, no las del usuario.
        """
        if self._context is not None:
            try:
                self._context.close()
            except Exception as e:
                logger.warning(f"Error al cerrar el contexto del navegador: {e}")
            self._context = None

        if self._playwright is not None:
            try:
                self._playwright.stop()
            except Exception as e:
                logger.warning(f"Error al detener Playwright: {e}")
            self._playwright = None

        logger.info("Navegador cerrado")


if __name__ == "__main__":
    print("=== Prueba basica de BrowserManager ===")
    manager = BrowserManager()
    try:
        manager.launch()
        page = manager.new_page()
        page.goto("https://www.google.com")
        print(f"Titulo de la pagina: {page.title()}")
    finally:
        manager.close()
    print("=== Prueba completada ===")
