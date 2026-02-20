"""
Ventana principal del dashboard de RPA Conciliaciones.

Por qué existe: Es la interfaz que el contador usa a diario. Muestra el
estado de sesiones, la lista de tareas, el selector de período y el botón
de ejecución. Toda la interacción del usuario pasa por esta ventana.

La UI corre en el thread principal de tkinter. Las operaciones largas
(health check, ejecución de bots) corren en threads secundarios y
actualizan la UI via queue.Queue + polling con after(50ms).

Patrón obligatorio: usar on_status_change() para actualizaciones desde
threads background, nunca tocar widgets directamente fuera del hilo UI.

Uso:
    dashboard = Dashboard(tasks=task_list, on_execute=callback,
                          on_manual_upload=callback)
    dashboard.mainloop()
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date
from queue import Empty, Queue

import customtkinter as ctk

from config import settings
from app.ui.date_selector import DateSelector
from app.ui.session_panel import SessionPanel
from app.ui.task_status import TaskStatusRow

if settings.SHOW_MACRO_TAB:
    from macros.recorder import MacroRecorder
    from macros.storage import MacroStorage
    from app.ui.macro_recorder_panel import MacroRecorderPanel
    from app.ui.macro_list_panel import MacroListPanel

logger = logging.getLogger(__name__)


class Dashboard(ctk.CTk):
    """
    Ventana principal que contiene todos los componentes del dashboard.

    Por qué existe: Ensambla los componentes visuales y conecta los eventos
    del usuario con callbacks del motor via main.py. Implementa el patrón
    queue.Queue para recibir actualizaciones de estado desde threads background
    de forma thread-safe.

    Layout (de arriba a abajo):
        1. Header: título + fecha de hoy
        2. Banner de actualización (oculto por defecto)
        3. SessionPanel: estado de sesiones
        4. DateSelector: selector de período
        5. Task list: frame scrollable con TaskStatusRow por tarea
        6. Botón "Ejecutar todo" + barra de progreso
    """

    def __init__(
        self,
        tasks: list[dict],
        on_execute: Callable[[dict], None],
        on_manual_upload: Callable[[str, str], None],
    ) -> None:
        """
        Args:
            tasks: Lista de dicts con task_id, task_name, platform_url.
            on_execute: Callback(selection_dict) al presionar "Ejecutar todo".
            on_manual_upload: Callback(task_id, task_name) para carga manual.
        """
        super().__init__()
        self.title("RPA Conciliaciones")
        self.geometry("900x650")
        self.resizable(False, False)
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")

        self._on_execute = on_execute
        self._on_manual_upload = on_manual_upload
        self._task_rows: dict[str, TaskStatusRow] = {}
        self._total_tasks = len(tasks)
        self._completed = 0
        self._status_queue: Queue[tuple[str, str, str]] = Queue()

        self._build_header()
        self._build_update_banner()

        if settings.SHOW_MACRO_TAB:
            self._build_tabview(tasks)
        else:
            self._build_session_panel(self)
            self._build_date_selector(self)
            self._build_task_list(tasks, self)
            self._build_footer(self)

        self._start_ui_polling()

    # ── Thread-safety con queue.Queue ─────────────────────────

    def on_status_change(self, task_id: str, status: str, message: str) -> None:
        """Callback para TaskRunner. PUEDE llamarse desde cualquier thread."""
        self._status_queue.put((task_id, status, message))

    def _start_ui_polling(self) -> None:
        """Inicia el ciclo de polling del queue en el hilo de UI."""
        self._poll_queue()

    def _poll_queue(self) -> None:
        """Vacía el queue y actualiza widgets. Se auto-reprograma cada 50ms."""
        try:
            while True:
                task_id, status, message = self._status_queue.get_nowait()
                self._update_task_row(task_id, status, message)
        except Empty:
            pass
        self.after(50, self._poll_queue)

    def _update_task_row(self, task_id: str, status: str, message: str) -> None:
        """Actualiza el estado visual de una tarea. Solo hilo principal."""
        row = self._task_rows.get(task_id)
        if row is None:
            logger.warning("Task row no encontrada: %s", task_id)
            return
        row.update_status(status, message)
        if status in ("done", "done_manual", "error"):
            self._completed += 1
            progress = self._completed / max(self._total_tasks, 1)
            self._progress_bar.set(progress)
            self._progress_label.configure(
                text=f"{self._completed} de {self._total_tasks} completadas"
            )

    # ── Overlay de ejecución ──────────────────────────────────

    def _show_execution_overlay(self) -> None:
        """Muestra overlay semitransparente durante la ejecución del bot."""
        if not hasattr(self, "_overlay_frame"):
            self._overlay_frame = ctk.CTkFrame(
                self, fg_color=("gray80", "gray20"), corner_radius=0,
            )
            ctk.CTkLabel(
                self._overlay_frame,
                text="Bot en ejecución\nNo toques el mouse ni el teclado",
                font=ctk.CTkFont(size=16, weight="bold"),
            ).place(relx=0.5, rely=0.5, anchor="center")
        self._overlay_frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        self._overlay_frame.lift()

    def _hide_execution_overlay(self) -> None:
        """Oculta el overlay de ejecución."""
        if hasattr(self, "_overlay_frame"):
            self._overlay_frame.place_forget()

    # ── Construcción de la UI ──────────────────────────────────

    def _build_header(self) -> None:
        """Header con título y fecha de hoy."""
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(12, 4))

        ctk.CTkLabel(
            header, text="RPA Conciliaciones",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).pack(side="left")

        ctk.CTkLabel(
            header, text=self._format_today(),
            font=ctk.CTkFont(size=12),
            text_color="gray",
        ).pack(side="right")

    def _build_update_banner(self) -> None:
        """Banner de actualización disponible (oculto por defecto)."""
        self._update_banner = ctk.CTkFrame(
            self, fg_color="#FFF3CD", corner_radius=8,
        )  # No se hace pack aquí — se muestra solo cuando hay update

        self._update_label = ctk.CTkLabel(
            self._update_banner, text="",
            font=ctk.CTkFont(size=12),
            text_color="#856404",
        )
        self._update_label.pack(side="left", padx=12, pady=8)

        self._update_btn = ctk.CTkButton(
            self._update_banner, text="Actualizar",
            width=100, height=28,
            font=ctk.CTkFont(size=11),
        )
        self._update_btn.pack(side="right", padx=12, pady=8)

    def _build_tabview(self, tasks: list[dict]) -> None:
        """Crea CTkTabview con tabs 'Tareas' y 'Macros' (solo técnicos)."""
        tabview = ctk.CTkTabview(self, height=520)
        tabview.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        tab_tasks = tabview.add("Tareas")
        tab_macros = tabview.add("Macros")

        self._build_session_panel(tab_tasks)
        self._build_date_selector(tab_tasks)
        self._build_task_list(tasks, tab_tasks)
        self._build_footer(tab_tasks)
        self._build_macro_tab(tab_macros)

    def _build_macro_tab(self, parent: ctk.CTkFrame) -> None:
        """
        Construye la tab de Macros con grabador arriba y lista abajo.

        Usa CTkScrollableFrame para que el estado Review (con los botones
        de guardar al pie) nunca quede cortado por el borde del tabview,
        independientemente del alto disponible.
        """
        scroll = ctk.CTkScrollableFrame(parent)
        scroll.pack(fill="both", expand=True, padx=0, pady=0)

        recorder = MacroRecorder()
        storage = MacroStorage()

        # Lista creada primero para que el closure de on_saved pueda
        # referenciarla. Se packea DESPUÉS del grabador para quedar abajo.
        list_panel = MacroListPanel(
            scroll, storage,
            on_test_macro=self._handle_test_macro,
        )

        # Grabador ARRIBA (PRD): botones "Guardar" siempre accesibles
        # al inicio de la tab, antes de hacer scroll.
        recorder_panel = MacroRecorderPanel(
            scroll, recorder, storage,
            on_saved=list_panel.refresh,
        )
        recorder_panel.pack(fill="x", padx=4, pady=(0, 8))

        # Lista ABAJO: visible al hacer scroll hacia abajo.
        list_panel.pack(fill="x", padx=4)

    def _build_session_panel(self, parent: ctk.CTkFrame) -> None:
        """Panel de estado de sesiones."""
        self._session_panel = SessionPanel(parent)
        self._session_panel.pack(fill="x", padx=16, pady=4)

    def _build_date_selector(self, parent: ctk.CTkFrame) -> None:
        """Selector de período de fecha."""
        self._date_selector = DateSelector(parent)
        self._date_selector.pack(fill="x", padx=16, pady=4)

    def _build_task_list(self, tasks: list[dict], parent: ctk.CTkFrame) -> None:
        """Lista scrollable de tareas."""
        ctk.CTkLabel(
            parent, text="Tareas",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(anchor="w", padx=28, pady=(8, 2))

        scroll_frame = ctk.CTkScrollableFrame(
            parent, height=220, corner_radius=8,
        )
        scroll_frame.pack(fill="x", padx=16, pady=(0, 8))

        for task_data in tasks:
            row = TaskStatusRow(
                scroll_frame,
                task_name=task_data.get("task_name", "Sin nombre"),
                task_id=task_data.get("task_id", ""),
                platform_url=task_data.get("platform_url", ""),
                on_manual_upload=self._on_manual_upload,
            )
            row.pack(fill="x", pady=2)
            self._task_rows[task_data["task_id"]] = row

    def _build_footer(self, parent: ctk.CTkFrame) -> None:
        """Botón de ejecución y barra de progreso."""
        footer = ctk.CTkFrame(parent, fg_color="transparent")
        footer.pack(fill="x", padx=16, pady=(4, 12))

        self._execute_btn = ctk.CTkButton(
            footer, text="\u25b6  Ejecutar todo",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=42, width=200,
            command=self._on_execute_click,
        )
        self._execute_btn.pack(pady=(0, 8))

        self._progress_bar = ctk.CTkProgressBar(footer, width=400)
        self._progress_bar.pack(pady=(0, 4))
        self._progress_bar.set(0)

        self._progress_label = ctk.CTkLabel(
            footer, text="",
            font=ctk.CTkFont(size=11),
            text_color="gray",
        )
        self._progress_label.pack()

    # ── Métodos públicos ────────────────────────────────────────

    def _handle_test_macro(self, recording) -> None:
        """Handler del botón '▶ Probar'. Lanza reproducción en thread secundario."""
        import threading
        thread = threading.Thread(
            target=self._run_macro_test,
            args=(recording,),
            daemon=True,
        )
        thread.start()

    def _run_macro_test(self, recording) -> None:
        """Reproduce la macro con fecha de ayer. Corre en thread secundario."""
        from core.chrome_launcher import ChromeLauncher
        from core.pyauto_executor import PyAutoExecutor
        from date_handlers.date_resolver import DateResolver
        from macros.player import MacroPlayer

        try:
            date_from, date_to = DateResolver.resolve("yesterday")
            launcher = ChromeLauncher()
            launcher.launch(recording.platform_url)

            executor = PyAutoExecutor()
            player = MacroPlayer(executor)
            player.play(recording, date_from, date_to)

            logger.info("Prueba de macro '%s' completada", recording.macro_name)
        except Exception as e:
            logger.error(
                "Error en prueba de macro '%s': %s", recording.macro_name, e
            )

    def update_task_status(self, task_id: str, status: str,
                           message: str = "") -> None:
        """Actualiza el estado visual de una tarea (solo hilo principal)."""
        self._update_task_row(task_id, status, message)

    def update_session_results(self, results: list) -> None:
        """Actualiza el panel de sesiones con resultados del health check."""
        self._session_panel.update_results(results)

    def show_update_banner(self, version_info: dict) -> None:
        """Muestra el banner de actualización disponible."""
        version = version_info.get("latest_version", "?")
        self._update_label.configure(
            text=f"Nueva version {version} disponible"
        )
        self._update_banner.pack(
            fill="x", padx=16, pady=4, before=self._session_panel
        )

    def on_execution_complete(self, summary: dict) -> None:
        """Re-habilita el botón de ejecución y oculta el overlay."""
        self._hide_execution_overlay()
        self._execute_btn.configure(state="normal")
        success = summary.get("success", 0)
        total = summary.get("total", 0)
        elapsed = summary.get("duration_seconds", 0)
        self._progress_label.configure(
            text=f"Finalizado: {success}/{total} exitosas ({elapsed:.0f}s)"
        )

    # ── Handlers privados ───────────────────────────────────────

    def _on_execute_click(self) -> None:
        """Handler del botón 'Ejecutar todo'."""
        self._execute_btn.configure(state="disabled")
        self._completed = 0
        self._progress_bar.set(0)
        self._progress_label.configure(text="Iniciando...")

        for row in self._task_rows.values():
            row.update_status("pending")

        selection = self._date_selector.get_selection()
        self._show_execution_overlay()
        self._on_execute(selection)

    def _format_today(self) -> str:
        """Formatea la fecha de hoy en español."""
        today = date.today()
        days = ["lunes", "martes", "miercoles", "jueves",
                "viernes", "sabado", "domingo"]
        months = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
                  "julio", "agosto", "septiembre", "octubre",
                  "noviembre", "diciembre"]
        day_name = days[today.weekday()]
        month_name = months[today.month - 1]
        return f"Tareas del {day_name} {today.day} de {month_name}"
