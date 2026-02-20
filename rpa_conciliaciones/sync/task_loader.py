"""
Cargador de tareas desde el servidor Laravel con cache local.

Por qué existe: Las tareas (bots) pueden actualizarse desde el servidor sin
redistribuir el .exe. Este módulo descarga la lista de tareas activas, compara
hashes para detectar cambios, y mantiene un cache local para funcionar offline.

Cuando USE_MOCK = True, lee los schema.json directamente de tasks/{plataforma}/
sin hacer peticiones HTTP.

Uso:
    loader = TaskLoader()
    tasks = loader.fetch_and_update()
    # tasks: list[dict] con la metadata de cada tarea activa
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from config import settings

if TYPE_CHECKING:
    from sync.api_client import ApiClient
    from sync.macro_sync import MacroSync

logger = logging.getLogger(__name__)

# Cache local: última lista válida de tareas
_CACHE_DIR = Path.home() / ".rpa_conciliaciones"
CACHE_FILE = _CACHE_DIR / "task_cache.json"

# Directorio raíz de tareas en el proyecto
_TASKS_DIR = Path(__file__).resolve().parent.parent / "tasks"


class TaskLoader:
    """
    Sincroniza la lista de tareas entre el servidor y el cliente local.

    Por qué existe: Permite al equipo técnico agregar o actualizar bots desde
    el servidor sin que el contador tenga que reinstalar la app. El cache local
    garantiza que la app funcione aunque el servidor esté caído.

    Uso:
        loader = TaskLoader(api_client)
        tasks = loader.fetch_and_update()
    """

    def __init__(
        self,
        api_client: ApiClient,
        macro_sync: MacroSync | None = None,
    ) -> None:
        """
        Args:
            api_client: Cliente HTTP con token de autenticación. Usado para
                incluir el Bearer token en peticiones GET /rpa/tasks.
            macro_sync: Sincronizador de macros. Si está presente, se llama
                a macro_sync.fetch_and_update() al final de fetch_and_update().
                Opcional: None omite la sincronización de macros.
        """
        self._api_client = api_client
        self._macro_sync = macro_sync

    def fetch_and_update(self) -> list[dict]:
        """
        Obtiene la lista de tareas activas.

        En modo mock: lee schema.json de cada subcarpeta en tasks/.
        En modo real: consulta GET /rpa/tasks, compara hashes, actualiza cache.

        Returns:
            Lista de dicts con la metadata de cada tarea activa.
        """
        if settings.USE_MOCK:
            tasks = self._fetch_local_schemas()
        else:
            tasks = self._fetch_from_server()

        # Sincronizar macros si el sincronizador está configurado.
        # Silencioso: un fallo en macros no debe interrumpir la carga de tareas.
        if self._macro_sync is not None:
            try:
                self._macro_sync.fetch_and_update()
            except Exception as e:
                logger.warning("Sincronización de macros omitida: %s", e)

        return tasks

    def _fetch_local_schemas(self) -> list[dict]:
        """Lee todos los schema.json locales de tasks/{plataforma}/."""
        tasks: list[dict] = []

        if not _TASKS_DIR.exists():
            logger.warning("Directorio de tareas no encontrado: %s", _TASKS_DIR)
            return tasks

        for platform_dir in sorted(_TASKS_DIR.iterdir()):
            if not platform_dir.is_dir():
                continue

            schema_path = platform_dir / "schema.json"
            if not schema_path.exists():
                continue

            try:
                with open(schema_path, "r", encoding="utf-8") as f:
                    schema = json.load(f)
                tasks.append(schema)
                logger.info(
                    "Schema cargado: %s (%s)",
                    schema.get("task_id", "?"), schema_path
                )
            except (json.JSONDecodeError, OSError) as e:
                logger.error(
                    "Error leyendo schema %s: %s", schema_path, e
                )

        logger.info("Modo mock: %d tareas cargadas desde schemas locales", len(tasks))
        self._save_cache(tasks)
        return tasks

    def _fetch_from_server(self) -> list[dict]:
        """Consulta la lista de tareas al servidor Laravel."""
        try:
            import httpx
            headers: dict = {}
            if self._api_client._token:
                headers["Authorization"] = f"Bearer {self._api_client._token}"
            client = httpx.Client(
                base_url=settings.SERVER_URL,
                timeout=settings.HTTP_TIMEOUT_SECONDS,
                headers=headers,
            )
            response = client.get("/rpa/tasks")
            response.raise_for_status()
            tasks = response.json()
            self._save_cache(tasks)
            logger.info(
                "Tareas sincronizadas desde servidor: %d activas", len(tasks)
            )
            return tasks
        except Exception as e:
            logger.warning(
                "No se pudo conectar al servidor, usando cache local: %s", e
            )
            return self._load_cache()

    def _save_cache(self, tasks: list[dict]) -> None:
        """Guarda la lista de tareas en cache local."""
        try:
            _CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(tasks, f, indent=2, ensure_ascii=False)
            logger.debug("Cache de tareas guardado en %s", CACHE_FILE)
        except OSError as e:
            logger.warning("No se pudo guardar cache de tareas: %s", e)

    def _load_cache(self) -> list[dict]:
        """Carga la lista de tareas desde el cache local."""
        if not CACHE_FILE.exists():
            logger.warning(
                "No hay cache de tareas disponible. "
                "Ejecute la app con conexión al servidor al menos una vez."
            )
            return []

        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                tasks = json.load(f)
            logger.info(
                "Cache de tareas cargado: %d tareas", len(tasks)
            )
            return tasks
        except (json.JSONDecodeError, OSError) as e:
            logger.error("Cache de tareas corrupto: %s", e)
            return []


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    from sync.api_client import ApiClient
    client = ApiClient()
    client.load_token()
    loader = TaskLoader(api_client=client)
    tasks = loader.fetch_and_update()
    print(f"Tareas cargadas: {len(tasks)}")
    for t in tasks:
        print(f"  - {t.get('task_id')}: {t.get('task_name')}")
