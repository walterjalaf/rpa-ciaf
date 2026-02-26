"""
Modal de carga manual de archivos.

Por qué existe: Cuando el bot falla o la plataforma envía el archivo por email,
el contador necesita poder seleccionar un archivo de su computadora y subirlo
al servidor. Este modal guía el proceso paso a paso.

Rediseño v2.0: identidad visual CIAF — tarjeta flotante limpia con zona de
selección destacada, botón primario CIAF azul y botón "Cancelar" como outline
secundario sin relleno sólido.

Uso:
    modal = ManualUploadModal(parent, task_name="Mercado Pago",
                               on_file_selected=callback)
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

logger = logging.getLogger(__name__)

# ── Paleta CIAF ────────────────────────────────────────────────
_CIAF_BLUE   = "#0F4069"
_CIAF_GRAY   = "#8A8A8D"
_COLOR_OK    = "#28A745"
_COLOR_ERROR = "#DC3545"


class ManualUploadModal(ctk.CTkToplevel):
    """
    Modal para que el contador seleccione y suba un archivo manualmente.

    Por qué existe: Es el fallback universal del sistema. Cubre dos casos:
    1. La plataforma tiene delivery="email" y no hay descarga automática.
    2. El bot falló y el contador descargó el archivo a mano.

    Uso:
        ManualUploadModal(parent, "Mercado Pago", on_file_selected=callback)
    """

    def __init__(
        self,
        parent,
        task_name: str,
        on_file_selected: Callable[[Path], None],
    ) -> None:
        super().__init__(parent)
        self.title(f"Cargar archivo — {task_name}")
        self.geometry("480x280")
        self.resizable(False, False)
        self.grab_set()

        # Centrar sobre la ventana padre
        self.after(10, self._center_on_parent, parent)

        self._task_name = task_name
        self._on_file_selected = on_file_selected
        self._selected_path: Path | None = None

        self._build()

    # ── Construcción ────────────────────────────────────────────

    def _build(self) -> None:
        """Construye el layout de card limpia."""
        # Franja azul CIAF en el tope
        ctk.CTkFrame(
            self, height=6, corner_radius=0, fg_color=_CIAF_BLUE,
        ).pack(fill="x")

        # Contenedor principal con padding generoso
        card = ctk.CTkFrame(self, fg_color="transparent")
        card.pack(fill="both", expand=True, padx=30, pady=20)

        # Título con ícono
        title_row = ctk.CTkFrame(card, fg_color="transparent")
        title_row.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            title_row,
            text="📂",
            font=ctk.CTkFont(size=22),
            width=32,
        ).pack(side="left")

        ctk.CTkLabel(
            title_row,
            text=f"Cargar archivo — {self._task_name}",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color=("gray10", "gray90"),
            anchor="w",
        ).pack(side="left", padx=(10, 0))

        # Separador
        ctk.CTkFrame(
            card, height=1, corner_radius=0,
            fg_color=("gray85", "gray25"),
        ).pack(fill="x", pady=(0, 14))

        # Instrucción
        ctk.CTkLabel(
            card,
            text=f"Seleccioná el archivo Excel o CSV que descargaste de {self._task_name}.",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=("gray20", "gray80"),
            wraplength=410,
            justify="left",
        ).pack(anchor="w", pady=(0, 14))

        # Zona de selección de archivo
        select_row = ctk.CTkFrame(
            card,
            corner_radius=8,
            fg_color=("#F4F8FB", "#16202C"),
            border_width=1,
            border_color=("gray80", "gray30"),
        )
        select_row.pack(fill="x", pady=(0, 6))

        ctk.CTkButton(
            select_row,
            text="Seleccionar archivo",
            width=160, height=34,
            corner_radius=6,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color=_CIAF_BLUE,
            hover_color="#0A2D50",
            command=self._select_file,
        ).pack(side="left", padx=10, pady=10)

        self._file_label = ctk.CTkLabel(
            select_row,
            text="Ningún archivo seleccionado",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=_CIAF_GRAY,
            anchor="w",
        )
        self._file_label.pack(side="left", padx=(0, 10), fill="x", expand=True)

        # ── Botones de acción ───────────────────────────────────
        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(fill="x", pady=(14, 0))

        # Primario: Subir al servidor (deshabilitado hasta elegir archivo)
        self._upload_btn = ctk.CTkButton(
            btn_row,
            text="Subir al servidor",
            width=160, height=36,
            corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color=_CIAF_BLUE,
            hover_color="#0A2D50",
            state="disabled",
            command=self._handle_upload,
        )
        self._upload_btn.pack(side="left", padx=(0, 8))

        # Secundario: Cancelar (outline sin relleno)
        ctk.CTkButton(
            btn_row,
            text="Cancelar",
            width=100, height=36,
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

    def _select_file(self) -> None:
        """Abre el diálogo de selección de archivos del sistema."""
        selected = filedialog.askopenfilename(
            title=f"Seleccionar archivo — {self._task_name}",
            filetypes=[
                ("Excel y CSV", "*.xlsx *.csv"),
                ("Todos los archivos", "*.*"),
            ],
        )
        if not selected:
            return

        self._selected_path = Path(selected)
        self._file_label.configure(
            text=self._selected_path.name,
            text_color=(_COLOR_OK, "#5CB87A"),
        )
        self._upload_btn.configure(state="normal")
        logger.debug("Archivo seleccionado: %s", self._selected_path)

    def _handle_upload(self) -> None:
        """Ejecuta el callback con el archivo seleccionado y cierra."""
        if self._selected_path and self._selected_path.exists():
            self._on_file_selected(self._selected_path)
            self.destroy()
        else:
            self._file_label.configure(
                text="El archivo ya no existe. Seleccioná otro.",
                text_color=_COLOR_ERROR,
            )
            self._selected_path = None
            self._upload_btn.configure(state="disabled")

    def _center_on_parent(self, parent) -> None:
        """Centra el modal sobre la ventana padre."""
        try:
            px = parent.winfo_x() + (parent.winfo_width()  - 480) // 2
            py = parent.winfo_y() + (parent.winfo_height() - 280) // 2
            self.geometry(f"480x280+{px}+{py}")
        except Exception:
            pass
