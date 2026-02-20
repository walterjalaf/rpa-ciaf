"""
Panel de estado de sesiones (health check) en el dashboard.

Por qué existe: Muestra al contador el resultado del pre-flight check de
sesiones. Cada plataforma aparece con un indicador verde (sesión activa) o
rojo (necesita login), y un botón para abrir el sitio web si necesita loguearse.

Uso:
    panel = SessionPanel(parent)
    panel.update_results(session_results)
"""

from __future__ import annotations

import logging
import webbrowser

import customtkinter as ctk

logger = logging.getLogger(__name__)


class SessionPanel(ctk.CTkFrame):
    """
    Panel que muestra el estado de sesión de cada plataforma.

    Por qué existe: El contador necesita saber si sus sesiones bancarias
    están activas antes de ejecutar los bots. Este panel muestra el resultado
    del health check y le permite abrir las plataformas que necesitan login.

    Uso:
        panel = SessionPanel(parent)
        panel.update_results(results)  # list[SessionStatus]
    """

    def __init__(self, parent, **kwargs) -> None:
        super().__init__(parent, **kwargs)
        self._rows: dict[str, ctk.CTkFrame] = {}

        self._title = ctk.CTkLabel(
            self, text="Estado de sesiones",
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self._title.pack(anchor="w", padx=12, pady=(8, 4))

        self._content = ctk.CTkFrame(self, fg_color="transparent")
        self._content.pack(fill="x", padx=12, pady=(0, 8))

        self._status_label = ctk.CTkLabel(
            self._content,
            text="Verificando sesiones...",
            font=ctk.CTkFont(size=12),
            text_color="gray",
        )
        self._status_label.pack(anchor="w")

    def update_results(self, results: list) -> None:
        """
        Actualiza el panel con los resultados del health check.

        Args:
            results: Lista de SessionStatus del HealthChecker.
        """
        # Limpiar contenido anterior
        for widget in self._content.winfo_children():
            widget.destroy()
        self._rows.clear()

        if not results:
            lbl = ctk.CTkLabel(
                self._content,
                text="No hay tareas configuradas",
                font=ctk.CTkFont(size=12),
                text_color="gray",
            )
            lbl.pack(anchor="w")
            return

        active = sum(1 for r in results if r.is_logged_in)
        total = len(results)

        summary = ctk.CTkLabel(
            self._content,
            text=f"{active}/{total} sesiones activas",
            font=ctk.CTkFont(size=12),
            text_color="#4CAF50" if active == total else "#FF9800",
        )
        summary.pack(anchor="w", pady=(0, 4))

        for result in results:
            row = self._create_session_row(result)
            row.pack(fill="x", pady=1)
            self._rows[result.task_id] = row

    def _create_session_row(self, result) -> ctk.CTkFrame:
        """Crea una fila para un resultado de sesión."""
        row = ctk.CTkFrame(self._content, fg_color="transparent", height=28)
        row.grid_columnconfigure(1, weight=1)

        icon = "\u2705" if result.is_logged_in else "\u274c"
        color = "#4CAF50" if result.is_logged_in else "#F44336"

        icon_lbl = ctk.CTkLabel(
            row, text=icon, width=24, font=ctk.CTkFont(size=12),
        )
        icon_lbl.grid(row=0, column=0, padx=(0, 4))

        name_lbl = ctk.CTkLabel(
            row, text=result.task_name,
            font=ctk.CTkFont(size=11), anchor="w",
        )
        name_lbl.grid(row=0, column=1, sticky="w")

        if not result.is_logged_in and result.platform_url:
            btn = ctk.CTkButton(
                row, text="Abrir sitio",
                width=80, height=24,
                font=ctk.CTkFont(size=10),
                command=lambda url=result.platform_url: webbrowser.open(url),
            )
            btn.grid(row=0, column=2, padx=4)

        if result.error:
            err_lbl = ctk.CTkLabel(
                row, text=f"({result.error[:40]})",
                font=ctk.CTkFont(size=10),
                text_color="gray",
            )
            err_lbl.grid(row=0, column=3, padx=4)

        return row
