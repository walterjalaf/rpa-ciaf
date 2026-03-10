"""
Wrapper sintético para ejecutar una macro grabada como BaseTask.

Por qué existe: El TaskRunner espera instancias de BaseTask en su task_list.
Cuando el usuario agrega una macro al plan de ejecución, necesitamos
envolverla en un objeto que respete ese contrato. MacroTask hace exactamente
eso: expone el task_id, task_name y platform_url de la Recording, y deja
los métodos navigate/trigger_download como no-ops porque el runner detecta
task.macro_id y delega la ejecución completa a MacroPlayer.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

from macros.models import Recording
from tasks.base_task import BaseTask

logger = logging.getLogger(__name__)


class MacroTask(BaseTask):
    """
    BaseTask sintético que envuelve una Recording grabada.

    Por qué existe: Permite que el TaskRunner trate macros grabadas
    igual que cualquier otra tarea de schema. El runner detecta que
    self.macro_id no es None y usa MacroPlayer en lugar de
    navigate() + trigger_download().

    navigate() y trigger_download() son no-ops deliberados: nunca
    deben llamarse para esta clase. Si se llaman por error, logueamos
    una advertencia en lugar de lanzar NotImplementedError (para no
    cortar la ejecución del plan).
    """

    def __init__(self, recording: Recording) -> None:
        """
        Args:
            recording: La macro grabada que se ejecutará como tarea.
        """
        # Atributos requeridos por BaseTask y el runner
        self.task_id: str                = recording.macro_id
        self.task_name: str              = recording.macro_name
        self.platform_url: str           = recording.platform_url
        self.date_handler_type: str      = "macro"
        self.date_mode: str              = "yesterday"
        self.macro_id: str               = recording.macro_id
        self.session_check_url: str      = recording.platform_url
        self.session_indicator_image: str = ""
        self.date_handler_kwargs: dict   = {}

        # Atributos opcionales con defaults seguros
        self.download_timeout_seconds: int  = 60
        self.expected_file_extension: str   = ""
        self.delivery: str                   = "direct"

        self._recording = recording

    def navigate(self, executor) -> None:  # type: ignore[override]
        """
        No-op: MacroPlayer maneja la navegación completa.

        El runner no debería llamar a este método para MacroTask
        (detecta macro_id != None antes). Si se llama, la advertencia
        en el log facilita el diagnóstico.
        """
        logger.warning(
            "MacroTask.navigate() llamado para '%s' — esto no debería ocurrir. "
            "El runner debería usar MacroPlayer directamente.",
            self.task_id,
        )

    def trigger_download(self, executor) -> None:  # type: ignore[override]
        """
        No-op: MacroPlayer maneja la descarga completa.

        Ver comentario en navigate().
        """
        logger.warning(
            "MacroTask.trigger_download() llamado para '%s' — esto no debería ocurrir.",
            self.task_id,
        )
