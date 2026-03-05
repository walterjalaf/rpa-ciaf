"""
Orquestador de ejecución de tareas (bots).

Por qué existe: Coordina la ejecución secuencial de todas las tareas activas,
delegando la descarga a cada BaseTask, el upload a FileUploader y el reporte
a Reporter. Notifica cambios de estado a la UI via callback.

El runner NO ejecuta lógica de negocio ni de UI. Solo orquesta:
resolver fechas → ejecutar bot → subir archivo → reportar → siguiente tarea.

Uso:
    runner = TaskRunner(task_list, on_status_change, file_uploader, reporter)
    summary = runner.run_all(date_mode="yesterday")
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

from core.reporter import Reporter
from date_handlers.date_resolver import DateResolver
from uploader.file_uploader import FileUploader

if TYPE_CHECKING:
    from macros.models import Recording
    from macros.storage import MacroStorage
    from uploader.upload_queue import UploadQueue

logger = logging.getLogger(__name__)

# ── Estados de tarea (constantes del módulo) ───────────────────
PENDING = "pending"
RUNNING = "running"
DONE = "done"
ERROR = "error"


class TaskRunner:
    """
    Orquesta la ejecución secuencial de todas las tareas de descarga.

    Por qué existe: Separa la orquestación de la ejecución individual.
    Cada BaseTask sabe cómo descargar un archivo de su plataforma.
    El runner sabe en qué orden ejecutarlas, qué hacer si una falla,
    y cómo reportar resultados.

    Política de errores: Si una tarea falla, el runner la marca como ERROR,
    reporta el fallo al servidor, y continúa con la siguiente. Nunca
    interrumpe el loop por el fallo de una tarea individual.

    Uso:
        runner = TaskRunner(task_list, on_status_change, uploader, reporter)
        summary = runner.run_all(date_mode="yesterday")
        # summary['success'] / summary['total'] = tareas exitosas
    """

    def __init__(
        self,
        task_list: list,
        on_status_change: Callable[[str, str, str], None],
        file_uploader: FileUploader,
        reporter: Reporter,
        macro_storage: MacroStorage | None = None,
        upload_queue: UploadQueue | None = None,
    ) -> None:
        """
        Args:
            task_list: Lista de instancias de BaseTask a ejecutar.
            on_status_change: Callback que recibe (task_id, status, message).
                La UI lo usa para actualizar el estado visual de cada tarea.
            file_uploader: Instancia de FileUploader para subir archivos.
            reporter: Instancia de Reporter para telemetría y reporte de fallos.
            macro_storage: Almacenamiento de macros grabadas. Usado en Feature 12
                para ejecutar tareas macro-based con MacroPlayer. Opcional.
            upload_queue: Si se provee, los uploads se ejecutan en background
                (Implementación E+F del PRD). Si es None, comportamiento actual.
        """
        self._task_list = task_list
        self._on_status_change = on_status_change
        self._file_uploader = file_uploader
        self._reporter = reporter
        self._macro_storage = macro_storage
        self._upload_queue = upload_queue

    def run_all(
        self,
        date_mode: str | None = None,
        custom_from: date | None = None,
        custom_to: date | None = None,
    ) -> dict:
        """
        Ejecuta todas las tareas en secuencia.

        Para cada tarea: resuelve fechas, ejecuta el bot, sube el archivo
        y reporta el resultado. Si una tarea falla, continúa con la siguiente.

        Args:
            date_mode: Modo de fecha global. Si None, usa el date_mode de
                cada tarea individual.
            custom_from: Fecha inicio custom (solo si date_mode='custom').
            custom_to: Fecha fin custom (solo si date_mode='custom').

        Returns:
            Dict con resumen de ejecución:
            {
                "total": int,
                "success": int,
                "failed": int,
                "failed_tasks": list[str],
                "duration_seconds": float,
                "total_rows_processed": int,
            }
        """
        total = len(self._task_list)
        success = 0
        failed_tasks: list[str] = []
        total_rows = 0
        global_start = time.monotonic()

        if self._upload_queue:
            self._upload_queue.start()

        logger.info(
            "Iniciando ejecución de %d tareas (mode=%s, pipeline=%s)",
            total, date_mode or "por tarea", self._upload_queue is not None,
        )

        for task in self._task_list:
            task_result = self._run_single_task(
                task, date_mode, custom_from, custom_to
            )

            if task_result["success"]:
                success += 1
                total_rows += task_result.get("row_count", 0)
            else:
                failed_tasks.append(task.task_id)

        global_elapsed = time.monotonic() - global_start

        # Esperar uploads pendientes si está en modo pipeline
        uploads_pending = 0
        uploads_failed: list[str] = []
        if self._upload_queue:
            upload_result = self._upload_queue.wait_all(timeout=60)
            uploads_pending = len(upload_result.get("pending", []))
            uploads_failed = upload_result.get("failed_ids", [])
            if uploads_pending > 0 or uploads_failed:
                logger.warning(
                    "Uploads: %d completados, %d fallidos, %d pendientes de timeout",
                    upload_result.get("uploaded", 0),
                    len(uploads_failed),
                    uploads_pending,
                )

        summary = {
            "total": total,
            "success": success,
            "failed": len(failed_tasks),
            "failed_tasks": failed_tasks,
            "duration_seconds": round(global_elapsed, 1),
            "total_rows_processed": total_rows,
            "uploads_pending": uploads_pending,
            "uploads_failed": uploads_failed,
        }

        logger.info(
            "Ejecución completada: %d/%d exitosas, %d fallidas (%.1fs)",
            success, total, len(failed_tasks), global_elapsed
        )

        return summary

    def _run_single_task(
        self,
        task,
        date_mode: str | None,
        custom_from: date | None,
        custom_to: date | None,
    ) -> dict:
        """
        Ejecuta una sola tarea: resolver fechas → bot → upload → reporte.

        Returns:
            Dict con {"success": bool, "row_count": int}.
        """
        # Resolver fechas
        mode = date_mode if date_mode is not None else task.date_mode
        try:
            date_from, date_to = DateResolver.resolve(
                mode, custom_from, custom_to
            )
        except Exception as e:
            self._handle_task_error(task, f"Error resolviendo fechas: {e}")
            return {"success": False, "row_count": 0}

        self._on_status_change(
            task.task_id, RUNNING,
            f"Ejecutando ({date_from} → {date_to})"
        )

        task_start = time.monotonic()

        try:
            # Ejecutar el bot: macro-based si tiene macro_id, code-based si no
            macro_id = getattr(task, "macro_id", None)
            if macro_id and self._macro_storage:
                macro = self._macro_storage.load(macro_id)
                if macro:
                    filepath = self._run_macro_task(task, macro, date_from, date_to)
                else:
                    logger.warning(
                        "Macro '%s' no encontrada en storage. "
                        "Usando flujo code-based como fallback.",
                        macro_id,
                    )
                    filepath = task.run(date_from, date_to)
            else:
                filepath = task.run(date_from, date_to)

            elapsed = time.monotonic() - task_start
            no_filter_ctx = getattr(task, "_handler_context", None)

            if self._upload_queue:
                # Modo pipeline (E+F): encolar upload en background y continuar
                # inmediatamente. report_success lo llama el consumer tras subir.
                # NOTA: no_filter_context siempre es None para tareas macro-based
                # porque base_task.run() ya filtra; se pasa por compatibilidad.
                self._upload_queue.enqueue(
                    task_id=task.task_id,
                    filepath=filepath,
                    date_from=date_from,
                    date_to=date_to,
                    no_filter_context=no_filter_ctx,
                    duration_seconds=elapsed,
                )
                self._on_status_change(
                    task.task_id, DONE,
                    f"Descargado en {elapsed:.0f}s — subiendo al servidor..."
                )
                return {"success": True, "row_count": 0}

            # Modo síncrono (comportamiento original): subir y reportar antes
            # de continuar con la siguiente tarea.
            self._file_uploader.upload(
                task_id=task.task_id,
                filepath=filepath,
                date_from=date_from,
                date_to=date_to,
                no_filter_context=no_filter_ctx,
            )

            row_count = self._report_success(
                task, filepath, date_from, date_to, elapsed
            )

            self._on_status_change(
                task.task_id, DONE,
                f"Completada en {elapsed:.0f}s"
            )

            return {"success": True, "row_count": row_count}

        except Exception as e:
            # base_task adjunta screenshot_path a la excepción si pudo
            # capturar pantalla antes de relanzar el error.
            screenshot = getattr(e, "screenshot_path", None)
            self._handle_task_error(task, str(e), screenshot_path=screenshot)
            return {"success": False, "row_count": 0}

    def _run_macro_task(
        self,
        task,
        macro: Recording,
        date_from: date,
        date_to: date,
    ) -> Path:
        """
        Ejecuta una tarea usando MacroPlayer en lugar de task.run().

        Flujo: ChromeLauncher.launch → snapshot → MacroPlayer.play
               → DownloadWatcher.wait → cleanup.

        El snapshot se toma antes de play() para detectar correctamente
        el archivo nuevo en Downloads (Chrome todavía no navegó).

        Args:
            task: Instancia de BaseTask con platform_url.
            macro: Recording cargada desde MacroStorage.
            date_from: Fecha inicio para DateStep.
            date_to: Fecha fin para DateStep.

        Returns:
            Path al archivo descargado y movido a temp/.

        Raises:
            PlaybackError: Si la macro falla durante la reproducción.
            DownloadTimeoutError: Si el archivo no aparece en el timeout.
        """
        from core.chrome_launcher import ChromeLauncher
        from core.downloader import DownloadWatcher
        from core.pyauto_executor import PyAutoExecutor
        from macros.player import MacroPlayer

        launcher = ChromeLauncher()
        try:
            logger.info(
                "Ejecutando macro '%s' para tarea '%s' (%s → %s)",
                macro.macro_name, task.task_id, date_from, date_to,
            )
            launcher.launch(task.platform_url)
            executor = PyAutoExecutor()

            # Snapshot ANTES de que la macro navegue/descargue
            watcher = DownloadWatcher()
            watcher.take_snapshot()

            player = MacroPlayer(executor)
            player.play(
                macro, date_from, date_to,
                on_progress=self._make_progress_callback(task.task_id),
            )

            filepath = watcher.wait_for_download()
            final_path = watcher.cleanup(filepath)
            logger.info(
                "Macro '%s' completada: %s", macro.macro_name, final_path.name
            )
            return final_path

        finally:
            try:
                launcher.close()
            except Exception as e:
                logger.debug("Error cerrando Chrome tras macro: %s", e)

    def _make_progress_callback(self, task_id: str) -> Callable[[str], None]:
        """
        Crea un callback de progreso para MacroPlayer.

        El callback emite mensajes "attempt|||max_retries|||desc" al hilo de UI
        via on_status_change con status="progress". La UI los parsea para mostrar
        el indicador de reintentos en tiempo real en la fila de la tarea.
        """
        def _on_progress(message: str) -> None:
            self._on_status_change(task_id, "progress", message)
        return _on_progress

    def _report_success(
        self,
        task,
        filepath: Path,
        date_from: date,
        date_to: date,
        elapsed: float,
    ) -> int:
        """Reporta éxito y retorna row_count estimado."""
        try:
            self._reporter.report_success(
                task_id=task.task_id,
                filepath=filepath,
                date_from=date_from,
                date_to=date_to,
                duration_seconds=elapsed,
            )
            # Estimar filas para el resumen
            return self._reporter._estimate_row_count(filepath)
        except Exception as e:
            logger.warning(
                "Error reportando éxito de %s: %s", task.task_id, e
            )
            return 0

    def _handle_task_error(
        self,
        task,
        error_msg: str,
        screenshot_path: Path | None = None,
    ) -> None:
        """Marca tarea como error, reporta con screenshot si disponible, y continúa."""
        logger.error("Tarea '%s' falló: %s", task.task_name, error_msg)

        self._on_status_change(task.task_id, ERROR, error_msg)

        try:
            self._reporter.report_failure(
                task_id=task.task_id,
                error=error_msg,
                screenshot_path=screenshot_path,
            )
        except Exception as e:
            logger.warning(
                "Error reportando fallo de %s: %s", task.task_id, e
            )


if __name__ == "__main__":
    import logging as _logging
    _logging.basicConfig(level=_logging.DEBUG)

    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

    from sync.api_client import ApiClient

    # Setup mock
    client = ApiClient()
    client.load_token()
    uploader = FileUploader(client)
    reporter = Reporter(client)

    # Callback de prueba
    def on_change(task_id: str, status: str, msg: str) -> None:
        print(f"  [{status.upper():>7}] {task_id}: {msg}")

    # Importar tareas piloto
    from tasks.mercadopago.task import MercadoPagoTask
    from tasks.galicia.task import GaliciaTask

    tasks = [MercadoPagoTask(), GaliciaTask()]

    runner = TaskRunner(tasks, on_change, uploader, reporter)
    print("=== TaskRunner instanciado con", len(tasks), "tareas ===")
    print("(No ejecutar run_all sin Chrome con sesiones activas)")
    print("=== Fin ===")
