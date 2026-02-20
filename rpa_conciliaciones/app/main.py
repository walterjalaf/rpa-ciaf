"""
Entry point de la aplicación RPA Conciliaciones.

Por qué existe: Es el punto de entrada único que instancia todos los componentes,
los conecta entre sí y arranca la interfaz gráfica. Ningún otro módulo debe
instanciar componentes de otras capas — esa responsabilidad es exclusiva de main.py.

Flujo al iniciar:
    1. Configurar logging
    2. Instanciar ApiClient y cargar token
    3. TaskLoader.fetch_and_update() → lista de tareas
    4. Verificar actualizaciones del .exe
    5. Instanciar Dashboard con callbacks
    6. Lanzar health check en thread background
    7. mainloop()

Uso en desarrollo:
    python -m app.main
    (o desde la raíz del proyecto: python app/main.py)
"""

from __future__ import annotations

import logging
import sys
import threading
from datetime import date
from pathlib import Path

import customtkinter as ctk

# Asegurar que el directorio raíz del proyecto esté en sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app.ui.alert_modal import AlertModal
from app.ui.dashboard import Dashboard
from config.settings import LOG_LEVEL
from core.reporter import Reporter
from sync.api_client import ApiClient
from sync.task_loader import TaskLoader
from sync.updater import UpdaterClient
from uploader.file_uploader import FileUploader
from uploader.manual_uploader import ManualUploader

# ── Logging: consola + archivo ─────────────────────────────────
_LOG_DIR = Path.home() / ".rpa_conciliaciones"
_LOG_DIR.mkdir(parents=True, exist_ok=True)
_LOG_FILE = _LOG_DIR / "app.log"

