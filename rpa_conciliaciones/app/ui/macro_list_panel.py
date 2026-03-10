"""
Panel de lista y gestión de macros guardadas.

Por qué existe: Permite al técnico ver, probar, eliminar y publicar
las macros grabadas con MacroRecorderPanel. Muestra cada macro como
una card horizontal con nombre, metadatos, contador de acciones y
botones de acción alineados a la derecha.

Rediseño v3.0: card horizontal de ancho completo.
    [strip CIAF] | [nombre + metadatos — flex] | [N acciones] | [botones]

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

_BTN_W = 114
_BTN_H = 30


class MacroListPanel(ctk.CTkFrame):
    """
    Lista scrollable de macros guardadas con controles de gestión.

    Por qué existe: Centraliza la gestión de macros en un componente
    reutilizable que ocupa el ancho completo de la tab. Cada macro se
    muestra como una fila horizontal con info a la izquierda, contador
    de acciones en el centro y botones de acción a la derecha.

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
            corner_radius=0,
            fg_color="transparent",
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
        """Header con título y botón de actualizar."""
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(10, 6))

        ctk.CTkLabel(
            header,
            text="Macros guardadas",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=("gray10", "gray90"),
        ).pack(side="left")

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

        ctk.CTkFrame(
            self, height=1, corner_radius=0,
            fg_color=("gray85", "gray25"),
        ).pack(fill="x", padx=16)

    def _build_list_area(self) -> None:
        """Frame scrollable que ocupa todo el espacio vertical disponible."""
        self._scroll_frame = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            scrollbar_button_color=(_CIAF_GRAY, "gray35"),
        )
        self._scroll_frame.pack(fill="both", expand=True, padx=8, pady=(6, 8))
        self._scroll_frame.columnconfigure(0, weight=1)

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
            ).pack(pady=32)
            return

        for recording in macros:
            self._build_macro_card(recording)

    def _build_macro_card(self, recording: Recording) -> None:
        """
        Renderiza una card horizontal de ancho completo para una macro.

        Layout (izquierda → derecha):
            [strip 5px CIAF] | [nombre + metadatos — flex] |
            [contador de acciones] | [botones verticales]
        """
        card = ctk.CTkFrame(
            self._scroll_frame,
            corner_radius=10,
            fg_color=("white", "#1A2535"),
            border_width=1,
            border_color=("gray85", "gray25"),
        )
        card.pack(fill="x", pady=(0, 8))

        # Borde izquierdo CIAF
        strip = ctk.CTkFrame(card, width=5, corner_radius=0, fg_color=_CIAF_BLUE)
        strip.pack(side="left", fill="y")
        strip.pack_propagate(False)

        # Cuerpo principal
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(side="left", fill="both", expand=True, padx=(16, 16), pady=14)

        # ── Botones (empacados primero → quedan a la derecha) ──
        self._build_card_buttons(body, recording)

        # ── Contador de acciones ──
        self._build_card_stats(body, recording)

        # ── Info (nombre + metadatos, llena el espacio restante) ──
        self._build_card_info(body, recording)

    def _build_card_info(self, body: ctk.CTkFrame, recording: Recording) -> None:
        """Columna izquierda: nombre en negrita y metadatos en gris."""
        info = ctk.CTkFrame(body, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True)

        ctk.CTkLabel(
            info,
            text=recording.macro_name,
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color=("gray10", "gray90"),
            anchor="w",
        ).pack(anchor="w")

        fecha   = recording.created_at.strftime("%d/%m/%Y  %H:%M")
        task_id = recording.task_id or "—"
        meta    = f"task: {task_id}   ·   {fecha}   ·   v{recording.version}"

        ctk.CTkLabel(
            info,
            text=meta,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=_CIAF_GRAY,
            anchor="w",
        ).pack(anchor="w", pady=(4, 0))

        if recording.description:
            ctk.CTkLabel(
                info,
                text=recording.description,
                font=ctk.CTkFont(family="Segoe UI", size=10),
                text_color=("gray50", "gray55"),
                anchor="w",
                wraplength=420,
                justify="left",
            ).pack(anchor="w", pady=(2, 0))

    def _build_card_stats(self, body: ctk.CTkFrame, recording: Recording) -> None:
        """Columna central: número grande de acciones como estadística visual."""
        stats = ctk.CTkFrame(body, fg_color="transparent")
        stats.pack(side="right", anchor="center", padx=(0, 24))

        ctk.CTkLabel(
            stats,
            text=str(len(recording.actions)),
            font=ctk.CTkFont(family="Segoe UI", size=28, weight="bold"),
            text_color=(_CIAF_BLUE, "#5BA3D9"),
        ).pack()

        ctk.CTkLabel(
            stats,
            text="acciones",
            font=ctk.CTkFont(family="Segoe UI", size=9),
            text_color=_CIAF_GRAY,
        ).pack()

    def _build_card_buttons(self, body: ctk.CTkFrame, recording: Recording) -> None:
        """Columna derecha: botones apilados verticalmente con jerarquía visual."""
        btn_col = ctk.CTkFrame(body, fg_color="transparent")
        btn_col.pack(side="right", anchor="center")

        if self._on_test_macro:
            ctk.CTkButton(
                btn_col,
                text="▶  Probar",
                width=_BTN_W, height=_BTN_H,
                corner_radius=6,
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                fg_color=_COLOR_OK,
                hover_color=_COLOR_OK_HOVER,
                command=lambda r=recording: self._test_macro(r),
            ).pack(fill="x", pady=(0, 5))

        if self._on_publish:
            ctk.CTkButton(
                btn_col,
                text="📤  Publicar",
                width=_BTN_W, height=_BTN_H,
                corner_radius=6,
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                fg_color=_CIAF_BLUE,
                hover_color=_CIAF_BLUE_HOVER,
                command=lambda r=recording: self._publish_macro(r),
            ).pack(fill="x", pady=(0, 5))

        ctk.CTkButton(
            btn_col,
            text="Eliminar",
            width=_BTN_W, height=_BTN_H,
            corner_radius=6,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="transparent",
            border_width=1,
            border_color=(_COLOR_ERROR, _COLOR_ERROR),
            hover_color=("gray92", "#2A3340"),
            text_color=(_COLOR_ERROR, "#E87070"),
            command=lambda r=recording: self._delete_macro(r),
        ).pack(fill="x")

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
