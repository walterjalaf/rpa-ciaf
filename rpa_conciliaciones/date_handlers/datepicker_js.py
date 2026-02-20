"""
Handler para calendarios JavaScript custom (date range pickers).

Por qué existe: Muchas plataformas financieras usan calendarios JS propios
en lugar del input nativo del navegador. Estos calendarios requieren:
1. Hacer clic para abrir el picker (localizado por image template)
2. Navegar mes a mes con flechas (localizadas por image template)
3. Hacer clic en el día correcto (localizado por image template)

Diferencia vs v1.2 (Playwright): antes se usaba page.get_by_text() para
encontrar botones por texto visible. Ahora se usan image templates PNG
capturados con el Macro Recorder para localizar cada elemento.

Estrategia de navegación: el calendario se asume abierto en el mes actual
(date.today()) al hacer clic en open_template. La navegación calcula la
diferencia en meses entre la posición actual y el mes destino y hace clic
en la flecha correspondiente el número exacto de veces.

Limitaciones conocidas:
- Los templates de días (day_01.png ... day_31.png) deben capturarse por
  el técnico para cada plataforma, ya que la fuente y tamaño varían.
- Si el calendar no abre en el mes actual sino en otra fecha, la navegación
  fallará. En ese caso, el técnico debe verificar el comportamiento de la
  plataforma antes de grabar los templates.
- MAX_NAVIGATION_MONTHS limita la navegación a 24 meses (2 años). Tasas
  históricas más largas requieren un handler custom.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

from core.exceptions import ImageNotFoundError
from core.pyauto_executor import PyAutoExecutor
from date_handlers.base_handler import BaseDateHandler
from date_handlers.exceptions import DatepickerNavigationError, DateSelectorNotFoundError

logger = logging.getLogger(__name__)

# Nombres de meses en español — solo para logging legible
MESES_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]

MAX_NAVIGATION_MONTHS = 24


class DatepickerJSHandler(BaseDateHandler):
    """
    Navega calendarios JavaScript custom usando image templates.

    Por qué existe: Los datepickers JS son el tipo de selector más frágil
    en RPA. Este handler mitiga el riesgo usando image templates capturados
    por el técnico, que son robustos ante cambios de clases CSS pero frágiles
    ante rediseños visuales del portal.

    Convención de templates de días:
        images_dir/day_01.png, day_02.png, ..., day_31.png
        Cada template es una captura del número de día tal como aparece
        dentro del calendario de la plataforma específica.

    Uso:
        handler = DatepickerJSHandler(
            open_template=Path("tasks/mercadopago/images/datepicker_btn.png"),
            prev_arrow_template=Path("tasks/mercadopago/images/arrow_prev.png"),
            next_arrow_template=Path("tasks/mercadopago/images/arrow_next.png"),
            images_dir=Path("tasks/mercadopago/images/"),
        )
        handler.set_dates(executor, date(2026, 2, 1), date(2026, 2, 17))
    """

    def __init__(
        self,
        open_template: Path,
        prev_arrow_template: Path,
        next_arrow_template: Path,
        images_dir: Path,
    ) -> None:
        """
        Args:
            open_template: Template PNG del botón que abre el calendario.
            prev_arrow_template: Template PNG de la flecha "mes anterior".
            next_arrow_template: Template PNG de la flecha "mes siguiente".
            images_dir: Carpeta con templates de días (day_01.png ... day_31.png).
        """
        super().__init__()
        self._open_template = open_template
        self._prev_arrow_template = prev_arrow_template
        self._next_arrow_template = next_arrow_template
        self._images_dir = images_dir
        # Mes actualmente visible en el calendario (se actualiza al navegar)
        self._calendar_month: date | None = None

    def set_dates(
        self, executor: PyAutoExecutor, date_from: date, date_to: date
    ) -> None:
        """
        Abre el datepicker, navega al mes de date_from, selecciona el día,
        luego navega al mes de date_to y selecciona el día final.

        Args:
            executor: Instancia de PyAutoExecutor con Chrome en foco.
            date_from: Fecha de inicio del período.
            date_to: Fecha de fin del período.

        Raises:
            DateSelectorNotFoundError: Si el botón open_template no aparece.
            DatepickerNavigationError: Si no se puede navegar o seleccionar un día.
        """
        self._open_calendar(executor)

        self._navigate_to_month(executor, date_from)
        self._click_day(executor, date_from.day)
        # Tras seleccionar date_from, el calendario de rango permanece abierto
        # en el mes de date_from. Actualizamos el estado interno.
        self._calendar_month = date(date_from.year, date_from.month, 1)

        self._navigate_to_month(executor, date_to)
        self._click_day(executor, date_to.day)

        logger.info(f"Datepicker configurado: {date_from} → {date_to}")

    # ── Métodos privados ────────────────────────────────────────────────────

    def _open_calendar(self, executor: PyAutoExecutor) -> None:
        """Hace clic en el botón que abre el calendario y registra el mes inicial."""
        try:
            x, y = executor.wait_for_image(self._open_template, timeout=15)
        except ImageNotFoundError:
            raise DateSelectorNotFoundError(
                f"No se encontró el botón del datepicker "
                f"(template: '{self._open_template.name}'). "
                f"El técnico debe re-capturar el template con el Macro Recorder."
            )
        executor.click(x, y)
        today = date.today()
        # El calendario abre en el mes actual por defecto
        self._calendar_month = date(today.year, today.month, 1)
        logger.debug(
            f"Datepicker abierto. Mes inicial asumido: "
            f"{MESES_ES[today.month - 1]} {today.year}"
        )

    def _navigate_to_month(self, executor: PyAutoExecutor, target: date) -> None:
        """
        Navega el calendario hasta el mes del target.

        Calcula la diferencia en meses entre la posición actual del calendario
        (self._calendar_month) y el mes destino, y hace clic en la flecha
        correspondiente el número exacto de veces.

        Raises:
            DatepickerNavigationError: Si la diferencia supera MAX_NAVIGATION_MONTHS
                o si la flecha de navegación no aparece en pantalla.
        """
        if self._calendar_month is None:
            raise DatepickerNavigationError(
                "Estado interno inválido: mes del calendario no inicializado. "
                "Llamar a set_dates() en lugar de _navigate_to_month() directamente."
            )

        target_first = date(target.year, target.month, 1)
        current = self._calendar_month

        months_diff = (
            (target_first.year - current.year) * 12
            + (target_first.month - current.month)
        )

        if months_diff == 0:
            logger.debug(
                f"Calendario ya en {MESES_ES[target.month - 1]} {target.year}"
            )
            return

        clicks_needed = abs(months_diff)
        if clicks_needed > MAX_NAVIGATION_MONTHS:
            raise DatepickerNavigationError(
                f"La navegación requiere {clicks_needed} meses, pero el límite "
                f"es {MAX_NAVIGATION_MONTHS}. Verificar las fechas configuradas "
                f"en la tarea o usar un handler custom para rangos históricos extensos."
            )

        arrow_template = (
            self._next_arrow_template if months_diff > 0 else self._prev_arrow_template
        )
        direction = "siguiente" if months_diff > 0 else "anterior"

        for i in range(clicks_needed):
            pos = executor.find_image(arrow_template)
            if pos is None:
                raise DatepickerNavigationError(
                    f"No se encontró la flecha '{direction}' del calendario "
                    f"(template: '{arrow_template.name}') en el click {i + 1} "
                    f"de {clicks_needed}. El técnico debe re-capturar el template."
                )
            executor.click(*pos)

        self._calendar_month = target_first
        logger.debug(
            f"Calendario navegado a {MESES_ES[target.month - 1]} {target.year}"
        )

    def _click_day(self, executor: PyAutoExecutor, day: int) -> None:
        """
        Hace clic en el número del día dentro del calendario visible.

        Busca el template day_NN.png en images_dir. Si el template no existe,
        el técnico debe capturarlo. Si existe pero no aparece en pantalla, el
        calendario puede no estar en el mes esperado.

        Args:
            day: Número del día (1-31).

        Raises:
            DatepickerNavigationError: Si el template no existe o no aparece
                en la pantalla en este momento.
        """
        day_template = self._images_dir / f"day_{day:02d}.png"

        if not day_template.exists():
            raise DatepickerNavigationError(
                f"Template del día {day} no encontrado: '{day_template}'. "
                f"El técnico debe capturar los templates de días para esta "
                f"plataforma. Nombre esperado: 'day_{day:02d}.png' en '{self._images_dir}'."
            )

        pos = executor.find_image(day_template)
        if pos is None:
            raise DatepickerNavigationError(
                f"El día {day} no apareció en el calendario visible "
                f"(template: '{day_template.name}'). "
                f"El mes del calendario puede no coincidir con el esperado. "
                f"Verificar que la navegación de meses funciona correctamente."
            )

        executor.click(*pos)
        logger.debug(f"Día {day} seleccionado en el datepicker")