_log_format = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format=_log_format,
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(_LOG_FILE, encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def _global_exception_handler(exc_type, exc_value, exc_tb) -> None:
    """Captura excepciones no manejadas y las loguea al archivo."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return
    logger.critical(
        "Error no capturado", exc_info=(exc_type, exc_value, exc_tb)
    )


sys.excepthook = _global_exception_handler


class Application:
    """
    Controlador principal de la aplicación.

    Por qué existe: Conecta las capas del sistema (sync, core, uploader, UI)
    sin que ninguna conozca a las demás directamente. Maneja el ciclo de vida
    de la app y la comunicación entre threads.
    """

    def __init__(self) -> None:
        # ── Capa sync ──────────────────────────────────────────
        self._api_client = ApiClient()
        self._api_client.load_token()
        self._macro_sync = None  # Activar en Feature 11 cuando macros/ esté listo
        self._task_loader = TaskLoader(
            api_client=self._api_client,
            macro_sync=self._macro_sync,
        )
        self._updater = UpdaterClient()

        # ── Cargar tareas ──────────────────────────────────────
        self._task_schemas = self._task_loader.fetch_and_update()
        logger.info("%d tareas cargadas", len(self._task_schemas))

        # ── Capa uploader/reporter ─────────────────────────────
        self._file_uploader = FileUploader(self._api_client)
        self._manual_uploader = ManualUploader(self._file_uploader)
        self._reporter = Reporter(self._api_client)

        # ── UI ─────────────────────────────────────────────────
        self._dashboard = Dashboard(
            tasks=self._task_schemas,
            on_execute=self._handle_execute,
            on_manual_upload=self._handle_manual_upload,
        )

        # ── Verificar actualizaciones ──────────────────────────
        self._check_updates()

        # ── Health check en background ─────────────────────────
        self._start_health_check()

    def run(self) -> None:
        """Arranca el mainloop de tkinter."""
        logger.info("Iniciando RPA Conciliaciones v1.0.0")
        self._dashboard.mainloop()

    # ── Handlers ───────────────────────────────────────────────

    def _handle_execute(self, selection: dict) -> None:
        """Handler del botón 'Ejecutar todo'. Corre en thread secundario."""
        thread = threading.Thread(
            target=self._run_tasks,
            args=(selection,),
            daemon=True,
        )
        thread.start()

    def _run_tasks(self, selection: dict) -> None:
        """Ejecuta las tareas en un thread secundario."""
        from core.runner import TaskRunner

        task_instances = self._load_task_instances()
        if not task_instances:
            self._dashboard.after(0, self._dashboard.on_execution_complete, {
                "total": 0, "success": 0, "failed": 0,
                "failed_tasks": [], "duration_seconds": 0,
                "total_rows_processed": 0,
            })
            return

        def on_status_change(task_id: str, status: str, msg: str) -> None:
            self._dashboard.on_status_change(task_id, status, msg)

        runner = TaskRunner(
            task_list=task_instances,
            on_status_change=on_status_change,
            file_uploader=self._file_uploader,
            reporter=self._reporter,
            macro_storage=None,  # Activar en Feature 11
        )

        summary = runner.run_all(
            date_mode=selection.get("mode"),
            custom_from=selection.get("custom_from"),
            custom_to=selection.get("custom_to"),
        )

        self._dashboard.after(0, self._dashboard.on_execution_complete, summary)

    def _handle_manual_upload(self, task_id: str, task_name: str) -> None:
        """Handler de carga manual desde la UI."""
        # Obtener fechas de la selección actual del date selector
        selection = self._dashboard._date_selector.get_selection()
        mode = selection.get("mode", "yesterday")

        from date_handlers.date_resolver import DateResolver
        try:
            date_from, date_to = DateResolver.resolve(
                mode,
                selection.get("custom_from"),
                selection.get("custom_to"),
            )
        except Exception:
            date_from = date_to = date.today()

        success = self._manual_uploader.prompt_and_upload(
            task_id, task_name, date_from, date_to
        )

        if success:
            self._dashboard.update_task_status(
                task_id, "done_manual", "Cargado manualmente"
            )

    def _check_updates(self) -> None:
        """Verifica si hay actualizaciones del .exe disponibles."""
        update_info = self._updater.check()
        if update_info:
            self._dashboard.show_update_banner(update_info)

    def _start_health_check(self) -> None:
        """Lanza el health check de sesiones en un thread background."""
        thread = threading.Thread(
            target=self._run_health_check,
            daemon=True,
        )
        thread.start()

    def _run_health_check(self) -> None:
        """Ejecuta el health check y actualiza la UI."""
        try:
            from core.chrome_launcher import ChromeLauncher    # noqa: PLC0415
            from core.health_checker import HealthChecker      # noqa: PLC0415
            from core.pyauto_executor import PyAutoExecutor    # noqa: PLC0415

            task_instances = self._load_task_instances()
            if not task_instances:
                return

            launcher = ChromeLauncher()
            executor = PyAutoExecutor()
            checker = HealthChecker(launcher, executor)
            results = checker.check_all(task_instances)

            self._dashboard.after(
                0, self._dashboard.update_session_results, results
            )
            self._reporter.report_session_check(results)

        except Exception as e:
            logger.warning("Health check falló: %s", e)

    def _load_task_instances(self) -> list:
        """
        Carga las instancias de BaseTask desde los schemas.

        Busca el task.py de cada plataforma y lo importa dinámicamente.
        """
        instances = []
        tasks_dir = _PROJECT_ROOT / "tasks"

        for schema in self._task_schemas:
            platform = schema.get("platform", "")
            task_module_path = tasks_dir / platform / "task.py"

            if not task_module_path.exists():
                logger.warning(
                    "No se encontró task.py para plataforma '%s'", platform
                )
                continue

            try:
                import importlib.util
                spec = importlib.util.spec_from_file_location(
                    f"tasks.{platform}.task", task_module_path
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Buscar la primera subclase de BaseTask en el módulo
                from tasks.base_task import BaseTask
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (isinstance(attr, type)
                            and issubclass(attr, BaseTask)
                            and attr is not BaseTask):
                        instances.append(attr())
                        logger.debug("Task cargada: %s", attr_name)
                        break

            except Exception as e:
                logger.error(
                    "Error cargando task de '%s': %s", platform, e
                )

        return instances


def main() -> None:
    """Arranca la aplicación RPA Conciliaciones."""
    app = Application()
    app.run()


if __name__ == "__main__":
    main()
