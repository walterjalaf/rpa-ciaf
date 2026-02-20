"""
Factory de handlers de fecha.

Por qué existe: Desacopla la decisión de qué handler usar de la construcción
del handler. El runner o el BaseTask llama a get_handler() con el string
date_handler_type del schema.json y recibe la instancia correcta.

Tipos válidos (v1.3):
  'input_date'   → InputDateHandler (campo HTML nativo, fill con paste_text)
  'datepicker_js'→ DatepickerJSHandler (calendario JS, navegación por imagen)
  'no_filter'    → NoDateFilterHandler (sin selector, pandas filtra después)
  'macro'        → None (MacroPlayer maneja los DateStep, no se usa handler)
"""

from __future__ import annotations

from pathlib import Path

from date_handlers.exceptions import UnknownDateHandlerError

# Tipos válidos de date_handler (definidos en el PRD sección 3.5)
VALID_HANDLER_TYPES = ["input_date", "datepicker_js", "no_filter", "macro"]


def get_handler(handler_type: str, **kwargs):
    """
    Instancia el handler de fecha correcto según el tipo.

    Args:
        handler_type: Uno de 'input_date', 'datepicker_js', 'no_filter', 'macro'.
                      Viene del campo date_handler_type en schema.json.
        **kwargs según handler_type:

            input_date:
                field_template_from (str | Path): template PNG del campo fecha inicio.
                field_template_to   (str | Path): template PNG del campo fecha fin.

            datepicker_js:
                open_template       (str | Path): template del botón que abre el calendario.
                prev_arrow_template (str | Path): template de la flecha "mes anterior".
                next_arrow_template (str | Path): template de la flecha "mes siguiente".
                images_dir          (str | Path): carpeta con day_01.png ... day_31.png.

            no_filter: sin argumentos adicionales.

            macro: sin argumentos (MacroPlayer maneja los DateStep directamente).

    Returns:
        Instancia de BaseDateHandler lista para usar, o None para 'macro'.

    Raises:
        UnknownDateHandlerError: Si handler_type no está en VALID_HANDLER_TYPES.
    """
    from date_handlers.input_date import InputDateHandler
    from date_handlers.datepicker_js import DatepickerJSHandler
    from date_handlers.no_date_filter import NoDateFilterHandler

    if handler_type == "input_date":
        return InputDateHandler(
            field_template_from=Path(kwargs.get("field_template_from", "")),
            field_template_to=Path(kwargs.get("field_template_to", "")),
        )

    if handler_type == "datepicker_js":
        return DatepickerJSHandler(
            open_template=Path(kwargs.get("open_template", "")),
            prev_arrow_template=Path(kwargs.get("prev_arrow_template", "")),
            next_arrow_template=Path(kwargs.get("next_arrow_template", "")),
            images_dir=Path(kwargs.get("images_dir", ".")),
        )

    if handler_type == "no_filter":
        return NoDateFilterHandler()

    if handler_type == "macro":
        # El runner detecta macro_id y usa MacroPlayer directamente.
        # get_handler() retorna None para que el caller sepa que no hay handler.
        return None

    raise UnknownDateHandlerError(
        f"Tipo de handler '{handler_type}' no reconocido. "
        f"Tipos válidos: {', '.join(VALID_HANDLER_TYPES)}. "
        f"Verificá el campo date_handler_type en el schema.json de la tarea."
    )
