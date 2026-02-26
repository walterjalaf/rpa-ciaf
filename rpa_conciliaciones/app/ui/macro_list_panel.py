"""
Panel de lista y gestión de macros guardadas.

Por qué existe: Permite al técnico ver, probar, eliminar y publicar
las macros grabadas con MacroRecorderPanel. Muestra cada macro como
una card con nombre, task_id, fecha de creación y versión.

Controles por macro:
    ▶ Probar   → ejecuta la macro con DateResolver.resolve('yesterday')
    📤 Publicar → llama al callback on_publish (MacroSync.upload_macro)
    Eliminar   → borra el JSON del storage local

Rediseño v2.0: identidad visual CIAF — cada macro es una card con borde
izquierdo azul CIAF, pill de cantidad de acciones, botones con jerarquía
primario / destructivo.

Uso:
    panel = MacroListPanel(parent, storage,
                           on_test_macro=runner.run_macro_test,
                           on_publish=macro_sync.upload_macro)
    panel.refresh()
"""

from __future__ import annotations

import logging
from collections.abc import Callable

import customtkinter as ctk

from macros.models import Recording
from macros.storage import MacroStorage

logger = logging.getLogger(__name__)

# ── Paleta CIAF ────────────────────────────────────────────────
_CIAF_BLUE       = "#0F4069"
_CIAF_BLUE_HOVER = "#0A2D50"
_CIAF_GRAY       = "#8A8A8D"
_COLOR_OK        = "#28A745"
_COLOR_OK_HOVER  = "#1E7E34"
_COLOR_ERROR     = "#DC3545"
_COLOR_ERROR_HOV = "#C82333"


