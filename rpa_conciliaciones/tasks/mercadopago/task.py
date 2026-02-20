"""
Bot de descarga de movimientos de Mercado Pago.

Por qué existe: Automatiza la descarga del reporte de movimientos desde
el portal de Mercado Pago Argentina. El contador ya no necesita entrar
manualmente a la plataforma, seleccionar fechas y exportar el Excel.

Plataforma: Mercado Pago Argentina (www.mercadopago.com.ar)
Tipo de descarga: directa (Chrome descarga el archivo automáticamente)
Tipo de fecha: datepicker_js (calendario JavaScript custom)

Diferencia vs v1.2 (Playwright): navigate() y trigger_download() usan
PyAutoExecutor con image templates en lugar de selectores CSS.

IMPORTANTE: Los templates PNG en la carpeta images/ son placeholders.
DEBEN capturarse con el Macro Recorder antes de usar en producción.
"""

from __future__ import annotations

import logging
from pathlib import Path

from tasks.base_task import BaseTask

logger = logging.getLogger(__name__)

# Carpeta de templates de imagen para esta plataforma
_IMAGES_DIR = Path(__file__).resolve().parent / "images"


class MercadoPagoTask(BaseTask):
    """
    Tarea de descarga de movimientos de Mercado Pago.

    Por qué existe: Mercado Pago es una de las dos plataformas piloto
    del proyecto. Su portal usa un datepicker JavaScript custom para
    seleccionar el rango de fechas antes de exportar.

    Uso:
        task = MercadoPagoTask()
        filepath = task.run(date_from, date_to)
    """

    task_id = "mercadopago_movimientos"
    task_name = "Mercado Pago — Movimientos"
    platform_url = "https://www.mercadopago.com.ar/activities"
    date_handler_type = "datepicker_js"
    date_mode = "yesterday"
    date_handler_kwargs = {
        # TODO: Capturar templates con Macro Recorder y actualizar rutas.
        "open_template": str(_IMAGES_DIR / "mp_datepicker_open.png"),
        "prev_arrow_template": str(_IMAGES_DIR / "mp_datepicker_prev.png"),
        "next_arrow_template": str(_IMAGES_DIR / "mp_datepicker_next.png"),
        "images_dir": str(_IMAGES_DIR),
    }
    session_check_url = "https://www.mercadopago.com.ar/home"
    session_indicator_image = "mercadopago_session_ok.png"

    def navigate(self, executor) -> None:
        """
        Espera que el dashboard de Mercado Pago cargue en Chrome.

        TODO: Verificar y reemplazar templates de imagen al grabar con
        Macro Recorder. El template mp_dashboard_loaded.png debe capturarse
        con el dashboard visible y sesión activa.
        """
        logger.info("Navegando a Mercado Pago...")
        # TODO: Reemplazar template con captura real del Macro Recorder.
        template = _IMAGES_DIR / "mp_dashboard_loaded.png"
        executor.wait_for_image(template, timeout=15)
        logger.debug("Dashboard de Mercado Pago detectado")

    def trigger_download(self, executor) -> None:
        """
        Hace clic en el botón de exportación de movimientos.

        TODO: Verificar y reemplazar template de imagen al grabar con
        Macro Recorder. El template mp_download_button.png debe capturarse
        con el botón de exportación visible en la pantalla.
        """
        logger.info("Iniciando descarga de movimientos de Mercado Pago...")
        # TODO: Reemplazar template con captura real del Macro Recorder.
        template = _IMAGES_DIR / "mp_download_button.png"
        x, y = executor.wait_for_image(template, timeout=10)
        executor.click(x, y)
        logger.debug("Clic en botón de descarga de Mercado Pago")
