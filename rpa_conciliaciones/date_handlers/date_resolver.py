"""
Resuelve modos de período ('yesterday', 'last_week', etc.) a fechas concretas.

Por qué existe separado de los handlers: Los handlers saben CÓMO ingresar
una fecha en un navegador (llenar un input, navegar un datepicker, etc.).
El DateResolver sabe CUÁNDO: convierte un modo legible ("ayer", "semana pasada")
a un par (date_from, date_to) concreto.

Esta separación permite que:
- El técnico grabe el bot UNA vez definiendo solo el date_handler_type
- El contador elija el período en la UI sin tocar el bot
- El DateResolver calcule las fechas reales al momento de ejecutar

Uso:
    from date_handlers.date_resolver import DateResolver
    date_from, date_to = DateResolver.resolve('last_week')
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta

from date_handlers.exceptions import UnknownDateModeError

VALID_MODES = [
    "yesterday",
    "current_week",
    "last_week",
    "current_month",
    "last_month",
    "custom",
]


class DateResolver:
    """
    Calcula (date_from, date_to) a partir de un modo de período.

    Por qué existe: Desacopla la decisión de "qué período descargar" de
    la mecánica de "cómo ingresar la fecha en la web". El runner llama
    a resolve() antes de ejecutar cada tarea, y pasa las fechas concretas
    al handler correspondiente.

    Modos válidos: 'yesterday', 'current_week', 'last_week',
                   'current_month', 'last_month', 'custom'
    """

    @classmethod
    def resolve(
        cls,
        mode: str,
        custom_from: date | None = None,
        custom_to: date | None = None,
    ) -> tuple[date, date]:
        """
        Resuelve un modo de período a un par de fechas concretas.

        Args:
            mode: Uno de los modos válidos (ver VALID_MODES).
            custom_from: Fecha inicio para modo 'custom'. Ignorada en otros modos.
            custom_to: Fecha fin para modo 'custom'. Ignorada en otros modos.

        Returns:
            Tupla (date_from, date_to) con las fechas calculadas.

        Raises:
            UnknownDateModeError: Si el modo no está en VALID_MODES.
            ValueError: Si modo es 'custom' y falta custom_from o custom_to.
        """
        today = date.today()

        if mode == "yesterday":
            yesterday = today - timedelta(days=1)
            return (yesterday, yesterday)

        if mode == "current_week":
            # Lunes de esta semana (ISO: lunes=0)
            monday = today - timedelta(days=today.weekday())
            return (monday, today)

        if mode == "last_week":
            # Lunes de la semana anterior
            monday_this_week = today - timedelta(days=today.weekday())
            monday_last_week = monday_this_week - timedelta(weeks=1)
            sunday_last_week = monday_last_week + timedelta(days=6)
            return (monday_last_week, sunday_last_week)

        if mode == "current_month":
            first_day = today.replace(day=1)
            return (first_day, today)

        if mode == "last_month":
            first_day_this_month = today.replace(day=1)
            last_day_prev_month = first_day_this_month - timedelta(days=1)
            first_day_prev_month = last_day_prev_month.replace(day=1)
            return (first_day_prev_month, last_day_prev_month)

        if mode == "custom":
            if custom_from is None or custom_to is None:
                raise ValueError(
                    "El modo 'custom' requiere custom_from y custom_to. "
                    "Ambas fechas deben estar definidas."
                )
            return (custom_from, custom_to)

        raise UnknownDateModeError(
            f"Modo de fecha '{mode}' no reconocido. "
            f"Modos válidos: {', '.join(VALID_MODES)}"
        )


if __name__ == "__main__":
    print("=== Prueba de DateResolver ===")
    for mode in VALID_MODES:
        if mode == "custom":
            result = DateResolver.resolve(
                "custom",
                custom_from=date(2026, 1, 1),
                custom_to=date(2026, 1, 31),
            )
        else:
            result = DateResolver.resolve(mode)
        print(f"  {mode:15s} -> from={result[0]}  to={result[1]}")
    print("=== Fin ===")
