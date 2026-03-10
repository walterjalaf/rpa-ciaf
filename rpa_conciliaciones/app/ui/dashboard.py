"""
Ventana principal del dashboard de RPA Conciliaciones — CIAF Consultora Integral.

Por qué existe: Es la interfaz que el contador usa a diario. Muestra el
estado de sesiones, la lista de tareas, el selector de período y el botón
de ejecución. Toda la interacción del usuario pasa por esta ventana.

La UI corre en el thread principal de tkinter. Las operaciones largas
(health check, ejecución de bots) corren en threads secundarios y actualizan
la UI via queue.Queue + polling con after(50ms).

Patrón obligatorio: usar on_status_change() para actualizaciones desde
threads background, nunca tocar widgets directamente fuera del hilo UI.

Rediseño v2.0: identidad visual CIAF — header con branding, cards por sección,
ventana responsiva, CTA prominente, Light/Dark mode real.

Uso:
    dashboard = Dashboard(tasks=task_list, on_execute=callback,
                          on_manual_upload=callback)
    dashboard.mainloop()
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from datetime import date
from pathlib import Path
from queue import Empty, Queue

from PIL import Image
import customtkinter as ctk

from config import settings
from app.ui.date_selector import DateSelector
from app.ui.session_panel import SessionPanel
from app.ui.task_status import TaskStatusRow

# Ruta absoluta al directorio de assets (independiente del cwd)
_ASSETS_DIR = Path(__file__).parent / "assets"

if settings.SHOW_MACRO_TAB:
    from macros.recorder import MacroRecorder
    from macros.storage import MacroStorage
    from app.ui.macro_recorder_panel import MacroRecorderPanel
    from app.ui.macro_list_panel import MacroListPanel

logger = logging.getLogger(__name__)

# ── Paleta CIAF ────────────────────────────────────────────────
_CIAF_BLUE        = "#0F4069"
_CIAF_BLUE_HOVER  = "#0A2D50"
_CIAF_BLUE_DARK   = "#092340"   # header dark mode
_CIAF_GRAY        = "#8A8A8D"
_COLOR_OK         = "#28A745"
_COLOR_ERROR      = "#DC3545"
_COLOR_WARN_BG    = ("#FFF8E6", "#3A2A00")
_COLOR_WARN_TEXT  = ("#856404", "#E8B84B")
_COLOR_WARN_BTN   = ("#E87722", "#CC6600")


class Dashboard(ctk.CTk):
    """
    Ventana principal con layout premium CIAF.

    Por qué existe: Ensambla los componentes visuales y conecta los eventos
    del usuario con callbacks del motor via main.py. Implementa el patrón
    queue.Queue para recibir actualizaciones de estado desde threads background
    de forma thread-safe.

    Layout grid (de arriba a abajo):
        row 0 — Header: logo CIAF + título + fecha
        row 1 — Banner de actualización (oculto por defecto)
        row 2 — Cuerpo principal (scrollable o tabview)
        row 3 — Footer CTA: botón Ejecutar + barra de progreso
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

        # ── Configuración de la ventana ────────────────────────
        self.title("RPA - Ciaf")
        self.geometry("960x700")
        self.minsize(800, 580)
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")

        # ── Estado interno ─────────────────────────────────────
        self._on_execute       = on_execute
        self._on_manual_upload = on_manual_upload
        self._task_rows:    dict[str, TaskStatusRow] = {}
        self._total_tasks   = len(tasks)
        self._completed     = 0
        self._status_queue: Queue[tuple[str, str, str]] = Queue()

        # ── Grid principal responsivo ──────────────────────────
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)   # El cuerpo se expande

        # ── Construcción ───────────────────────────────────────
        self._build_header()
        self._build_update_banner()

        if settings.SHOW_MACRO_TAB:
            self._build_tabview(tasks)
        else:
            self._build_body(tasks)

        self._build_footer()
        self._start_ui_polling()

    # ══════════════════════════════════════════════════════════
    # Thread-safety con queue.Queue
    # ══════════════════════════════════════════════════════════

    def on_status_change(self, task_id: str, status: str, message: str) -> None:
        """
        Callback para TaskRunner. PUEDE llamarse desde cualquier thread.
        Contrato público — firma no puede cambiar.
        """
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
                text=f"{self._completed} de {self._total_tasks} tareas completadas"
            )

    # ══════════════════════════════════════════════════════════
    # Overlay de ejecución
    # ══════════════════════════════════════════════════════════

    def _show_execution_overlay(self) -> None:
        """Muestra overlay semitransparente durante la ejecución del bot."""
        if not hasattr(self, "_overlay_frame"):
            self._overlay_frame = ctk.CTkFrame(
                self, fg_color=("gray80", "gray15"), corner_radius=0,
            )
            inner = ctk.CTkFrame(
                self._overlay_frame,
                corner_radius=16,
                fg_color=("white", "#1E2530"),
                border_width=1,
                border_color=(_CIAF_BLUE, "#0A2D50"),
            )
            inner.place(relx=0.5, rely=0.5, anchor="center")
            ctk.CTkLabel(
                inner,
                text="⟳  Bot en ejecución",
                font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
                text_color=(_CIAF_BLUE, "#5BA3D9"),
            ).pack(padx=40, pady=(20, 6))
            ctk.CTkLabel(
                inner,
                text="No toques el mouse ni el teclado\nmientras el bot trabaja.",
                font=ctk.CTkFont(family="Segoe UI", size=13),
                text_color=("gray30", "gray70"),
                justify="center",
            ).pack(padx=40, pady=(0, 20))
        self._overlay_frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        self._overlay_frame.lift()

    def _hide_execution_overlay(self) -> None:
        """Oculta el overlay de ejecución."""
        if hasattr(self, "_overlay_frame"):
            self._overlay_frame.place_forget()

    # ══════════════════════════════════════════════════════════
    # Construcción del layout
    # ══════════════════════════════════════════════════════════

    def _build_header(self) -> None:
        """
        Header superior con branding CIAF.
        Fondo azul marino, logo real izquierda, fecha derecha.
        """
        header = ctk.CTkFrame(
            self,
            fg_color=(_CIAF_BLUE, _CIAF_BLUE_DARK),
            corner_radius=0,
            height=64,
        )
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(1, weight=1)
        header.grid_propagate(False)

        # Logo CIAF real (PNG con fondo transparente)
        logo_widget = self._make_logo_widget(header)
        logo_widget.grid(row=0, column=0, padx=(20, 12), pady=12)

        # Título de la app
        title_col = ctk.CTkFrame(header, fg_color="transparent")
        title_col.grid(row=0, column=1, sticky="w")

        ctk.CTkLabel(
            title_col,
            text="RPA - Ciaf",
            font=ctk.CTkFont(family="Segoe UI", size=17, weight="bold"),
            text_color="white",
        ).pack(anchor="w")
        ctk.CTkLabel(
            title_col,
            text="Consultora Integral CIAF",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color="#8BB8D4",
        ).pack(anchor="w")

        # Fecha a la derecha
        ctk.CTkLabel(
            header,
            text=self._format_today(),
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#8BB8D4",
        ).grid(row=0, column=2, padx=(0, 20))

    def _build_update_banner(self) -> None:
        """Banner de actualización disponible (oculto por defecto)."""
        self._update_banner = ctk.CTkFrame(
            self,
            fg_color=_COLOR_WARN_BG,
            corner_radius=0,
            height=42,
        )
        # No se hace grid aquí — se muestra solo cuando hay update disponible

        banner_inner = ctk.CTkFrame(self._update_banner, fg_color="transparent")
        banner_inner.pack(fill="x", padx=20)

        self._update_label = ctk.CTkLabel(
            banner_inner,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=_COLOR_WARN_TEXT,
        )
        self._update_label.pack(side="left", pady=10)

        self._update_btn = ctk.CTkButton(
            banner_inner,
            text="Actualizar ahora",
            width=130, height=26,
            corner_radius=6,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color=_COLOR_WARN_BTN,
            hover_color="#A84D00",
        )
        self._update_btn.pack(side="right", pady=8)

    def _build_body(self, tasks: list[dict]) -> None:
        """
        Cuerpo principal sin tabs: session + date + task list en una columna.
        Usa CTkScrollableFrame para adaptarse al número de tareas.
        """
        scroll = ctk.CTkScrollableFrame(
            self,
            fg_color=("gray95", "gray12"),
            corner_radius=0,
            scrollbar_button_color=(_CIAF_GRAY, "gray35"),
        )
        scroll.grid(row=2, column=0, sticky="nsew")
        scroll.columnconfigure(0, weight=1)

        self._build_session_panel(scroll)
        self._build_date_selector(scroll)
        self._build_task_list(tasks, scroll)

    def _build_tabview(self, tasks: list[dict]) -> None:
        """Crea CTkTabview con tabs 'Tareas' y 'Macros' (solo técnicos)."""
        self._tabview = ctk.CTkTabview(
            self,
            fg_color=("gray95", "gray12"),
            segmented_button_selected_color=_CIAF_BLUE,
            segmented_button_selected_hover_color=_CIAF_BLUE_HOVER,
            text_color=("gray10", "gray90"),
            command=self._on_tab_change,
        )
        tabview = self._tabview
        tabview.grid(row=2, column=0, sticky="nsew", padx=0, pady=0)

        tab_tasks  = tabview.add("Tareas")
        tab_macros = tabview.add("Macros")

        tab_tasks.columnconfigure(0, weight=1)

        self._build_session_panel(tab_tasks)
        self._build_date_selector(tab_tasks)
        self._build_task_list(tasks, tab_tasks)
        self._build_macro_tab(tab_macros)

    def _build_macro_tab(self, parent) -> None:
        """
        Construye la tab de Macros con grabador arriba y lista abajo.
        Usa CTkScrollableFrame para que el estado Review nunca quede cortado.
        """
        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        recorder = MacroRecorder()
        storage  = MacroStorage()

        list_panel = MacroListPanel(
            scroll, storage,
            on_test_macro=self._handle_test_macro,
        )

        recorder_panel = MacroRecorderPanel(
            scroll, recorder, storage,
            on_saved=list_panel.refresh,
        )
        recorder_panel.pack(fill="x", padx=12, pady=(8, 8))
        list_panel.pack(fill="x", padx=12)

    def _build_session_panel(self, parent) -> None:
        """Card de estado de sesiones."""
        self._session_panel = SessionPanel(parent)
        self._session_panel.pack(fill="x", padx=16, pady=(12, 6))

    def _build_date_selector(self, parent) -> None:
        """Card de selector de período."""
        self._date_selector = DateSelector(parent)
        self._date_selector.pack(fill="x", padx=16, pady=6)

    def _build_task_list(self, tasks: list[dict], parent) -> None:
        """Card scrollable de tareas."""
        # Encabezado de sección
        section_header = ctk.CTkFrame(parent, fg_color="transparent")
        section_header.pack(fill="x", padx=16, pady=(10, 4))

        ctk.CTkLabel(
            section_header,
            text="Tareas programadas",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=("gray10", "gray90"),
        ).pack(side="left")

        self._tasks_count_label = ctk.CTkLabel(
            section_header,
            text=f"{len(tasks)} tareas",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            corner_radius=10,
            fg_color=("#E8E8E9", "#3A3A3C"),
            text_color=(_CIAF_GRAY, "#AAAAAD"),
            padx=10, pady=2,
        )
        self._tasks_count_label.pack(side="right")

        # Card contenedora de las filas
        tasks_card = ctk.CTkFrame(
            parent,
            corner_radius=12,
            fg_color=("white", "#1E2530"),
        )
        tasks_card.pack(fill="x", padx=16, pady=(0, 12))

        for i, task_data in enumerate(tasks):
            row = TaskStatusRow(
                tasks_card,
                task_name=task_data.get("task_name", "Sin nombre"),
                task_id=task_data.get("task_id", ""),
                platform_url=task_data.get("platform_url", ""),
                on_manual_upload=self._on_manual_upload,
            )
            row.pack(fill="x", padx=8, pady=(8 if i == 0 else 4, 4))
            self._task_rows[task_data["task_id"]] = row

        # Espacio inferior dentro de la card
        ctk.CTkFrame(tasks_card, fg_color="transparent", height=4).pack()

    def _build_footer(self) -> None:
        """
        Footer con el CTA principal (Ejecutar todo) y barra de progreso.
        Siempre visible, no scrollea.
        """
        self._footer = ctk.CTkFrame(
            self,
            fg_color=("white", "#161D28"),
            corner_radius=0,
            border_width=1,
            border_color=("gray85", "gray20"),
        )
        self._footer.grid(row=3, column=0, sticky="ew")
        self._footer.columnconfigure(0, weight=1)
        footer = self._footer

        # Contenedor interior centrado
        inner = ctk.CTkFrame(footer, fg_color="transparent")
        inner.pack(pady=14)

        # Botón CTA primario — el elemento más prominente de la vista
        self._execute_btn = ctk.CTkButton(
            inner,
            text="▶   Ejecutar todo",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            height=48, width=240,
            corner_radius=10,
            fg_color=_CIAF_BLUE,
            hover_color=_CIAF_BLUE_HOVER,
            command=self._on_execute_click,
        )
        self._execute_btn.pack(pady=(0, 10))

        # Barra de progreso general
        self._progress_bar = ctk.CTkProgressBar(
            inner,
            width=420, height=6,
            corner_radius=3,
            progress_color=_CIAF_BLUE,
            fg_color=("gray85", "gray25"),
        )
        self._progress_bar.pack(pady=(0, 6))
        self._progress_bar.set(0)

        self._progress_label = ctk.CTkLabel(
            inner,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=_CIAF_GRAY,
        )
        self._progress_label.pack()

    def _on_tab_change(self) -> None:
        """Muestra u oculta el footer según la tab activa."""
        if self._tabview.get() == "Macros":
            self._footer.grid_remove()
        else:
            self._footer.grid(row=3, column=0, sticky="ew")

    # ══════════════════════════════════════════════════════════
    # Métodos públicos (contratos que no pueden cambiar)
    # ══════════════════════════════════════════════════════════

    def update_session_results(self, results: list) -> None:
        """
        Actualiza el panel de sesiones con resultados del health check.
        Contrato público — firma no puede cambiar.
        """
        self._session_panel.update_results(results)

    def show_update_banner(self, version_info: dict) -> None:
        """
        Muestra el banner de actualización disponible.
        Contrato público — firma no puede cambiar.
        """
        version = version_info.get("latest_version", "?")
        self._update_label.configure(
            text=f"⬆  Nueva versión {version} disponible — reiniciá la app para instalarla."
        )
        # Insertar entre header (row 0) y cuerpo (row 2)
        self._update_banner.grid(row=1, column=0, sticky="ew")

    def on_execution_complete(self, summary: dict) -> None:
        """
        Re-habilita el botón de ejecución y oculta el overlay.
        Contrato público — firma no puede cambiar.
        """
        self._hide_execution_overlay()
        self._execute_btn.configure(state="normal")
        success          = summary.get("success", 0)
        total            = summary.get("total", 0)
        elapsed          = summary.get("duration_seconds", 0)
        uploads_pending  = summary.get("uploads_pending", 0)
        uploads_failed   = summary.get("uploads_failed", [])

        base_text = f"Finalizado — {success} de {total} tareas exitosas  ({elapsed:.0f}s)"

        if uploads_failed:
            base_text += f"  |  {len(uploads_failed)} archivo(s) no se pudieron subir"
        elif uploads_pending:
            base_text += f"  |  {uploads_pending} archivo(s) pendientes de subida"

        self._progress_label.configure(text=base_text)

    def update_task_status(self, task_id: str, status: str, message: str = "") -> None:
        """Actualiza el estado visual de una tarea (solo hilo principal)."""
        self._update_task_row(task_id, status, message)

    # ══════════════════════════════════════════════════════════
    # Handlers privados
    # ══════════════════════════════════════════════════════════

    def _on_execute_click(self) -> None:
        """Handler del botón 'Ejecutar todo'."""
        self._execute_btn.configure(state="disabled")
        self._completed = 0
        self._progress_bar.set(0)
        self._progress_label.configure(text="Iniciando ejecución...")

        for row in self._task_rows.values():
            row.update_status("pending")

        selection = self._date_selector.get_selection()
        self._show_execution_overlay()
        self._on_execute(selection)

    def _handle_test_macro(self, recording) -> None:
        """Handler del botón '▶ Probar'. Lanza reproducción en thread secundario."""
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

        date_from, date_to = DateResolver.resolve("yesterday")
        launcher = ChromeLauncher()
        try:
            launcher.launch(recording.platform_url)
            executor = PyAutoExecutor()
            player = MacroPlayer(executor)
            player.play(recording, date_from, date_to)
            logger.info("Prueba de macro '%s' completada", recording.macro_name)
        except Exception as e:
            logger.error("Error en prueba de macro '%s': %s", recording.macro_name, e)
        finally:
            launcher.close()

    # ── Utilidades ──────────────────────────────────────────────

    def _make_logo_widget(self, parent) -> ctk.CTkLabel:
        """
        Carga ciaf_logo_2.png como CTkImage DPI-aware y retorna un CTkLabel.

        Usa un tamaño de 100×40px (ratio original ≈ 2.46:1).
        Si la imagen no se encuentra, cae a un label de texto como fallback
        para no crashear la app en entornos donde falte el asset.
        """
        logo_path = _ASSETS_DIR / "ciaf_logo_2.png"
        try:
            pil_img = Image.open(logo_path).convert("RGBA")
            ctk_img = ctk.CTkImage(
                light_image=pil_img,
                dark_image=pil_img,
                size=(100, 40),
            )
            return ctk.CTkLabel(parent, image=ctk_img, text="")
        except Exception as e:
            logger.warning("No se pudo cargar el logo CIAF: %s", e)
            # Fallback: rectángulo con texto
            fallback = ctk.CTkFrame(
                parent, corner_radius=6, fg_color="white",
                width=72, height=36,
            )
            fallback.grid_propagate(False)
            ctk.CTkLabel(
                fallback, text="CIAF",
                font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
                text_color=_CIAF_BLUE,
            ).place(relx=0.5, rely=0.5, anchor="center")
            return fallback  # type: ignore[return-value]

    def _format_today(self) -> str:
        """Formatea la fecha de hoy en español para el header."""
        today = date.today()
        days   = ["lunes", "martes", "miércoles", "jueves",
                  "viernes", "sábado", "domingo"]
        months = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
                  "julio", "agosto", "septiembre", "octubre",
                  "noviembre", "diciembre"]
        return (
            f"{days[today.weekday()].capitalize()} "
            f"{today.day} de {months[today.month - 1]} de {today.year}"
        )
