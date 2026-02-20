"""
Excepciones del módulo core/.

Por qué existe: Centraliza las excepciones del motor de ejecución para que
los módulos que dependen de core/ puedan capturar errores específicos sin
acoplarse a la implementación interna.
"""


class ChromeNotFoundError(Exception):
    """Chrome no está instalado, no está en ejecución o fue cerrado durante el bot."""


class ImageNotFoundError(Exception):
    """Template PNG no encontrado en pantalla dentro del timeout configurado."""


class DownloadTimeoutError(Exception):
    """El archivo no se descargó dentro del tiempo límite configurado."""
