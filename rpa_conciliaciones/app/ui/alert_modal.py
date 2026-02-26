"""
Modal de error con opción de carga manual.

Por qué existe: Cuando un bot falla, el contador necesita saber qué pasó
en lenguaje simple y tener opciones claras: abrir el sitio para completar
la descarga manualmente, o cargar un archivo que ya tiene.

Rediseño v2.0: identidad visual CIAF — tarjeta flotante con padding generoso,
ícono de alerta prominente, jerarquía clara de botones (primario vs secundario
outline), detalle técnico colapsable para no abrumar al contador.

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

# ── Paleta CIAF ────────────────────────────────────────────────
_CIAF_BLUE   = "#0F4069"
_CIAF_GRAY   = "#8A8A8D"
_COLOR_ERROR = "#DC3545"


class AlertModal(ctk.CTkToplevel):
    """
    Modal que muestra el error de una tarea con opciones de acción.

    Por qué existe: Los errores de los bots deben comunicarse al contador
    en lenguaje de negocio, no técnico. Este modal ofrece alternativas
    claras: abrir el sitio web o cargar el archivo manualmente.

    Layout (card):
        Franja roja superior · ícono · título · descripción · detalle · botones
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
        self.title(f"No se pudo completar — {task_name}")
        self.geometry("500x360")
        self.resizable(False, False)
        self.grab_set()

        # Centrar sobre la ventana padre
        self.after(10, self._center_on_parent, parent)

        self._on_manual_upload = on_manual_upload
        self._detail_visible = False

        self._build(task_name, error_message, platform_url)

    # ── Construcción ────────────────────────────────────────────

    def _build(self, task_name: str, error_message: str, platform_url: str) -> None:
        """Construye el layout de card flotante."""
        # Franja de color en el tope (señal visual de error)
        accent_bar = ctk.CTkFrame(
            self, height=6, corner_radius=0, fg_color=_COLOR_ERROR,
        )
        accent_bar.pack(fill="x")

        # Contenedor principal con padding generoso
        card = ctk.CTkFrame(self, fg_color="transparent")
        card.pack(fill="both", expand=True, padx=30, pady=20)

        # Ícono + título en la misma línea
        title_row = ctk.CTkFrame(card, fg_color="transparent")
        title_row.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            title_row,
            text="⚠",
            font=ctk.CTkFont(size=26),
            text_color=_COLOR_ERROR,
            width=36,
        ).pack(side="left")

        ctk.CTkLabel(
            title_row,
            text=f"No se pudo descargar:\n{task_name}",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color=("gray10", "gray90"),
            justify="left",
            anchor="w",
        ).pack(side="left", padx=(10, 0))

        # Separador
        ctk.CTkFrame(
            card, height=1, corner_radius=0,
            fg_color=("gray85", "gray25"),
        ).pack(fill="x", pady=(0, 12))

        # Mensaje para el contador (sin tecnicismos)
        ctk.CTkLabel(
            card,
            text=(
                "Podés completar este paso manualmente:\n"
                "abrí el sitio web, descargá el archivo y cargalo acá."
            ),
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=("gray20", "gray80"),
            wraplength=430,
            justify="left",
        ).pack(anchor="w", pady=(0, 10))

        # Botón colapsable de detalle técnico (para el técnico de soporte)
        self._detail_btn = ctk.CTkButton(
            card,
            text="▾  Ver detalle técnico",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="transparent",
            hover_color=("gray92", "#2A3340"),
            text_color=_CIAF_GRAY,
            anchor="w",
            width=180, height=24,
            command=self._toggle_detail,
        )
        self._detail_btn.pack(anchor="w", pady=(0, 4))

        # Contenedor del detalle (oculto por defecto)
        self._detail_frame = ctk.CTkFrame(
            card,
            corner_radius=6,
            fg_color=("gray95", "#16202C"),
            border_width=1,
            border_color=("gray80", "gray30"),
        )
        self._detail_label = ctk.CTkLabel(
            self._detail_frame,
            text=error_message,
            font=ctk.CTkFont(family="Consolas", size=10),
            text_color=_CIAF_GRAY,
            wraplength=400,
            justify="left",
        )
        self._detail_label.pack(padx=10, pady=8, anchor="w")

        # ── Botones de acción ───────────────────────────────────
        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(fill="x", pady=(14, 0))

        # Primario: Abrir sitio web
        if platform_url:
            ctk.CTkButton(
                btn_row,
                text="Abrir sitio web",
                width=148, height=36,
                corner_radius=8,
                font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                fg_color=_CIAF_BLUE,
                hover_color="#0A2D50",
                command=lambda: webbrowser.open(platform_url),
            ).pack(side="left", padx=(0, 8))

        # Primario: Cargar archivo
        if on_manual_upload := self._on_manual_upload:
            ctk.CTkButton(
                btn_row,
                text="Cargar archivo",
                width=148, height=36,
                corner_radius=8,
                font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                fg_color=_CIAF_BLUE,
                hover_color="#0A2D50",
                command=self._handle_manual,
            ).pack(side="left", padx=(0, 8))

        # Secundario: Cerrar (outline sin relleno)
        ctk.CTkButton(
            btn_row,
            text="Cerrar",
            width=90, height=36,
            corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color="transparent",
            border_width=1,
            border_color=(_CIAF_GRAY, "gray40"),
            hover_color=("gray92", "#2A3340"),
            text_color=(_CIAF_GRAY, "gray70"),
            command=self.destroy,
        ).pack(side="right")

    # ── Handlers privados ───────────────────────────────────────

    def _toggle_detail(self) -> None:
        """Muestra / oculta el panel de detalle técnico."""
        if self._detail_visible:
            self._detail_frame.pack_forget()
            self._detail_btn.configure(text="▾  Ver detalle técnico")
        else:
            self._detail_frame.pack(fill="x", pady=(0, 8))
            self._detail_btn.configure(text="▴  Ocultar detalle")
        self._detail_visible = not self._detail_visible

    def _handle_manual(self) -> None:
        """Ejecuta el callback de carga manual y cierra el modal."""
        if self._on_manual_upload:
            self._on_manual_upload()
        self.destroy()

    def _center_on_parent(self, parent) -> None:
        """Centra el modal sobre la ventana padre."""
        try:
            px = parent.winfo_x() + (parent.winfo_width()  - 500) // 2
            py = parent.winfo_y() + (parent.winfo_height() - 360) // 2
            self.geometry(f"500x360+{px}+{py}")
        except Exception:
            pass