class MacroListPanel(ctk.CTkFrame):
    """
    Lista scrollable de macros guardadas con controles de gestión.

    Por qué existe: Centraliza la gestión de macros en un componente
    reutilizable. El técnico puede ver el estado de todas sus macros
    y realizar acciones sin ir a la carpeta de AppData.

    Callbacks:
        on_test_macro: Llamado con (recording: Recording) al presionar "▶ Probar".
        on_publish:    Llamado con (recording: Recording) al presionar "Publicar".
    """

    def __init__(
        self,
        parent: ctk.CTkFrame,
        storage: MacroStorage,
        on_test_macro: Callable[[Recording], None] | None = None,
        on_publish: Callable[[Recording], None] | None = None,
    ) -> None:
        super().__init__(
            parent,
            corner_radius=12,
            fg_color=("white", "#1E2530"),
        )
        self._storage       = storage
        self._on_test_macro = on_test_macro
        self._on_publish    = on_publish

        self._build_header()
        self._build_list_area()
        self.refresh()

    def refresh(self, _recording: Recording | None = None) -> None:
        """
        Recarga la lista desde MacroStorage y actualiza el panel.

        Acepta un argumento opcional (Recording) para ser compatible
        con el callback on_saved del MacroRecorderPanel.
        """
        self._rebuild_list()

    # ══════════════════════════════════════════════════════════
    # Construcción
    # ══════════════════════════════════════════════════════════

    def _build_header(self) -> None:
        """Header con título, contador y botón de actualizar."""
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(12, 6))

        ctk.CTkLabel(
            header,
            text="Macros guardadas",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=("gray10", "gray90"),
        ).pack(side="left")

        # Botón actualizar — outline secundario
        ctk.CTkButton(
            header,
            text="↻  Actualizar",
            width=96, height=28,
            corner_radius=6,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="transparent",
            border_width=1,
            border_color=(_CIAF_BLUE, "#5BA3D9"),
            hover_color=("gray92", "#2A3340"),
            text_color=(_CIAF_BLUE, "#5BA3D9"),
            command=self.refresh,
        ).pack(side="right")

        # Separador
        ctk.CTkFrame(
            self, height=1, corner_radius=0,
            fg_color=("gray85", "gray25"),
        ).pack(fill="x", padx=16)

    def _build_list_area(self) -> None:
        """Frame scrollable donde se renderizan las cards de macros."""
        self._scroll_frame = ctk.CTkScrollableFrame(
            self,
            height=200,
            fg_color="transparent",
            scrollbar_button_color=(_CIAF_GRAY, "gray35"),
        )
        self._scroll_frame.pack(fill="x", padx=12, pady=(6, 12))

    def _rebuild_list(self) -> None:
        """Limpia y repopula el frame scrollable con las macros actuales."""
        for widget in self._scroll_frame.winfo_children():
            widget.destroy()

        macros = self._storage.list_all()

        if not macros:
            ctk.CTkLabel(
                self._scroll_frame,
                text="No hay macros guardadas.\nUsá el panel de grabación para crear una.",
                font=ctk.CTkFont(family="Segoe UI", size=11),
                text_color=_CIAF_GRAY,
                justify="center",
            ).pack(pady=24)
            return

        for recording in macros:
            self._build_macro_card(recording)

    def _build_macro_card(self, recording: Recording) -> None:
        """
        Renderiza una card con info y controles para una macro.

        Layout:
            [strip 4px CIAF] | [nombre + detalles]          [pill acciones]
                               [botones: Probar / Publicar / Eliminar]
        """
        # Contenedor externo de la card
        card = ctk.CTkFrame(
            self._scroll_frame,
            corner_radius=10,
            fg_color=("white", "#1A2535"),
            border_width=1,
            border_color=("gray85", "gray25"),
        )
        card.pack(fill="x", pady=(0, 6))

        # Borde izquierdo CIAF (strip de 4px)
        strip = ctk.CTkFrame(
            card, width=5, corner_radius=0, fg_color=_CIAF_BLUE,
        )
        strip.pack(side="left", fill="y")
        strip.pack_propagate(False)

        # Cuerpo de la card
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(side="left", fill="both", expand=True,
                  padx=(10, 12), pady=10)

        # ── Fila superior: nombre + pill ────────────────────
        top_row = ctk.CTkFrame(body, fg_color="transparent")
        top_row.pack(fill="x")

        ctk.CTkLabel(
            top_row,
            text=recording.macro_name,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=("gray10", "gray90"),
            anchor="w",
        ).pack(side="left")

        # Pill con cantidad de acciones
        ctk.CTkLabel(
            top_row,
            text=f"{len(recording.actions)} acciones",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            corner_radius=10,
            fg_color=("#D6E4F0", "#0A2A45"),
            text_color=(_CIAF_BLUE, "#5BA3D9"),
            padx=8, pady=2,
        ).pack(side="right")

        # ── Fila de metadatos ───────────────────────────────
        fecha   = recording.created_at.strftime("%d/%m/%Y  %H:%M")
        task_id = recording.task_id or "—"
        ctk.CTkLabel(
            body,
            text=f"task_id: {task_id}   ·   v{recording.version}   ·   {fecha}",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=_CIAF_GRAY,
            anchor="w",
        ).pack(anchor="w", pady=(2, 8))

        # ── Botones de acción ───────────────────────────────
        btn_row = ctk.CTkFrame(body, fg_color="transparent")
        btn_row.pack(anchor="w")

        if self._on_test_macro:
            ctk.CTkButton(
                btn_row,
                text="▶  Probar",
                width=90, height=30,
                corner_radius=6,
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                fg_color=_COLOR_OK,
                hover_color=_COLOR_OK_HOVER,
                command=lambda r=recording: self._test_macro(r),
            ).pack(side="left", padx=(0, 6))

        if self._on_publish:
            ctk.CTkButton(
                btn_row,
                text="📤  Publicar",
                width=96, height=30,
                corner_radius=6,
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                fg_color=_CIAF_BLUE,
                hover_color=_CIAF_BLUE_HOVER,
                command=lambda r=recording: self._publish_macro(r),
            ).pack(side="left", padx=(0, 6))

        # Eliminar — outline destructivo
        ctk.CTkButton(
            btn_row,
            text="Eliminar",
            width=84, height=30,
            corner_radius=6,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="transparent",
            border_width=1,
            border_color=(_COLOR_ERROR, _COLOR_ERROR),
            hover_color=("gray92", "#2A3340"),
            text_color=(_COLOR_ERROR, "#E87070"),
            command=lambda r=recording: self._delete_macro(r),
        ).pack(side="left")

    # ══════════════════════════════════════════════════════════
    # Handlers
    # ══════════════════════════════════════════════════════════

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
