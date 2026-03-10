"""
Persistencia del plan de ejecución de tareas.

Por qué existe: El usuario puede reordenar tareas y agregar macros al plan
de ejecución. Este módulo guarda ese orden y el semáforo de estado
(pending/done/error) entre sesiones, para que el contador vea el mismo
estado al volver a abrir la app.

La lista se guarda en: ~/.rpa_conciliaciones/task_plan.json
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_PLAN_FILE = Path.home() / ".rpa_conciliaciones" / "task_plan.json"


@dataclass
class TaskPlanEntry:
    """
    Representa una entrada en el plan de ejecución.

    Por qué existe: Unifica schema tasks y macros bajo una interfaz común
    para que el TaskManagerPanel y el runner los traten de la misma forma.
    El entry_id es la clave estable dentro del plan — no cambia si se
    renombra la tarea o la macro.
    """

    entry_id: str          # uuid4 — clave estable
    display_name: str      # nombre visible en la UI
    item_type: str         # "schema" | "macro"
    task_id: str           # key para el runner: schema.task_id | recording.macro_id
    macro_id: str | None   # solo para item_type=="macro" (para MacroStorage.load)
    platform_url: str
    last_status: str       # "pending" | "done" | "error"
    last_run_at: str | None = None   # ISO datetime


def _entry_from_dict(data: dict[str, Any]) -> TaskPlanEntry:
    """Deserializa un dict en TaskPlanEntry con compatibilidad hacia atrás."""
    return TaskPlanEntry(
        entry_id=data.get("entry_id", str(uuid.uuid4())),
        display_name=data.get("display_name", "Sin nombre"),
        item_type=data.get("item_type", "schema"),
        task_id=data.get("task_id", ""),
        macro_id=data.get("macro_id"),
        platform_url=data.get("platform_url", ""),
        last_status=data.get("last_status", "pending"),
        last_run_at=data.get("last_run_at"),
    )


class TaskPlanStore:
    """
    Persistencia JSON del plan de ejecución de tareas.

    Por qué existe: Mantiene el orden de ejecución elegido por el usuario
    y los estados de semáforo entre sesiones. Es el único lugar que escribe
    task_plan.json.

    Thread-safety: los métodos son llamados desde el hilo UI. Si en el futuro
    se necesita escritura concurrente, agregar threading.Lock aquí.
    """

    _PLAN_FILE: Path = _PLAN_FILE

    def load(self) -> list[TaskPlanEntry]:
        """
        Carga el plan desde disco.

        Retorna lista vacía si el archivo no existe o está vacío/corrupto.
        El caller (TaskManagerPanel) detecta [] y auto-puebla con schemas.
        """
        if not self._PLAN_FILE.exists():
            return []
        try:
            text = self._PLAN_FILE.read_text(encoding="utf-8")
            data = json.loads(text)
            if not isinstance(data, list):
                logger.warning("task_plan.json tiene formato inesperado, se reinicia")
                return []
            return [_entry_from_dict(item) for item in data]
        except Exception as e:
            logger.warning("No se pudo leer task_plan.json: %s", e)
            return []

    def save(self, plan: list[TaskPlanEntry]) -> None:
        """Guarda el plan completo en disco."""
        try:
            self._PLAN_FILE.parent.mkdir(parents=True, exist_ok=True)
            text = json.dumps(
                [asdict(entry) for entry in plan],
                ensure_ascii=False,
                indent=2,
            )
            self._PLAN_FILE.write_text(text, encoding="utf-8")
        except Exception as e:
            logger.error("Error al guardar task_plan.json: %s", e)

    def update_status(self, entry_id: str, status: str) -> None:
        """
        Actualiza last_status y last_run_at de una entrada y guarda.

        Llamado desde el on_status_change wrapper en main.py cada vez
        que una tarea termina (done / error).
        """
        plan = self.load()
        for entry in plan:
            if entry.entry_id == entry_id:
                entry.last_status = status
                entry.last_run_at = datetime.now().isoformat()
                break
        else:
            logger.warning(
                "update_status: entry_id '%s' no encontrado en el plan", entry_id
            )
            return
        self.save(plan)
