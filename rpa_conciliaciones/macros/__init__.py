"""
Módulo de grabación y reproducción de macros de automatización.

Exporta las clases principales para uso externo.
"""

from macros.models import Action, Recording
from macros.recorder import MacroRecorder
from macros.player import MacroPlayer
from macros.storage import MacroStorage
from macros.exceptions import MacroRecorderError, PlaybackError

__all__ = [
    "Action",
    "Recording",
    "MacroRecorder",
    "MacroPlayer",
    "MacroStorage",
    "MacroRecorderError",
    "PlaybackError",
]
