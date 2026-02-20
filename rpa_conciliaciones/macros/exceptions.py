"""
Excepciones del módulo macros/.

Por qué existe: Cada submódulo del proyecto define sus excepciones
en un archivo exceptions.py para que los callers puedan capturarlas
con precisión sin depender de excepciones genéricas de Python.

MacroRecorderError: errores durante la grabación (ej: intentar grabar
    cuando ya hay una grabación activa, detener sin haber iniciado).

PlaybackError: error durante la reproducción de una macro. Incluye
    screenshot_path para diagnóstico remoto (adjuntado al reporte
    de fallo que llega al servidor Laravel).
"""

from __future__ import annotations

from pathlib import Path


class MacroRecorderError(Exception):
    """
    Error en el ciclo de vida del MacroRecorder.

    Lanzado cuando:
    - Se llama start() con una grabación ya activa.
    - Se llama stop() o mark_date_step() sin grabación activa.
    """


class PlaybackError(Exception):
    """
    Error durante la reproducción de una macro con MacroPlayer.

    Atributos:
        screenshot_path: Path al PNG capturado en el momento del error.
            Incluido en el reporte de fallo al servidor para diagnóstico.
            Puede ser None si el screenshot no pudo tomarse.

    Causa más común: action.type == 'wait_image' y el template no
    aparece en pantalla dentro del timeout configurado.
    """

    def __init__(self, message: str, screenshot_path: Path | None = None) -> None:
        super().__init__(message)
        self.screenshot_path = screenshot_path
