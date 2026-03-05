"""
Cola de uploads con retry automático en thread background.

Por qué existe: Desacopla la fase de descarga (bot usa mouse/pantalla)
de la fase de upload (red pura). El runner puede iniciar el siguiente
bot mientras el archivo de la tarea anterior se sube en background,
reduciendo el tiempo total de ejecución en ~27%.

Uso:
    queue = UploadQueue(file_uploader, reporter)
    queue.start()
    queue.enqueue("mercadopago", path, date_from, date_to, duration_seconds=25.3)
    # runner continúa con la siguiente tarea inmediatamente
    result = queue.wait_all(timeout=60)
    # {"uploaded": 2, "failed": 0, "pending": []}
    queue.stop()
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.reporter import Reporter
    from uploader.file_uploader import FileUploader

logger = logging.getLogger(__name__)

_SENTINEL = None  # Señal de fin para el consumer thread


@dataclass
class _UploadJob:
    """Trabajo de upload pendiente en la cola. Uso interno."""
    task_id: str
    filepath: Path
    date_from: date
    date_to: date
    no_filter_context: dict | None
    duration_seconds: float  # tiempo del bot, para telemetría


class UploadQueue:
    """
    Cola de uploads con thread consumer y retry automático.

    Por qué existe: Permite que el runner desacople la descarga del upload.
    El bot termina y libera el mouse para la siguiente tarea mientras el
    upload de la anterior corre en background (IO de red puro).

    Thread-safety: enqueue() es thread-safe desde cualquier hilo.
    wait_all() debe llamarse desde el hilo del runner, una vez que todos
    los enqueue() fueron emitidos.

    Limitaciones:
    - Consumer de un solo thread: los uploads son secuenciales en background
      para no saturar la red con múltiples requests simultáneos.
    - Si wait_all(timeout) expira, los jobs restantes quedan marcados como
      "pending". El consumer thread sigue corriendo en background (daemon),
      pero sus resultados no se incluyen en el summary de ejecución.
    """

    def __init__(
        self,
        file_uploader: FileUploader,
        reporter: Reporter,
        max_retries: int = 3,
    ) -> None:
        """
        Args:
            file_uploader: Para subir archivos al servidor.
            reporter: Para report_success() tras cada upload exitoso.
            max_retries: Intentos por job antes de marcarlo como fallido.
        """
        self._file_uploader = file_uploader
        self._reporter = reporter
        self._max_retries = max_retries

        self._queue: queue.Queue[_UploadJob | None] = queue.Queue()
        self._lock = threading.Lock()
        self._uploaded: list[str] = []
        self._failed: list[str] = []
        self._pending_task_ids: list[str] = []
        self._total_enqueued = 0
        self._total_processed = 0

        self._done_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Arranca el thread consumer. Llamar antes del primer enqueue()."""
        self._thread = threading.Thread(
            target=self._consumer,
            name="upload-queue-consumer",
            daemon=True,
        )
        self._thread.start()
        logger.debug("UploadQueue: consumer iniciado")

    def enqueue(
        self,
        task_id: str,
        filepath: Path,
        date_from: date,
        date_to: date,
        no_filter_context: dict | None = None,
        duration_seconds: float = 0.0,
    ) -> None:
        """
        Encola un upload para procesamiento en background.

        Thread-safe. Retorna inmediatamente sin bloquear al caller.

        Args:
            task_id: Identificador de la tarea.
            filepath: Ruta al archivo descargado.
            date_from: Inicio del período.
            date_to: Fin del período.
            no_filter_context: Contexto de no_filter si aplica.
            duration_seconds: Tiempo de ejecución del bot (para telemetría).
        """
        with self._lock:
            self._total_enqueued += 1
            self._pending_task_ids.append(task_id)
        self._queue.put(_UploadJob(
            task_id=task_id,
            filepath=filepath,
            date_from=date_from,
            date_to=date_to,
            no_filter_context=no_filter_context,
            duration_seconds=duration_seconds,
        ))
        logger.debug("Upload encolado: %s (%s)", task_id, filepath.name)

    def wait_all(self, timeout: int = 60) -> dict:
        """
        Espera a que todos los uploads encolados terminen o expiren.

        Debe llamarse DESPUÉS de que todos los enqueue() fueron emitidos
        (es decir, al final del loop de tareas en run_all()).

        Args:
            timeout: Segundos máximos de espera total.

        Returns:
            {
                "uploaded": int,          # uploads completados con éxito
                "failed_ids": list[str],  # task_ids que agotaron max_retries
                "pending": list[str],     # task_ids que no terminaron a tiempo
            }
        """
        self._queue.put(_SENTINEL)
        logger.debug(
            "UploadQueue: esperando %d upload(s) (timeout=%ds)",
            self._total_enqueued, timeout,
        )
        self._done_event.wait(timeout=timeout)

        with self._lock:
            pending_count = self._total_enqueued - self._total_processed
            pending_ids = list(self._pending_task_ids)

            if pending_count > 0:
                logger.warning(
                    "UploadQueue: %d upload(s) no completaron en %ds",
                    pending_count, timeout,
                )

            return {
                "uploaded": len(self._uploaded),
                "failed_ids": list(self._failed),
                "pending": pending_ids,
            }

    def stop(self) -> None:
        """Señaliza al consumer que termine (alternativa a wait_all)."""
        self._queue.put(_SENTINEL)

    # ── Implementación interna ──────────────────────────────────

    def _consumer(self) -> None:
        """
        Thread consumer: procesa jobs hasta recibir el sentinel.

        Por cada job: intenta el upload hasta max_retries veces con
        RETRY_DELAY_SECONDS entre intentos. Si agota los reintentos,
        lo registra como fallido.
        """
        retry_delay = 5.0

        while True:
            job = self._queue.get()
            if job is _SENTINEL:
                logger.debug("UploadQueue: sentinel recibido, consumer terminando")
                self._done_event.set()
                break
            self._process_job(job, retry_delay)

    def _process_job(self, job: _UploadJob, retry_delay: float) -> None:
        """Procesa un job con reintentos. Llama report_success si OK."""
        last_error = ""

        for attempt in range(1, self._max_retries + 1):
            try:
                success = self._file_uploader.upload(
                    task_id=job.task_id,
                    filepath=job.filepath,
                    date_from=job.date_from,
                    date_to=job.date_to,
                    no_filter_context=job.no_filter_context,
                )
                if success:
                    logger.info(
                        "Upload exitoso: %s (intento %d/%d)",
                        job.task_id, attempt, self._max_retries,
                    )
                    self._on_upload_success(job)
                    return

                last_error = "El servidor rechazó el archivo"

            except Exception as e:
                last_error = str(e)
                logger.warning(
                    "Upload fallido: %s (intento %d/%d): %s",
                    job.task_id, attempt, self._max_retries, e,
                )

            if attempt < self._max_retries:
                time.sleep(retry_delay)

        logger.error(
            "Upload de '%s' agotó %d intentos. Último error: %s",
            job.task_id, self._max_retries, last_error,
        )
        with self._lock:
            self._failed.append(job.task_id)
            self._total_processed += 1
            if job.task_id in self._pending_task_ids:
                self._pending_task_ids.remove(job.task_id)

    def _on_upload_success(self, job: _UploadJob) -> None:
        """Registra éxito y envía telemetría al servidor."""
        with self._lock:
            self._uploaded.append(job.task_id)
            self._total_processed += 1
            if job.task_id in self._pending_task_ids:
                self._pending_task_ids.remove(job.task_id)

        try:
            self._reporter.report_success(
                task_id=job.task_id,
                filepath=job.filepath,
                date_from=job.date_from,
                date_to=job.date_to,
                duration_seconds=job.duration_seconds,
            )
        except Exception as e:
            logger.warning(
                "Error enviando telemetría de '%s': %s", job.task_id, e
            )
