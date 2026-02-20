"""
Panel de lista y gestión de macros guardadas.

Por qué existe: Permite al técnico ver, probar, eliminar y publicar
las macros grabadas con MacroRecorderPanel. Muestra cada macro con
su nombre, task_id, fecha de creación y versión.

Controles por macro:
    ▶ Probar   → ejecuta la macro con DateResolver.resolve('yesterday')
    🗑 Eliminar → borra el JSON del storage local
    📤 Publicar → llama al callback on_publish (MacroSync.upload_macro)

Uso:
    panel = MacroListPanel(parent, storage,
                           on_test_macro=runner.run_macro_test,
                           on_publish=macro_sync.upload_macro)
    panel.refresh()
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date

import customtkinter as ctk

from macros.models import Recording
from macros.storage import MacroStorage

logger = logging.getLogger(__name__)


class MacroListPanel(ctk.CTkFrame):
    """
    Lista scrollable de macros guardadas con controles de gestión.

    Por qué existe: Centraliza la gestión de macros en un componente
    reutilizable. El técnico puede ver el estado de todas sus macros
    y realizar acciones sin ir a la carpeta de AppData.

    Callbacks:
        on_test_macro: Llamado con (recording: Recording) al presionar "▶ Probar".
            El caller (generalmente main.py) ejecuta la macro con fecha de ayer.
        on_publish: Llamado con (recording: Recording) al presionar "📤 Publicar".
            Generalmente apunta a MacroSync.upload_macro().
    """

    def __init__(
        self,
        parent: ctk.CTkFrame,
        storage: MacroStorage,
        on_test_macro: Callable[[Recording], None] | None = None,
        on_publish: Callable[[Recording], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self._storage = storage
        self._on_test_macro = on_test_macro
        self._on_publish = on_publish

        self._build_header()
        self._build_list_area()
        self.refresh()

    def refresh(self, _recording: Recording | None = None) -> None:
        """
        Recarga la lista desde MacroStorage y actualiza el panel.

        Acepta un argumento opcional (Recording) para ser compatible
        con el callback on_saved del MacroRecorderPanel que pasa la
        macro recién guardada.
        """
        self._rebuild_list()

    # ── Construcción ────────────────────────────────────────────────────

    def _build_header(self) -> None:
        """Header con título y botón de actualizar."""
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=8, pady=(8, 4))

        ctk.CTkLabel(
            header, text="Macros guardadas",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(side="left")

        ctk.CTkButton(
            header, text="↻ Actualizar",
            width=90, height=26,
            font=ctk.CTkFont(size=11),
            command=self.refresh,
        ).pack(side="right")

    def _build_list_area(self) -> None:
        """Frame scrollable donde se renderizan las filas de macros."""
        self._scroll_frame = ctk.CTkScrollableFrame(self, height=180)
        self._scroll_frame.pack(fill="x", padx=8, pady=(0, 8))

        self._empty_label = ctk.CTkLabel(
            self._scroll_frame,
            text="No hay macros guardadas. Usa el panel de grabación para crear una.",
            font=ctk.CTkFont(size=11),
            text_color="gray",
        )

    def _rebuild_list(self) -> None:
        """Limpia y repopula el frame scrollable con las macros actuales."""
        for widget in self._scroll_frame.winfo_children():
            widget.destroy()

        macros = self._storage.list_all()

        if not macros:
            self._empty_label = ctk.CTkLabel(
                self._scroll_frame,
                text="No hay macros guardadas. Usa el panel de grabación para crear una.",
                font=ctk.CTkFont(size=11),
                text_color="gray",
            )
            self._empty_label.pack(pady=20)
            return

        for recording in macros:
            self._build_macro_row(recording)

    def _build_macro_row(self, recording: Recording) -> None:
        """Renderiza una fila con info y controles para una macro."""
        row = ctk.CTkFrame(
            self._scroll_frame,
            corner_radius=6, border_width=1,
            border_color=("gray80", "gray30"),
        )
        row.pack(fill="x", pady=3)

        # Info de la macro
        info_frame = ctk.CTkFrame(row, fg_color="transparent")
        info_frame.pack(side="left", fill="x", expand=True, padx=8, pady=6)

        ctk.CTkLabel(
            info_frame,
            text=recording.macro_name,
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w",
        ).pack(anchor="w")

        fecha = recording.created_at.strftime("%d/%m/%Y %H:%M")
        details = (
            f"task_id: {recording.task_id or '—'}  |  "
            f"v{recording.version}  |  "
            f"{len(recording.actions)} acciones  |  "
            f"grabada: {fecha}"
        )
        ctk.CTkLabel(
            info_frame,
            text=details,
            font=ctk.CTkFont(size=10),
            text_color="gray",
            anchor="w",
        ).pack(anchor="w")

        # Botones de acción
        btn_frame = ctk.CTkFrame(row, fg_color="transparent")
        btn_frame.pack(side="right", padx=8, pady=6)

        if self._on_test_macro:
            ctk.CTkButton(
                btn_frame, text="▶ Probar",
                width=80, height=28,
                font=ctk.CTkFont(size=11),
                fg_color="#28a745", hover_color="#1e7e34",
                command=lambda r=recording: self._test_macro(r),
            ).pack(side="left", padx=2)

        if self._on_publish:
            ctk.CTkButton(
                btn_frame, text="📤 Publicar",
                width=88, height=28,
                font=ctk.CTkFont(size=11),
                command=lambda r=recording: self._publish_macro(r),
            ).pack(side="left", padx=2)

        ctk.CTkButton(
            btn_frame, text="🗑 Eliminar",
            width=80, height=28,
            font=ctk.CTkFont(size=11),
            fg_color="#dc3545", hover_color="#c82333",
            command=lambda r=recording: self._delete_macro(r),
        ).pack(side="left", padx=2)

    # ── Handlers ────────────────────────────────────────────────────────

    def _test_macro(self, recording: Recording) -> None:
        """Ejecuta la macro en modo prueba con la fecha de ayer."""
        logger.info("Iniciando prueba de macro: %s", recording.macro_name)
        if self._on_test_macro:
            self._on_test_macro(recording)

    def _publish_macro(self, recording: Recording) -> None:
        """Publica la macro al servidor via MacroSync."""
        logger.info("Publicando macro: %s", recording.macro_name)
        if self._on_publish:
            self._on_publish(recording)

    def _delete_macro(self, recording: Recording) -> None:
        """Elimina la macro del storage local y refresca la lista."""
        self._storage.delete(recording.macro_id)
        logger.info("Macro eliminada: %s (%s)", recording.macro_name, recording.macro_id)
        self.refresh()
