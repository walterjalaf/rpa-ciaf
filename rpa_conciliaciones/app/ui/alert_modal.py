"""
Modal de error con opción de carga manual.

Por qué existe: Cuando un bot falla, el contador necesita saber qué pasó
en lenguaje simple y tener opciones claras: abrir el sitio para completar
la descarga manualmente, o cargar un archivo que ya tiene.

Uso:
    modal = AlertModal(parent, task_name="Mercado Pago",
                       error_message="Timeout en descarga",
                       platform_url="https://...",
                       on_manual_upload=callback)
"""

from __future__ import annotations

import logging
import webbrowser
from collections.abc import Callable

import customtkinter as ctk

logger = logging.getLogger(__name__)


class AlertModal(ctk.CTkToplevel):
    """
    Modal que muestra el error de una tarea con opciones de acción.

    Por qué existe: Los errores de los bots deben comunicarse al contador
    en lenguaje de negocio, no técnico. Este modal ofrece alternativas
    claras: abrir el sitio web o cargar el archivo manualmente.

    Uso:
        AlertModal(parent, "Mercado Pago", "Error técnico", url, callback)
    """

    def __init__(
        self,
        parent,
        task_name: str,
        error_message: str,
        platform_url: str,
        on_manual_upload: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.title(f"Error — {task_name}")
        self.geometry("480x320")
        self.resizable(False, False)
        self.grab_set()

        self._on_manual_upload = on_manual_upload

        # Contenedor principal
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=16)

        # Ícono y título
        title = ctk.CTkLabel(
            container,
            text=f"\u26a0\ufe0f  No se pudo descargar: {task_name}",
            font=ctk.CTkFont(size=15, weight="bold"),
            wraplength=420,
        )
        title.pack(anchor="w", pady=(0, 8))

        # Mensaje para el contador
        msg = ctk.CTkLabel(
            container,
            text=(
                "Podés completar este paso manualmente: "
                "abrí el sitio web, descargá el archivo, y cargalo acá."
            ),
            font=ctk.CTkFont(size=12),
            wraplength=420,
            justify="left",
        )
        msg.pack(anchor="w", pady=(0, 12))

        # Detalle técnico colapsable
        self._detail_visible = False
        self._detail_btn = ctk.CTkButton(
            container, text="Ver detalle técnico \u25bc",
            width=160, height=26,
            font=ctk.CTkFont(size=11),
            fg_color="transparent",
            text_color="gray",
            hover_color=("gray90", "gray20"),
            command=self._toggle_detail,
        )
        self._detail_btn.pack(anchor="w", pady=(0, 4))

        self._detail_label = ctk.CTkLabel(
            container,
            text=error_message,
            font=ctk.CTkFont(size=10, family="Consolas"),
            text_color="gray",
            wraplength=420,
            justify="left",
        )

        # Botones de acción
        btn_frame = ctk.CTkFrame(container, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(12, 0))

        if platform_url:
            ctk.CTkButton(
                btn_frame, text="Abrir sitio web",
                width=140,
                command=lambda: webbrowser.open(platform_url),
            ).pack(side="left", padx=(0, 8))

        if on_manual_upload:
            ctk.CTkButton(
                btn_frame, text="Cargar archivo",
                width=140,
                command=self._handle_manual,
            ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_frame, text="Cerrar",
            width=80,
            fg_color="gray",
            command=self.destroy,
        ).pack(side="right")

    def _toggle_detail(self) -> None:
        """Muestra/oculta el detalle técnico del error."""
        if self._detail_visible:
            self._detail_label.pack_forget()
            self._detail_btn.configure(text="Ver detalle técnico \u25bc")
        else:
            self._detail_label.pack(anchor="w", pady=(0, 4))
            self._detail_btn.configure(text="Ocultar detalle \u25b2")
        self._detail_visible = not self._detail_visible

    def _handle_manual(self) -> None:
        """Ejecuta el callback de carga manual y cierra el modal."""
        if self._on_manual_upload:
            self._on_manual_upload()
        self.destroy()
