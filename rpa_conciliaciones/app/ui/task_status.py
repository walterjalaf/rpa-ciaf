"""
Componente visual de estado por tarea en el dashboard.

Por qué existe: Cada tarea tiene una fila en la lista principal del dashboard.
Esta fila muestra el estado actual (pendiente, ejecutando, completado, error)
con borde lateral de color, íconos semánticos y una barra de progreso
indeterminada cuando la tarea está corriendo.

Rediseño v2.0: identidad visual CIAF — borde izquierdo de 4px, pill de estado,
barra de progreso inline, sin código técnico visible al contador.

Uso:
    row = TaskStatusRow(parent, task_name="Mercado Pago", task_id="mp_mov",
                        platform_url="https://...", on_manual_upload=callback)
    row.update_status("running", "Descargando...")
"""

from __future__ import annotations

import logging
from collections.abc import Callable

import customtkinter as ctk

logger = logging.getLogger(__name__)

# ── Paleta CIAF ────────────────────────────────────────────────
_CIAF_BLUE    = "#0F4069"
_CIAF_GRAY    = "#8A8A8D"
_COLOR_OK     = "#28A745"
_COLOR_ERROR  = "#DC3545"
_COLOR_WARN   = "#E87722"

# ── Mapa de estados visuales ───────────────────────────────────
_STATUS_CONFIG: dict[str, dict] = {
    "pending": {
        "icon":         "◷",
        "border_color": _CIAF_GRAY,
        "label":        "Pendiente",
        "pill_bg":      ("#E8E8E9", "#3A3A3C"),
        "pill_fg":      (_CIAF_GRAY, "#AAAAAD"),
    },
    "running": {
        "icon":         "⟳",
        "border_color": _CIAF_BLUE,
        "label":        "Ejecutando...",
        "pill_bg":      ("#D6E4F0", "#0A2A45"),
        "pill_fg":      (_CIAF_BLUE, "#5BA3D9"),
    },
    "done": {
        "icon":         "✓",
        "border_color": _COLOR_OK,
        "label":        "Completado",
        "pill_bg":      ("#D4EDDA", "#143020"),
        "pill_fg":      (_COLOR_OK, "#5CB87A"),
    },
    "done_manual": {
        "icon":         "📎",
        "border_color": _COLOR_OK,
        "label":        "Cargado manualmente",
        "pill_bg":      ("#D4EDDA", "#143020"),
        "pill_fg":      (_COLOR_OK, "#5CB87A"),
    },
    "error": {
        "icon":         "✕",
        "border_color": _COLOR_ERROR,
        "label":        "Error — acción requerida",
        "pill_bg":      ("#FDECEA", "#3B1214"),
        "pill_fg":      (_COLOR_ERROR, "#E87070"),
    },
}


