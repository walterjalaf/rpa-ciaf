"""
Sincronización de macros grabadas con el servidor Laravel.

Por qué existe: Distribuye macros grabadas por técnicos a los equipos de
los contadores vía el servidor, sin redistribuir el .exe. Solo descarga
macros que cambiaron (comparación de hash). USE_MOCK=True → no-op silencioso.

Uso:
    sync = MacroSync(api_client, macro_storage)
    sync.fetch_and_update()
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import logging
from datetime import datetime
from typing import TYPE_CHECKING

from config import settings
from sync.exceptions import MacroSyncError

if TYPE_CHECKING:
    from macros.models import Recording
    from macros.storage import MacroStorage
    from sync.api_client import ApiClient

logger = logging.getLogger(__name__)


class MacroSync:
    """
    Sincroniza macros grabadas entre el servidor y el almacenamiento local.

    Por qué existe: Distribuye macros nuevas/actualizadas a los contadores.
    Compara hashes para descarga incremental. No elimina macros locales
    que no estén en el servidor (pueden estar sin publicar aún).

    Recording y MacroStorage se importan dinámicamente (macros/ es Feature 11).

    Uso:
        sync = MacroSync(api_client, storage)
        sync.fetch_and_update()
    """

    def __init__(
        self,
        api_client: ApiClient,
        storage: MacroStorage,
    ) -> None:
        """
        Args:
            api_client: Cliente HTTP con token de autenticación.
            storage: Almacenamiento local de macros (macros/storage.py).
                     Disponible a partir de Feature 11.
        """
        self._api_client = api_client
        self._storage = storage

    def fetch_macros(self) -> list[dict]:
        """
        Obtiene la lista de macros disponibles en el servidor.

        Returns:
            Lista de dicts con {macro_id, version, hash} por macro.
            Lista vacía en modo mock o si no hay macros en el servidor.

        Raises:
            MacroSyncError: Si la petición al servidor falló.
        """
        if settings.USE_MOCK:
            logger.debug("Modo mock: lista de macros vacía (sin servidor)")
            return []

        return self._fetch_macros_real()

    def download_macro(self, macro_id: str) -> Recording:
        """
        Descarga una macro del servidor y la deserializa en un Recording.

        Args:
            macro_id: Identificador único de la macro a descargar.

        Returns:
            Instancia de Recording con todas las acciones grabadas.

        Raises:
            MacroSyncError: Si la descarga falló o macros/ no está disponible.
        """
        if settings.USE_MOCK:
            raise MacroSyncError(
                f"No se puede descargar la macro '{macro_id}' en modo mock: "
                "no hay servidor disponible."
            )

        return self._download_macro_real(macro_id)

    def upload_macro(self, recording: Recording) -> bool:
        """
        Publica una macro grabada en el servidor.

        En modo mock: simula la publicación con log informativo.

        Args:
            recording: Instancia de Recording a publicar.

        Returns:
            True si el servidor aceptó la macro, False en caso de error.
        """
        if settings.USE_MOCK:
            logger.info(
                "Modo mock: publicación de macro '%s' simulada",
                recording.macro_id,
            )
            return True

        return self._upload_macro_real(recording)

    def fetch_and_update(self) -> None:
        """
        Descarga macros nuevas o actualizadas desde el servidor.

        Compara el hash de cada macro remota con la copia local.
        Solo descarga las que cambiaron para minimizar tráfico de red.
        Silencioso si el servidor no está disponible — no bloquea el inicio.
        """
        if settings.USE_MOCK:
            logger.debug("Modo mock: sincronización de macros omitida")
            return

        try:
            remote_list = self.fetch_macros()
            if not remote_list:
                logger.info("No hay macros en el servidor para sincronizar")
                return

            updated = 0
            for remote_meta in remote_list:
                macro_id = remote_meta.get("macro_id")
                remote_hash = remote_meta.get("hash", "")

                if not macro_id:
                    continue

                local = self._storage.load(macro_id)
                if local is not None and self._compute_hash(local) == remote_hash:
                    logger.debug("Macro '%s' al dia (hash coincide)", macro_id)
                    continue

                recording = self.download_macro(macro_id)
                self._storage.save(recording)
                updated += 1
                logger.info("Macro '%s' actualizada desde el servidor", macro_id)

            logger.info(
                "Sincronización completada: %d/%d macros actualizadas",
                updated, len(remote_list),
            )

        except Exception as e:
            logger.warning(
                "Sincronización de macros falló (no crítico): %s", e
            )

    def _fetch_macros_real(self) -> list[dict]:
        """GET /rpa/macros → lista de {macro_id, version, hash}."""
        try:
            import httpx
            response = self._make_client().get("/rpa/macros")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise MacroSyncError(
                f"No se pudo obtener la lista de macros del servidor: {e}"
            ) from e

    def _download_macro_real(self, macro_id: str) -> Recording:
        """GET /rpa/macros/{macro_id} → Recording deserializada."""
        try:
            # Import dinámico: macros/ disponible a partir de Feature 11
            from macros.models import Action, Recording  # noqa: PLC0415
        except ImportError as exc:
            raise MacroSyncError(
                "El módulo macros/ no está disponible. "
                "Completar Feature 11 antes de usar sincronización real."
            ) from exc

        try:
            response = self._make_client().get(f"/rpa/macros/{macro_id}")
            response.raise_for_status()
            return self._deserialize(response.json(), Recording, Action)
        except MacroSyncError:
            raise
        except Exception as e:
            raise MacroSyncError(
                f"No se pudo descargar la macro '{macro_id}': {e}"
            ) from e

    def _upload_macro_real(self, recording: Recording) -> bool:
        """POST /rpa/macros con el JSON de la Recording."""
        try:
            payload = self._serialize(recording)
            response = self._make_client().post("/rpa/macros", json=payload)
            response.raise_for_status()
            logger.info(
                "Macro '%s' publicada al servidor exitosamente",
                recording.macro_id,
            )
            return True
        except Exception as e:
            logger.error(
                "No se pudo publicar la macro '%s': %s",
                recording.macro_id, e,
            )
            return False

    def _make_client(self):
        """Crea un cliente httpx con auth Bearer del ApiClient."""
        import httpx
        headers: dict = {}
        if self._api_client._token:
            headers["Authorization"] = f"Bearer {self._api_client._token}"
        return httpx.Client(
            base_url=settings.SERVER_URL,
            timeout=settings.HTTP_TIMEOUT_SECONDS,
            headers=headers,
        )

    def _serialize(self, recording: Recording) -> dict:
        """Convierte un Recording en dict JSON-serializable."""
        return {
            "macro_id": recording.macro_id,
            "macro_name": recording.macro_name,
            "platform_url": recording.platform_url,
            "task_id": recording.task_id,
            "version": recording.version,
            "description": recording.description,
            "created_at": recording.created_at.isoformat(),
            "actions": [
                {k: v for k, v in vars(action).items() if v is not None}
                for action in recording.actions
            ],
        }

    def _deserialize(self, data: dict, recording_cls, action_cls) -> Recording:
        """Convierte un dict JSON en una instancia de Recording."""
        # Filtrar solo los campos que el dataclass conoce para tolerancia a
        # versiones de API con campos extra o faltantes.
        action_fields = {f.name for f in dataclasses.fields(action_cls)}
        actions = [
            action_cls(**{k: v for k, v in a.items() if k in action_fields})
            for a in data.get("actions", [])
        ]

        rec_fields = {f.name for f in dataclasses.fields(recording_cls)}
        rec_data = {k: v for k, v in data.items() if k in rec_fields}
        rec_data["actions"] = actions
        rec_data["created_at"] = datetime.fromisoformat(data["created_at"])
        return recording_cls(**rec_data)

    def _compute_hash(self, recording: Recording) -> str:
        """
        Calcula un hash SHA-256 truncado de los datos de una macro.

        Usado para comparar versiones locales vs remotas sin descargar el
        contenido completo. Solo los primeros 16 caracteres del hex digest.
        """
        payload = self._serialize(recording)
        content = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(content.encode()).hexdigest()[:16]


if __name__ == "__main__":
    import logging as _logging
    import sys
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
    _logging.basicConfig(level=_logging.DEBUG)

    from sync.api_client import ApiClient

    class _MockStorage:  # Stub hasta que macros/ exista (Feature 11)
        def load(self, _): return None
        def save(self, _): pass
        def list_all(self): return []

    client = ApiClient()
    client.load_token()
    sync = MacroSync(client, _MockStorage())
    print(f"fetch_macros (mock): {sync.fetch_macros()}")
    sync.fetch_and_update()
    print("OK — fetch_and_update completado")
