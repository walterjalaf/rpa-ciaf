"""
Componente visual de estado por tarea en el dashboard.

Por qué existe: Cada tarea tiene una fila en la lista principal del dashboard.
Esta fila muestra el estado actual (pendiente, ejecutando, completado, error)
con íconos y colores que el contador entiende sin necesidad de leer logs.

Uso:
    row = TaskStatusRow(parent, task_name="Mercado Pago", task_id="mp_mov",
                        platform_url="https://...", on_manual_upload=callback)
    row.update_status("running", "Descargando...")
"""

from __future__ import annotations

import logging
import webbrowser
from collections.abc import Callable

import customtkinter as ctk

logger = logging.getLogger(__name__)

# ── Mapa de estados visuales ──────────────────────────────────
_STATUS_CONFIG = {
    "pending":     {"icon": "\u23f8",  "color": "gray",       "label": "Pendiente"},
    "running":     {"icon": "\u21bb",  "color": "#2196F3",    "label": "Ejecutando..."},
    "done":        {"icon": "\u2705",  "color": "#4CAF50",    "label": "Completado"},
    "done_manual": {"icon": "\U0001f4ce\u2705", "color": "#81C784", "label": "Cargado manualmente"},
    "error":       {"icon": "\u274c",  "color": "#F44336",    "label": "Error"},
}


class TaskStatusRow(ctk.CTkFrame):
    """
    Fila visual que muestra el estado de una tarea en el dashboard.

    Por qué existe: El contador necesita ver de un vistazo qué tareas están
    pendientes, cuáles se ejecutaron bien y cuáles fallaron. Esta fila es
    el componente atómico que la lista de tareas repite por cada tarea activa.

    Layout: [icono] [nombre de tarea] [mensaje de estado] [botón acción]
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
            task_name: Nombre legible de la tarea.
            task_id: Identificador de la tarea.
            platform_url: URL de la plataforma (para el botón "Abrir sitio").
            on_manual_upload: Callback(task_id, task_name) al presionar
                "Cargar archivo". None si no se quiere mostrar el botón.
        """
        super().__init__(parent, corner_radius=8, fg_color="transparent")
        self._task_id = task_id
        self._task_name = task_name
        self._platform_url = platform_url
        self._on_manual_upload = on_manual_upload
        self._current_status = "pending"

        self.grid_columnconfigure(2, weight=1)

        # Icono de estado
        self._icon_label = ctk.CTkLabel(
            self, text="\u23f8", width=30,
            font=ctk.CTkFont(size=16),
        )
        self._icon_label.grid(row=0, column=0, padx=(8, 4), pady=8)

        # Nombre de la tarea
        self._name_label = ctk.CTkLabel(
            self, text=task_name,
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
        )
        self._name_label.grid(row=0, column=1, padx=(4, 8), pady=8, sticky="w")

        # Mensaje de estado
        self._status_label = ctk.CTkLabel(
            self, text="Pendiente",
            font=ctk.CTkFont(size=12),
            text_color="gray", anchor="w",
        )
        self._status_label.grid(row=0, column=2, padx=8, pady=8, sticky="w")

        # Frame para botones de acción
        self._action_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._action_frame.grid(row=0, column=3, padx=8, pady=4)

        self._action_btn: ctk.CTkButton | None = None

    @property
    def task_id(self) -> str:
        return self._task_id

    def update_status(self, status: str, message: str = "") -> None:
        """
        Actualiza el estado visual de la fila.

        Args:
            status: Uno de 'pending', 'running', 'done', 'done_manual', 'error'.
            message: Mensaje adicional para mostrar junto al estado.
        """
        self._current_status = status
        config = _STATUS_CONFIG.get(status, _STATUS_CONFIG["pending"])

        self._icon_label.configure(text=config["icon"])
        display_msg = message if message else config["label"]
        self._status_label.configure(
            text=display_msg, text_color=config["color"]
        )

        # Limpiar botón anterior
        if self._action_btn is not None:
            self._action_btn.destroy()
            self._action_btn = None

        # Mostrar botón de carga manual en estado error
        if status == "error" and self._on_manual_upload:
            self._action_btn = ctk.CTkButton(
                self._action_frame,
                text="Cargar archivo",
                width=120, height=28,
                font=ctk.CTkFont(size=11),
                command=self._handle_manual_upload,
            )
            self._action_btn.pack(side="left", padx=2)

    def _handle_manual_upload(self) -> None:
        """Llama al callback de carga manual."""
        if self._on_manual_upload:
            self._on_manual_upload(self._task_id, self._task_name)
