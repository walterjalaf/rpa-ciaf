"""
Excepciones del módulo date_handlers/.

Por qué existe: Cada tipo de selector de fecha puede fallar de formas
distintas. Excepciones específicas permiten que el runner identifique
exactamente qué salió mal y genere mensajes claros para el contador.
"""


class UnknownDateModeError(ValueError):
    """El modo de fecha solicitado no existe en DateResolver."""


class UnknownDateHandlerError(ValueError):
    """El tipo de date_handler no está registrado en el factory."""


class DateSelectorNotFoundError(Exception):
    """El selector de fecha (input HTML) no se encontró en la página."""


class DatepickerNavigationError(Exception):
    """No se pudo navegar el calendario JavaScript al mes/día deseado."""
