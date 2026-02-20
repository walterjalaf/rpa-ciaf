"""
Handler para plataformas sin selector de fecha.

Por qué existe: Algunas plataformas no permiten filtrar por fecha en la
exportación — siempre descargan el período completo o el último mes.
En estos casos, el bot descarga todo y pandas filtra las filas por fecha
antes de subir al servidor.

Este handler no toca el navegador. Su única responsabilidad es guardar
las fechas en self.context para que el uploader sepa qué filas mantener.
"""

from __future__ import annotations

import logging
from datetime import date

from core.pyauto_executor import PyAutoExecutor
from date_handlers.base_handler import BaseDateHandler

logger = logging.getLogger(__name__)


class NoDateFilterHandler(BaseDateHandler):
    """
    No opera sobre el navegador. Pasa las fechas al uploader via context.

    Por qué existe: Cuando una plataforma no tiene selector de fecha,
    el archivo descargado contiene más datos de los necesarios. El uploader
    usa las fechas guardadas en self.context para filtrar filas con pandas
    antes de enviar al servidor.

    Uso:
        handler = NoDateFilterHandler()
        handler.set_dates(executor, date(2026, 2, 1), date(2026, 2, 17))
        # handler.context == {'date_from': date(2026, 2, 1), 'date_to': date(2026, 2, 17)}
    """

    def set_dates(
        self, executor: PyAutoExecutor, date_from: date, date_to: date
    ) -> None:
        """
        No interactúa con la pantalla. Guarda las fechas en el contexto.

        Args:
            executor: No se usa. Presente por contrato de BaseDateHandler.
            date_from: Fecha de inicio para filtrar filas después.
            date_to: Fecha de fin para filtrar filas después.
        """
        self.context["date_from"] = date_from
        self.context["date_to"] = date_to
        logger.info(
            f"NoDateFilter: fechas guardadas en contexto para filtro posterior "
            f"({date_from} → {date_to})"
        )
