"""
Clase abstracta para handlers de selector de fecha.

Por qué existe: Cada plataforma financiera tiene su propio mecanismo para
configurar el rango de fechas de exportación. Hay tres tipos:

1. input_date: Campo <input type="date"> nativo de HTML.
   El handler localiza el campo con un image template y usa paste_text()
   para pegar la fecha en formato YYYY-MM-DD.

2. datepicker_js: Calendario JavaScript custom (date range picker).
   El handler usa wait_for_image() para esperar que aparezca el calendario
   y find_image() para localizar las flechas de navegación por mes.

3. no_filter: La plataforma no tiene selector de fecha. Descarga todo el
   período disponible. Pandas filtra las filas por fecha después de descargar.

Cada handler hereda de BaseDateHandler e implementa set_dates().
El factory.py instancia el handler correcto según date_handler_type del schema.json.

NOTA v1.3: set_dates() recibe PyAutoExecutor, NO Page de Playwright.
Playwright fue removido del proyecto en v1.3.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.pyauto_executor import PyAutoExecutor


class BaseDateHandler(ABC):
    """
    Interfaz base para todos los handlers de fecha.

    Por qué existe: Define el contrato que todos los handlers deben cumplir.
    El runner y el BaseTask llaman a set_dates() sin saber qué tipo de
    selector tiene la plataforma — el polimorfismo resuelve eso.

    Atributos:
        context: Diccionario para pasar datos entre el handler y otros módulos.
                 Usado por NoDateFilterHandler para comunicar las fechas al
                 uploader, que las usa para filtrar filas con pandas.
    """

    def __init__(self) -> None:
        self.context: dict = {}

    @abstractmethod
    def set_dates(
        self, executor: PyAutoExecutor, date_from: date, date_to: date
    ) -> None:
        """
        Configura el rango de fechas en la plataforma.

        Args:
            executor: Instancia de PyAutoExecutor. NO es una Page de Playwright.
                      Versión 1.3+: Playwright fue removido del proyecto.
            date_from: Fecha de inicio del período.
            date_to: Fecha de fin del período.

        Raises:
            DateSelectorNotFoundError: Si el template del campo de fecha no
                aparece en pantalla dentro del timeout.
            DatepickerNavigationError: Si no se puede navegar al mes/día
                correcto en un calendario JavaScript.
        """
