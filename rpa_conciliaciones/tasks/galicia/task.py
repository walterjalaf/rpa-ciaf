"""
Bot de descarga de extracto de Banco Galicia.

Por qué existe: Automatiza la descarga del extracto desde el homebanking
de Banco Galicia. El contador ya no necesita entrar manualmente al portal,
navegar al módulo de extractos y exportar el archivo.

Plataforma: Banco Galicia Online Banking
Tipo de descarga: directa (Chrome descarga el archivo automáticamente)
Tipo de fecha: no_filter (el portal no permite filtrar por fecha en la
descarga; se descarga todo y pandas filtra las filas después)

Diferencia vs v1.2 (Playwright): navigate() y trigger_download() usan
PyAutoExecutor con image templates en lugar de selectores CSS.

IMPORTANTE: Los templates PNG en la carpeta images/ son placeholders.
DEBEN capturarse con el Macro Recorder antes de usar en producción.
El portal de Galicia puede requerir navegación a través de iframes o
menús dinámicos — documentar cada paso al grabar.
"""

from __future__ import annotations

import logging
from pathlib import Path

from tasks.base_task import BaseTask

logger = logging.getLogger(__name__)

# Carpeta de templates de imagen para esta plataforma
_IMAGES_DIR = Path(__file__).resolve().parent / "images"


class GaliciaTask(BaseTask):
    """
    Tarea de descarga de extracto de Banco Galicia.

    Por qué existe: Banco Galicia es una de las dos plataformas piloto
    del proyecto. Su portal no permite filtrar por fecha al exportar,
    por lo que se usa date_handler_type='no_filter' y pandas filtra
    las filas por fecha antes de subir al servidor.

    Uso:
        task = GaliciaTask()
        filepath = task.run(date_from, date_to)
    """

    task_id = "galicia_movimientos"
    task_name = "Banco Galicia — Extracto"
    platform_url = "https://www.bancogalicia.com/personas/home.html"
    date_handler_type = "no_filter"
    date_mode = "last_month"
    date_handler_kwargs = {}
    session_check_url = "https://www.bancogalicia.com/personas/home.html"
    session_indicator_image = "galicia_session_ok.png"

    def navigate(self, executor) -> None:
        """
        Navega al módulo de extractos del homebanking de Galicia.

        TODO: Verificar y reemplazar templates de imagen al grabar con
        Macro Recorder. El portal de Galicia usa menús dinámicos —
        documentar cada clic al grabar la sesión completa de navegación.
        El template galicia_dashboard_loaded.png debe capturarse con el
        homebanking visible y sesión activa.
        """
        logger.info("Navegando a Banco Galicia...")
        # TODO: Reemplazar template con captura real del Macro Recorder.
        # El portal puede requerir múltiples clics para llegar al módulo de extractos.
        template = _IMAGES_DIR / "galicia_dashboard_loaded.png"
        executor.wait_for_image(template, timeout=15)
        logger.debug("Dashboard de Banco Galicia detectado")

    def trigger_download(self, executor) -> None:
        """
        Hace clic en el botón de exportación del extracto.

        TODO: Verificar y reemplazar template de imagen al grabar con
        Macro Recorder. El template galicia_download_button.png debe
        capturarse con el botón de exportación visible en pantalla.
        Confirmar si el botón abre un submenú (Excel / CSV) y agregar
        un segundo clic si es necesario.
        """
        logger.info("Iniciando descarga de extracto de Banco Galicia...")
        # TODO: Reemplazar template con captura real del Macro Recorder.
        template = _IMAGES_DIR / "galicia_download_button.png"
        x, y = executor.wait_for_image(template, timeout=10)
        executor.click(x, y)
        logger.debug("Clic en botón de descarga de Banco Galicia")
