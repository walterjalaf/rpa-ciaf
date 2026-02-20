"""
Handler para campos <input type="date"> nativos de HTML.

Por qué existe: Algunas plataformas usan el selector de fecha nativo del
navegador. Este handler localiza el campo mediante un image template PNG
y pega la fecha con paste_text(), que es más fiable que typewrite para
caracteres especiales y más rápido que tipo tecla a tecla.

Diferencia vs v1.2 (Playwright): antes se usaba page.fill(selector, valor).
Ahora se usa wait_for_image(template) para localizar el campo visualmente
y paste_text() para ingresar la fecha.

Limitación conocida: Si la plataforma cambia el diseño del campo de fecha,
el template PNG debe re-capturarse con el Macro Recorder.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

from core.exceptions import ImageNotFoundError
from core.pyauto_executor import PyAutoExecutor
from date_handlers.base_handler import BaseDateHandler
from date_handlers.exceptions import DateSelectorNotFoundError

logger = logging.getLogger(__name__)


class InputDateHandler(BaseDateHandler):
    """
    Ingresa fechas en campos <input type="date"> nativos usando image templates.

    Por qué existe: Es el handler más simple y confiable. Cuando una
    plataforma usa inputs nativos, solo se necesita localizar el campo
    visualmente (image template) y pegar la fecha.

    El triple_click() antes del paste garantiza que cualquier valor previo
    en el campo quede seleccionado y sea reemplazado por la nueva fecha.

    Uso:
        handler = InputDateHandler(
            field_template_from=Path("tasks/galicia/images/date_from.png"),
            field_template_to=Path("tasks/galicia/images/date_to.png"),
        )
        handler.set_dates(executor, date(2026, 2, 1), date(2026, 2, 17))
    """

    def __init__(
        self, field_template_from: Path, field_template_to: Path
    ) -> None:
        """
        Args:
            field_template_from: Path al PNG template del campo de fecha inicio.
            field_template_to: Path al PNG template del campo de fecha fin.
        """
        super().__init__()
        self._template_from = field_template_from
        self._template_to = field_template_to

    def set_dates(
        self, executor: PyAutoExecutor, date_from: date, date_to: date
    ) -> None:
        """
        Localiza los campos de fecha por image template y pega las fechas.

        Secuencia por cada campo:
          1. wait_for_image(template, timeout=10) → (x, y)
          2. triple_click(x, y) para seleccionar el texto existente
          3. paste_text(fecha en formato YYYY-MM-DD)

        Args:
            executor: Instancia de PyAutoExecutor con Chrome en foco.
            date_from: Fecha de inicio del período.
            date_to: Fecha de fin del período.

        Raises:
            DateSelectorNotFoundError: Si alguno de los templates no aparece
                en pantalla en 10 segundos.
        """
        formatted_from = date_from.strftime("%Y-%m-%d")
        formatted_to = date_to.strftime("%Y-%m-%d")

        for template, value, label in [
            (self._template_from, formatted_from, "fecha inicio"),
            (self._template_to, formatted_to, "fecha fin"),
        ]:
            try:
                x, y = executor.wait_for_image(template, timeout=10)
            except ImageNotFoundError:
                raise DateSelectorNotFoundError(
                    f"No se encontró el campo de {label} usando el template "
                    f"'{template.name}'. Es posible que la plataforma haya "
                    f"cambiado su interfaz. El técnico debe re-capturar el "
                    f"template con el Macro Recorder."
                )
            executor.triple_click(x, y)
            executor.paste_text(value)
            logger.info(f"Fecha {label} configurada: {value}")
