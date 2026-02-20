"""
Modal de carga manual de archivos.

Por qué existe: Cuando el bot falla o la plataforma envía el archivo por email,
el contador necesita poder seleccionar un archivo de su computadora y subirlo
al servidor. Este modal guía el proceso paso a paso.

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
        self.geometry("450x240")
        self.resizable(False, False)
        self.grab_set()

        self._task_name = task_name
        self._on_file_selected = on_file_selected
        self._selected_path: Path | None = None

        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=16)

        # Instrucciones
        ctk.CTkLabel(
            container,
            text=(
                f"Seleccioná el archivo Excel o CSV que "
                f"descargaste de {task_name}"
            ),
            font=ctk.CTkFont(size=12),
            wraplength=400,
            justify="left",
        ).pack(anchor="w", pady=(0, 12))

        # Botón de selección + preview del nombre
        select_frame = ctk.CTkFrame(container, fg_color="transparent")
        select_frame.pack(fill="x", pady=(0, 8))

        ctk.CTkButton(
            select_frame, text="Seleccionar archivo",
            width=160,
            command=self._select_file,
        ).pack(side="left")

        self._file_label = ctk.CTkLabel(
            select_frame,
            text="Ningún archivo seleccionado",
            font=ctk.CTkFont(size=11),
            text_color="gray",
        )
        self._file_label.pack(side="left", padx=12)

        # Botones de acción
        btn_frame = ctk.CTkFrame(container, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(16, 0))

        self._upload_btn = ctk.CTkButton(
            btn_frame, text="Subir al servidor",
            width=140, state="disabled",
            command=self._handle_upload,
        )
        self._upload_btn.pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_frame, text="Cancelar",
            width=80, fg_color="gray",
            command=self.destroy,
        ).pack(side="right")

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
            text_color=("gray10", "gray90"),
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
                text_color="#F44336",
            )
            self._selected_path = None
            self._upload_btn.configure(state="disabled")