class TaskStatusRow(ctk.CTkFrame):
    """
    Fila visual que muestra el estado de una tarea en el dashboard.

    Por qué existe: El contador necesita ver de un vistazo qué tareas están
    pendientes, cuáles se ejecutaron bien y cuáles fallaron. Esta fila es
    el componente atómico que la lista de tareas repite por cada tarea activa.

    Layout:
        [strip 4px] | [ícono] [nombre]  [pill-estado]  [botón acción?]
                      [barra de progreso — solo en estado "running"]
    """

    def __init__(
        self,
        parent,
        task_name: str,
        task_id: str,
        platform_url: str,
        on_manual_upload: Callable[[str, str], None] | None = None,
    ) -> None:
        """
        Args:
            parent: Widget padre (el frame scrollable del dashboard).
            task_name: Nombre legible de la tarea (para el contador).
            task_id: Identificador interno de la tarea.
            platform_url: URL de la plataforma (para botón "Abrir sitio").
            on_manual_upload: Callback(task_id, task_name). None = sin botón.
        """
        super().__init__(
            parent,
            corner_radius=10,
            fg_color=("white", "#1E2530"),
            border_width=0,
        )
        self._task_id = task_id
        self._task_name = task_name
        self._platform_url = platform_url
        self._on_manual_upload = on_manual_upload
        self._current_status = "pending"
        self._progress_bar: ctk.CTkProgressBar | None = None
        self._action_btn: ctk.CTkButton | None = None
        # Estado de progreso determinístico (wait_image_or_reload / wait_download_or_reload)
        self._elapsed_seconds: int = 0
        self._elapsed_after_id: str | None = None
        self._det_progress_bar: ctk.CTkProgressBar | None = None
        self._progress_det_label: ctk.CTkLabel | None = None
        self._progress_elapsed_label: ctk.CTkLabel | None = None

        self._build()

    def _build(self) -> None:
        """Construye el layout interno de la fila."""
        # Borde lateral de color (4px) — cambia según estado
        self._status_strip = ctk.CTkFrame(
            self, width=5, corner_radius=0,
            fg_color=_CIAF_GRAY,
        )
        self._status_strip.pack(side="left", fill="y")
        self._status_strip.pack_propagate(False)

        # Contenedor principal (a la derecha del strip)
        self._main = ctk.CTkFrame(self, fg_color="transparent")
        self._main.pack(side="left", fill="both", expand=True)
        self._main.columnconfigure(1, weight=1)

        # Fila superior: ícono · nombre · pill · botón
        self._icon_label = ctk.CTkLabel(
            self._main,
            text="◷",
            width=28,
            font=ctk.CTkFont(size=16),
            text_color=_CIAF_GRAY,
        )
        self._icon_label.grid(row=0, column=0, padx=(10, 4), pady=(10, 4))

        self._name_label = ctk.CTkLabel(
            self._main,
            text=self._task_name,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            anchor="w",
            text_color=("gray10", "gray90"),
        )
        self._name_label.grid(row=0, column=1, padx=4, pady=(10, 4), sticky="w")

        # Pill de estado
        self._pill = ctk.CTkLabel(
            self._main,
            text="Pendiente",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            corner_radius=10,
            fg_color=("#E8E8E9", "#3A3A3C"),
            text_color=(_CIAF_GRAY, "#AAAAAD"),
            padx=10, pady=2,
        )
        self._pill.grid(row=0, column=2, padx=8, pady=(10, 4))

        # Frame para botones de acción (columna 3)
        self._action_frame = ctk.CTkFrame(self._main, fg_color="transparent")
        self._action_frame.grid(row=0, column=3, padx=(0, 10), pady=(10, 4))

        # Fila inferior: barra de progreso (oculta por defecto)
        self._progress_row = ctk.CTkFrame(self._main, fg_color="transparent")
        self._progress_row.grid(
            row=1, column=0, columnspan=4,
            padx=(10, 10), pady=(0, 8), sticky="ew",
        )
        self._progress_row.columnconfigure(0, weight=1)

    @property
    def task_id(self) -> str:
        return self._task_id

    def update_status(self, status: str, message: str = "") -> None:
        """
        Actualiza el estado visual de la fila.

        Contrato público — firma no puede cambiar.

        Args:
            status: 'pending' | 'running' | 'done' | 'done_manual' | 'error' | 'progress'.
            message: Texto adicional visible al contador. Para 'progress' usa el
                formato "attempt|||max_retries|||descripción" (lo parsea internamente).
        """
        self._current_status = status

        # Estado transitorio de progreso (recargas en macros)
        if status == "progress":
            parts = message.split("|||", 2)
            try:
                attempt = int(parts[0]) if len(parts) > 0 else 1
                max_retries = int(parts[1]) if len(parts) > 1 else 1
            except ValueError:
                attempt, max_retries = 1, 1
            desc = parts[2] if len(parts) > 2 else message
            self._manage_progress_indicator(attempt, max_retries, desc)
            return

        # Al salir de "progress", limpiar indicador determinístico
        self._cleanup_progress_indicator()

        cfg = _STATUS_CONFIG.get(status, _STATUS_CONFIG["pending"])
        border_color = cfg["border_color"]

        # Strip de color lateral
        self._status_strip.configure(fg_color=border_color)

        # Ícono con color del estado
        self._icon_label.configure(
            text=cfg["icon"],
            text_color=border_color,
        )

        # Pill de estado
        pill_text = message if message else cfg["label"]
        self._pill.configure(
            text=pill_text,
            fg_color=cfg["pill_bg"],
            text_color=cfg["pill_fg"],
        )

        # Barra de progreso indeterminada (solo "running")
        self._manage_progress_bar(status)

        # Botón de acción (solo "error")
        self._manage_action_button(status)

    # ── Gestión de barra de progreso ───────────────────────────

    def _manage_progress_bar(self, status: str) -> None:
        """Muestra la barra indeterminada en 'running', la oculta en otros."""
        if status == "running":
            if self._progress_bar is None:
                self._progress_bar = ctk.CTkProgressBar(
                    self._progress_row,
                    mode="indeterminate",
                    height=3,
                    corner_radius=2,
                    progress_color=_CIAF_BLUE,
                    fg_color=("#D6E4F0", "#0A2A45"),
                )
                self._progress_bar.grid(row=0, column=0, sticky="ew")
            self._progress_bar.start()
        else:
            if self._progress_bar is not None:
                self._progress_bar.stop()
                self._progress_bar.destroy()
                self._progress_bar = None

    # ── Gestión de botón de acción ─────────────────────────────

    def _manage_action_button(self, status: str) -> None:
        """Muestra el botón 'Cargar archivo' solo en estado error."""
        # Destruir botón anterior en cualquier caso
        if self._action_btn is not None:
            self._action_btn.destroy()
            self._action_btn = None

        if status == "error" and self._on_manual_upload:
            self._action_btn = ctk.CTkButton(
                self._action_frame,
                text="Cargar archivo",
                width=120, height=28,
                font=ctk.CTkFont(family="Segoe UI", size=11),
                fg_color=_COLOR_ERROR,
                hover_color="#B02A37",
                corner_radius=6,
                command=self._handle_manual_upload,
            )
            self._action_btn.pack(side="left", padx=2)

    def _handle_manual_upload(self) -> None:
        """Llama al callback de carga manual."""
        if self._on_manual_upload:
            self._on_manual_upload(self._task_id, self._task_name)

    # ── Indicador de progreso determinístico (Plan D) ───────────

    def _manage_progress_indicator(
        self, attempt: int, max_retries: int, desc: str
    ) -> None:
        """
        Crea o actualiza el indicador de progreso para acciones de espera con recarga.

        Primera llamada: crea barra determinística + labels + timer elapsed.
        Llamadas siguientes: actualiza valor de barra y texto.
        Limpia la barra indeterminada de "running" si existía.
        """
        if self._det_progress_bar is None:
            # Limpiar barra indeterminada de "running" si existe
            self._manage_progress_bar("progress")
            # Header visual: strip + ícono + pill
            self._status_strip.configure(fg_color=_CIAF_BLUE)
            self._icon_label.configure(text="⟳", text_color=_CIAF_BLUE)
            self._pill.configure(
                text="Reintentando...",
                fg_color=("#D6E4F0", "#0A2A45"),
                text_color=(_CIAF_BLUE, "#5BA3D9"),
            )
            # Barra determinística
            self._det_progress_bar = ctk.CTkProgressBar(
                self._progress_row,
                mode="determinate",
                height=6,
                corner_radius=3,
                progress_color=_CIAF_BLUE,
                fg_color=("#D6E4F0", "#0A2A45"),
            )
            self._det_progress_bar.grid(
                row=0, column=0, columnspan=2, sticky="ew", pady=(0, 2)
            )
            # Label: "Intento X/N — desc"
            self._progress_det_label = ctk.CTkLabel(
                self._progress_row,
                text="",
                font=ctk.CTkFont(family="Segoe UI", size=10),
                text_color=(_CIAF_BLUE, "#5BA3D9"),
                anchor="w",
            )
            self._progress_det_label.grid(row=1, column=0, sticky="w")
            # Label elapsed
            self._progress_elapsed_label = ctk.CTkLabel(
                self._progress_row,
                text="0:00",
                font=ctk.CTkFont(family="Segoe UI", size=10),
                text_color=(_CIAF_GRAY, "#AAAAAD"),
                anchor="e",
            )
            self._progress_elapsed_label.grid(row=1, column=1, sticky="e")
            self._progress_row.columnconfigure(1, weight=0)
            # Iniciar contador de tiempo
            self._elapsed_seconds = 0
            self._tick_elapsed()

        # Actualizar valores
        self._det_progress_bar.set((attempt - 1) / max(max_retries, 1))
        self._progress_det_label.configure(
            text=f"Intento {attempt}/{max_retries} — {desc}"
        )

    def _cleanup_progress_indicator(self) -> None:
        """Destruye el indicador determinístico y cancela el timer elapsed."""
        if self._elapsed_after_id is not None:
            self.after_cancel(self._elapsed_after_id)
            self._elapsed_after_id = None
        for widget in (
            self._det_progress_bar,
            self._progress_det_label,
            self._progress_elapsed_label,
        ):
            if widget is not None:
                widget.destroy()
        self._det_progress_bar = None
        self._progress_det_label = None
        self._progress_elapsed_label = None

    def _tick_elapsed(self) -> None:
        """Incrementa y muestra el tiempo transcurrido desde el primer progreso."""
        if self._progress_elapsed_label is not None:
            mins, secs = divmod(self._elapsed_seconds, 60)
            self._progress_elapsed_label.configure(text=f"{mins}:{secs:02d}")
            self._elapsed_seconds += 1
            self._elapsed_after_id = self.after(1000, self._tick_elapsed)
