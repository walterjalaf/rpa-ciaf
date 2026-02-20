"""
Persistencia local de macros grabadas en JSON.

Por qué existe: MacroRecorder produce Recording objects en memoria.
MacroStorage los serializa a JSON en AppData para que sobrevivan
entre sesiones. Cada macro es un archivo {macro_id}.json.

La carpeta por defecto es AppData/Local/rpa_conciliaciones/macros/
para evitar que el técnico accidentalmente borre los bots al reinstalar
la app (AppData no se toca en una reinstalación típica).

Formato del JSON:
    {
        "macro_id": "mercadopago_movimientos",
        "macro_name": "Mercado Pago - Movimientos",
        "platform_url": "https://...",
        "task_id": "mercadopago_movimientos",
        "actions": [...],
        "created_at": "2024-01-31T14:30:00",
        "version": "1.0",
        "description": ""
    }

Uso:
    storage = MacroStorage()
    path = storage.save(recording)
    macro = storage.load("mercadopago_movimientos")
    macros = storage.list_all()
"""

from __future__ import annotations

import dataclasses
import json
import logging
from datetime import datetime
from pathlib import Path

from macros.models import Action, Recording

logger = logging.getLogger(__name__)

_DEFAULT_STORAGE_DIR = (
    Path.home() / "AppData" / "Local" / "rpa_conciliaciones" / "macros"
)


class MacroStorage:
    """
    Almacena y recupera Recording objects como archivos JSON locales.

    Por qué existe: Separa la serialización del modelo de datos (Recording)
    de la lógica de grabación y reproducción. Si en el futuro se quiere
    cambiar el formato de almacenamiento (ej: SQLite), solo cambia esta clase.

    Uso:
        storage = MacroStorage()
        path = storage.save(recording)           # Guarda JSON
        macro = storage.load("macro_id")         # Carga JSON → Recording
        all_macros = storage.list_all()          # Lista todas las macros
        storage.delete("macro_id")              # Elimina el archivo
    """

    def __init__(self, storage_dir: Path | None = None) -> None:
        """
        Args:
            storage_dir: Carpeta raíz de almacenamiento.
                Default: AppData/Local/rpa_conciliaciones/macros/
        """
        self._storage_dir = storage_dir or _DEFAULT_STORAGE_DIR
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        logger.debug("MacroStorage inicializado en: %s", self._storage_dir)

    @property
    def storage_dir(self) -> Path:
        """Directorio donde se guardan los JSONs de macros."""
        return self._storage_dir

    def save(self, recording: Recording) -> Path:
        """
        Serializa y guarda una Recording en JSON.

        Si ya existe un archivo con ese macro_id, lo sobreescribe.

        Args:
            recording: Recording a guardar.

        Returns:
            Path del archivo JSON guardado.
        """
        data = dataclasses.asdict(recording)
        # datetime no es JSON serializable por defecto → convertir a ISO
        data["created_at"] = recording.created_at.isoformat()

        filepath = self._storage_dir / f"{recording.macro_id}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(
            "Macro '%s' guardada en: %s", recording.macro_name, filepath
        )
        return filepath

    def load(self, macro_id: str) -> Recording | None:
        """
        Carga y deserializa una Recording desde JSON.

        Args:
            macro_id: ID de la macro a cargar.

        Returns:
            Recording si existe el archivo. None si no existe.
        """
        filepath = self._storage_dir / f"{macro_id}.json"
        if not filepath.exists():
            logger.debug("Macro no encontrada: %s", macro_id)
            return None

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            return self._dict_to_recording(data)
        except Exception as e:
            logger.warning("Error cargando macro '%s': %s", macro_id, e)
            return None

    def list_all(self) -> list[Recording]:
        """
        Retorna todas las macros guardadas, ordenadas por fecha de creación.

        Returns:
            Lista de Recording. Las macros corruptas se omiten (con warning).
        """
        recordings: list[Recording] = []
        for path in sorted(self._storage_dir.glob("*.json")):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                recordings.append(self._dict_to_recording(data))
            except Exception as e:
                logger.warning("Error cargando macro '%s': %s. Ignorando.", path.name, e)

        recordings.sort(key=lambda r: r.created_at, reverse=True)
        return recordings

    def delete(self, macro_id: str) -> None:
        """
        Elimina el archivo JSON de la macro.

        No lanza excepción si la macro no existe.

        Args:
            macro_id: ID de la macro a eliminar.
        """
        filepath = self._storage_dir / f"{macro_id}.json"
        if filepath.exists():
            filepath.unlink()
            logger.info("Macro eliminada: %s", macro_id)
        else:
            logger.debug("Macro a eliminar no encontrada: %s", macro_id)

    # ── Deserialización ────────────────────────────────────────────────────

    def _dict_to_recording(self, data: dict) -> Recording:
        """Convierte un dict (desde JSON) en una instancia de Recording."""
        actions = [
            Action(**action_dict)
            for action_dict in data.get("actions", [])
        ]
        return Recording(
            macro_id=data["macro_id"],
            macro_name=data["macro_name"],
            platform_url=data["platform_url"],
            task_id=data["task_id"],
            actions=actions,
            created_at=datetime.fromisoformat(data["created_at"]),
            version=data.get("version", "1.0"),
            description=data.get("description", ""),
        )


if __name__ == "__main__":
    from macros.models import Action, Recording
    from datetime import datetime

    # Prueba básica de save/load
    test_storage = MacroStorage(storage_dir=Path("./temp/test_macros"))
    test_recording = Recording(
        macro_id="test_macro_001",
        macro_name="Macro de prueba",
        platform_url="https://ejemplo.com",
        task_id="test_task",
        actions=[
            Action(type="click", x=100, y=200),
            Action(type="date_step", date_field="date_from", date_format="%d/%m/%Y"),
            Action(type="key", keys=["enter"]),
        ],
        created_at=datetime.now(),
    )
    saved_path = test_storage.save(test_recording)
    print(f"Guardada en: {saved_path}")

    loaded = test_storage.load("test_macro_001")
    print(f"Cargada: {loaded.macro_name} — {len(loaded.actions)} acciones")

    all_macros = test_storage.list_all()
    print(f"Total en storage: {len(all_macros)} macros")
    print("=== Prueba completada ===")
