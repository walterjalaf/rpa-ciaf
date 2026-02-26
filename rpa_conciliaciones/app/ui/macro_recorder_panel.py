"""
Panel de grabación de macros. Visible solo si SHOW_MACRO_TAB = True.

Por qué existe: Permite al técnico grabar bots sin escribir código.
El flujo es: completar formulario → countdown de 5s → grabar → detener
→ revisar acciones → guardar (local o publicar al servidor).

Este panel es para TÉCNICOS, no para contadores. Los mensajes
son en español técnico (no de negocio).

Estados del panel:
    IDLE      → formulario + botón "Iniciar grabación"
    COUNTDOWN → cuenta regresiva con cancelar
    RECORDING → indicador pulsante + contadores + controles
    REVIEW    → lista de acciones + guardar/publicar/descartar

Thread-safety: los callbacks del MacroRecorder corren en threads de
pynput. Cualquier actualización de widgets usa self.after(0, ...).

Rediseño v2.0: identidad visual CIAF — card por estado, paleta coherente
con el resto del dashboard (azul marino #0F4069, rojo semántico #DC3545).
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import datetime

import customtkinter as ctk
import pygetwindow as gw

from macros.date_step import DATE_FROM, DATE_TO, FORMATS_COMUNES
from macros.exceptions import MacroRecorderError
from macros.models import Recording
from macros.recorder import MacroRecorder
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
_COLOR_WARN      = "#E87722"

# Estados del panel
_IDLE      = "idle"
_COUNTDOWN = "countdown"
_RECORDING = "recording"
_REVIEW    = "review"


class MacroRecorderPanel(ctk.CTkFrame):
    """
    Panel de grabación de macros para técnicos.

    Por qué existe: Encapsula el ciclo completo de grabación en un
    componente reutilizable que el Dashboard integra en la tab Macros.

    Callbacks:
        on_saved: Llamado cuando se guarda una macro (local o publicada).
                  Recibe (recording: Recording) para que el MacroListPanel
                  pueda refrescar su lista.

    Uso:
        panel = MacroRecorderPanel(parent, recorder, storage,
                                   on_saved=list_panel.refresh)
    """

    def __init__(
        self,
        parent: ctk.CTkFrame,
        recorder: MacroRecorder,
        storage: MacroStorage,
        on_saved: Callable[[Recording], None] | None = None,
        on_publish: Callable[[Recording], None] | None = None,
    ) -> None:
        super().__init__(
            parent,
            corner_radius=12,
            fg_color=("white", "#1E2530"),
        )
        self._recorder   = recorder
        self._storage    = storage
        self._on_saved   = on_saved
        self._on_publish = on_publish
        self._state      = _IDLE
        self._recording: Recording | None = None
        self._timer_start: float  = 0.0
        self._countdown_val       = 5
        self._timer_job: str | None = None

        self._build_idle_state()

    # ══════════════════════════════════════════════════════════
    # Construcción por estado
    # ══════════════════════════════════════════════════════════

    def _build_idle_state(self) -> None:
        """Formulario inicial con campos de nombre, URL y botón iniciar."""
        self._clear_frame()

        self._build_section_header("Nueva grabación", "⏺")

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="x", padx=16, pady=(0, 16))

        # Campo nombre
        ctk.CTkLabel(
            body, text="Nombre de la macro  *",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=("gray20", "gray80"),
        ).pack(anchor="w", pady=(0, 3))
        self._name_entry = ctk.CTkEntry(
            body,
            placeholder_text="ej: Mercado Pago — Movimientos",
            height=34, corner_radius=6,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            border_color=("gray75", "gray35"),
        )
        self._name_entry.pack(fill="x", pady=(0, 10))

        # Campo URL
        ctk.CTkLabel(
            body, text="URL de inicio  *  (debe comenzar con https://)",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=("gray20", "gray80"),
        ).pack(anchor="w", pady=(0, 3))
        self._url_entry = ctk.CTkEntry(
            body,
            placeholder_text="https://www.mercadopago.com.ar/activities",
            height=34, corner_radius=6,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            border_color=("gray75", "gray35"),
        )
        self._url_entry.pack(fill="x", pady=(0, 8))

        # Label de error (oculto hasta que se necesite)
        self._error_label = ctk.CTkLabel(
            body, text="",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=_COLOR_ERROR,
            anchor="w",
        )
        self._error_label.pack(anchor="w", pady=(0, 6))

        # Botón CTA
        ctk.CTkButton(
            body,
            text="⏺   Iniciar grabación",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color=_COLOR_OK, hover_color=_COLOR_OK_HOVER,
            height=42, corner_radius=8,
            command=self._on_start_click,
        ).pack(fill="x")

    def _build_countdown_state(self) -> None:
        """Cuenta regresiva de 5 segundos con botón cancelar."""
        self._clear_frame()

        self._build_section_header("Preparándose para grabar...", "⏳")

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="x", padx=16, pady=(0, 16))

        self._countdown_label = ctk.CTkLabel(
            body,
            text="Iniciando en: 5",
            font=ctk.CTkFont(family="Segoe UI", size=32, weight="bold"),
            text_color=(_CIAF_BLUE, "#5BA3D9"),
        )
        self._countdown_label.pack(pady=(8, 4))

        ctk.CTkLabel(
            body,
            text="Posicioná Chrome en la ventana de inicio antes del 0",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=_CIAF_GRAY,
        ).pack(pady=(0, 12))

        ctk.CTkButton(
            body,
            text="Cancelar",
            fg_color="transparent",
            border_width=1, border_color=(_COLOR_ERROR, _COLOR_ERROR),
            hover_color=("gray92", "#2A3340"),
            text_color=(_COLOR_ERROR, "#E87070"),
            height=34, corner_radius=8,
            command=self._on_cancel_countdown,
        ).pack()

        self._countdown_val = 5
        self._run_countdown()

    def _build_recording_state(self) -> None:
        """Indicador de grabación activa + controles."""
        self._clear_frame()

        self._build_section_header("Grabando acciones", "●")

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="x", padx=16, pady=(0, 16))

        # Indicador pulsante
        self._recording_indicator = ctk.CTkLabel(
            body,
            text="● REC  —  Grabando...",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color=_COLOR_ERROR,
        )
        self._recording_indicator.pack(pady=(4, 2))

        # Contador de acciones + timer en una fila
        counters = ctk.CTkFrame(body, fg_color="transparent")
        counters.pack(pady=(0, 10))

        self._action_count_label = ctk.CTkLabel(
            counters,
            text="0 acciones",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color=("gray10", "gray90"),
        )
        self._action_count_label.pack(side="left", padx=(0, 16))

        self._timer_label = ctk.CTkLabel(
            counters,
            text="0:00",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color=_CIAF_GRAY,
        )
        self._timer_label.pack(side="left")

        # Separador
        ctk.CTkFrame(
            body, height=1, corner_radius=0,
            fg_color=("gray85", "gray25"),
        ).pack(fill="x", pady=(0, 10))

        # Controles de grabación en grid 2x2
        controls = ctk.CTkFrame(body, fg_color="transparent")
        controls.pack(fill="x", pady=(0, 10))
        controls.columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            controls,
            text="↩  Deshacer última",
            height=32, corner_radius=6,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color=("gray88", "#2A3340"),
            hover_color=("gray80", "#323E4D"),
            text_color=("gray10", "gray90"),
            command=self._on_undo,
        ).grid(row=0, column=0, padx=(0, 4), pady=3, sticky="ew")

        ctk.CTkButton(
            controls,
            text="📅  Marcar fecha inicio",
            height=32, corner_radius=6,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color=_CIAF_BLUE, hover_color=_CIAF_BLUE_HOVER,
            command=lambda: self._show_format_picker(DATE_FROM),
        ).grid(row=0, column=1, padx=(4, 0), pady=3, sticky="ew")

        ctk.CTkButton(
            controls,
            text="📅  Marcar fecha fin",
            height=32, corner_radius=6,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color=_CIAF_BLUE, hover_color=_CIAF_BLUE_HOVER,
            command=lambda: self._show_format_picker(DATE_TO),
        ).grid(row=1, column=1, padx=(4, 0), pady=3, sticky="ew")

        # Botón detener — CTA rojo prominente
        ctk.CTkButton(
            body,
            text="⏹   Detener y revisar",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color=_COLOR_ERROR, hover_color=_COLOR_ERROR_HOV,
            height=42, corner_radius=8,
            command=self._on_stop_click,
        ).pack(fill="x")

        self._timer_start = time.monotonic()
        self._update_recording_ui()

    def _build_review_state(self, recording: Recording) -> None:
        """Lista de acciones grabadas + opciones de guardado."""
        self._clear_frame()

        self._build_section_header(
            f"Revisión — {len(recording.actions)} acciones grabadas", "✓"
        )

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="x", padx=16, pady=(0, 16))

        # Lista scrollable de acciones (fondo diferenciado)
        scroll_card = ctk.CTkFrame(
            body,
            corner_radius=8,
            fg_color=("#F4F8FB", "#16202C"),
            border_width=1,
            border_color=("gray80", "gray30"),
        )
        scroll_card.pack(fill="x", pady=(0, 10))

        scroll = ctk.CTkScrollableFrame(
            scroll_card, height=110,
            fg_color="transparent",
        )
        scroll.pack(fill="x", padx=4, pady=4)

        for i, action in enumerate(recording.actions):
            summary = self._action_summary(action)
            row_bg = ("gray96", "#1A2533") if i % 2 == 0 else ("white", "#1E2B3A")
            ctk.CTkLabel(
                scroll,
                text=f"  {i+1:3}.  {summary}",
                font=ctk.CTkFont(family="Consolas", size=10),
                anchor="w",
                fg_color=row_bg,
                corner_radius=3,
                text_color=("gray15", "gray85"),
            ).pack(fill="x", pady=1)

        # Campo descripción
        ctk.CTkLabel(
            body, text="Descripción (opcional):",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=("gray20", "gray80"),
        ).pack(anchor="w", pady=(0, 3))
        self._desc_entry = ctk.CTkEntry(
            body, height=32, corner_radius=6,
            font=ctk.CTkFont(family="Segoe UI", size=12),
        )
        self._desc_entry.pack(fill="x", pady=(0, 12))

        # Botones de acción — misma jerarquía que los modales
        btn_row = ctk.CTkFrame(body, fg_color="transparent")
        btn_row.pack(fill="x")
        btn_row.columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            btn_row,
            text="💾  Guardar localmente",
            height=38, corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color=_COLOR_OK, hover_color=_COLOR_OK_HOVER,
            command=self._on_save_local,
        ).grid(row=0, column=0, padx=(0, 4), sticky="ew")

        ctk.CTkButton(
            btn_row,
            text="📤  Guardar y publicar",
            height=38, corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color=_CIAF_BLUE, hover_color=_CIAF_BLUE_HOVER,
            command=self._on_save_publish,
        ).grid(row=0, column=1, padx=(4, 0), sticky="ew")

        # Descartar — botón outline secundario
        ctk.CTkButton(
            body,
            text="Descartar grabación",
            height=32, corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="transparent",
            border_width=1, border_color=(_COLOR_ERROR, _COLOR_ERROR),
            hover_color=("gray92", "#2A3340"),
            text_color=(_COLOR_ERROR, "#E87070"),
            command=self._on_discard,
        ).pack(fill="x", pady=(8, 0))

    # ══════════════════════════════════════════════════════════
    # Handlers de botones
    # ══════════════════════════════════════════════════════════

    def _on_start_click(self) -> None:
        """Valida el formulario y arranca el countdown."""
        name = self._name_entry.get().strip()
        url  = self._url_entry.get().strip()

        if not name:
            self._error_label.configure(text="⚠  El nombre es obligatorio")
            self._name_entry.configure(border_color=_COLOR_ERROR)
            return

        if not (url.startswith("http://") or url.startswith("https://")):
            self._error_label.configure(
                text="⚠  La URL debe comenzar con https://"
            )
            self._url_entry.configure(border_color=_COLOR_ERROR)
            return

        if not gw.getWindowsWithTitle("Chrome"):
            self._error_label.configure(
                text="⚠  Abrí Chrome en la plataforma antes de iniciar la grabación"
            )
            return

        self._pending_name = name
        self._pending_url  = url
        self._state = _COUNTDOWN
        self._build_countdown_state()

    def _on_cancel_countdown(self) -> None:
        """Cancela el countdown y vuelve al estado idle."""
        if self._timer_job:
            self.after_cancel(self._timer_job)
            self._timer_job = None
        self._state = _IDLE
        self._build_idle_state()

    def _on_stop_click(self) -> None:
        """Detiene la grabación y va al estado de revisión."""
        if self._timer_job:
            self.after_cancel(self._timer_job)
            self._timer_job = None
        try:
            recording = self._recorder.stop()
            self._recording = recording
            self._state = _REVIEW
            self._build_review_state(recording)
        except MacroRecorderError as e:
            logger.warning("Error deteniendo grabación: %s", e)

    def _on_undo(self) -> None:
        """Elimina la última acción grabada."""
        if self._recorder.action_count > 0:
            self._recorder._actions.pop()
            logger.debug("Última acción deshecha. Total: %d", self._recorder.action_count)

    def _on_save_local(self) -> None:
        """Guarda la macro localmente y regresa al estado idle."""
        if self._recording is None:
            return
        desc = self._desc_entry.get().strip() if hasattr(self, "_desc_entry") else ""
        self._recording.description = desc
        self._storage.save(self._recording)
        if self._on_saved:
            self._on_saved(self._recording)
        self._recording = None
        self._state = _IDLE
        self._build_idle_state()

    def _on_save_publish(self) -> None:
        """Guarda la macro localmente y llama al callback de publicación."""
        if self._recording is None:
            return
        desc = self._desc_entry.get().strip() if hasattr(self, "_desc_entry") else ""
        self._recording.description = desc
        self._storage.save(self._recording)
        if self._on_saved:
            self._on_saved(self._recording)
        if self._on_publish:
            self._on_publish(self._recording)
        self._recording = None
        self._state = _IDLE
        self._build_idle_state()

    def _on_discard(self) -> None:
        """Descarta la grabación con log y vuelve al estado idle."""
        if self._recording and len(self._recording.actions) > 0:
            # TODO: mostrar modal de confirmación en lugar de descartar directo
            logger.info("Grabación descartada: %d acciones", len(self._recording.actions))
        self._recording = None
        self._state = _IDLE
        self._build_idle_state()

    def _show_format_picker(self, date_field: str) -> None:
        """Abre un popup CIAF-styled para elegir el formato de DateStep."""
        popup = ctk.CTkToplevel(self)
        popup.title("Seleccionar formato de fecha")
        popup.geometry("300x240")
        popup.resizable(False, False)
        popup.grab_set()

        ctk.CTkFrame(popup, height=5, corner_radius=0, fg_color=_CIAF_BLUE).pack(fill="x")

        label_text = "fecha inicio" if date_field == DATE_FROM else "fecha fin"
        ctk.CTkLabel(
            popup,
            text=f"Formato para {label_text}:",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=("gray10", "gray90"),
        ).pack(pady=(12, 6), padx=16, anchor="w")

        for format_name, format_str in FORMATS_COMUNES.items():
            example = datetime.now().strftime(format_str)
            ctk.CTkButton(
                popup,
                text=f"{format_name}  →  {example}",
                height=32, corner_radius=6,
                font=ctk.CTkFont(family="Segoe UI", size=11),
                fg_color=_CIAF_BLUE, hover_color=_CIAF_BLUE_HOVER,
                anchor="w",
                command=lambda f=format_str, p=popup: self._apply_date_step(
                    date_field, f, p
                ),
            ).pack(fill="x", padx=16, pady=2)

    def _apply_date_step(self, date_field: str, date_format: str, popup) -> None:
        """Inserta el DateStep en la grabación y cierra el popup."""
        popup.destroy()
        try:
            self._recorder.mark_date_step(date_field, date_format)
        except MacroRecorderError as e:
            logger.warning("mark_date_step falló: %s", e)

    # ══════════════════════════════════════════════════════════
    # Actualización periódica durante la grabación
    # ══════════════════════════════════════════════════════════

    def _run_countdown(self) -> None:
        """Actualiza el label de countdown cada segundo."""
        if self._countdown_val <= 0:
            self._start_recording()
            return
        self._countdown_label.configure(
            text=f"Iniciando en: {self._countdown_val}"
        )
        self._countdown_val -= 1
        self._timer_job = self.after(1000, self._run_countdown)

    def _start_recording(self) -> None:
        """Arranca el MacroRecorder y cambia al estado Recording."""
        macro_id = f"macro_{int(time.time())}"
        try:
            self._recorder.start(
                macro_id=macro_id,
                macro_name=self._pending_name,
                platform_url=self._pending_url,
                task_id="",  # Se asigna en schema.json después de grabar
            )
            self._state = _RECORDING
            self._build_recording_state()
        except MacroRecorderError as e:
            logger.error("No se pudo iniciar la grabación: %s", e)
            self._state = _IDLE
            self._build_idle_state()

    def _update_recording_ui(self) -> None:
        """Actualiza contador de acciones y timer. Se auto-reprograma cada 500ms."""
        if self._state != _RECORDING:
            return

        count = self._recorder.action_count
        warn_color = _COLOR_WARN if count > 400 else ("gray10" if ctk.get_appearance_mode() == "Light" else "gray90")
        self._action_count_label.configure(
            text=f"{count} acciones grabadas",
            text_color=warn_color,
        )

        elapsed = int(time.monotonic() - self._timer_start)
        mins, secs = divmod(elapsed, 60)
        self._timer_label.configure(text=f"{mins}:{secs:02d}")

        # Pulso del indicador: alterna entre dos tonos de rojo
        current = self._recording_indicator.cget("text_color")
        next_color = "#FF6B6B" if current == _COLOR_ERROR else _COLOR_ERROR
        self._recording_indicator.configure(text_color=next_color)

        self._timer_job = self.after(500, self._update_recording_ui)

    # ══════════════════════════════════════════════════════════
    # Helpers de construcción
    # ══════════════════════════════════════════════════════════

    def _build_section_header(self, title: str, icon: str) -> None:
        """Header de card interno con ícono y título."""
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(14, 8))

        ctk.CTkLabel(
            header,
            text=icon,
            font=ctk.CTkFont(size=16),
            text_color=_CIAF_BLUE,
            width=24,
        ).pack(side="left")

        ctk.CTkLabel(
            header,
            text=title,
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color=("gray10", "gray90"),
        ).pack(side="left", padx=(8, 0))

        # Separador
        ctk.CTkFrame(
            self, height=1, corner_radius=0,
            fg_color=("gray85", "gray25"),
        ).pack(fill="x", padx=16, pady=(0, 8))

    def _clear_frame(self) -> None:
        """Elimina todos los widgets del frame."""
        for widget in self.winfo_children():
            widget.destroy()

    @staticmethod
    def _action_summary(action) -> str:
        """Genera un resumen legible de una Action para la lista de revisión."""
        t = action.type
        if t in ("click", "double_click", "triple_click", "right_click"):
            return f"{t:18} @ ({action.x}, {action.y})"
        if t == "type":
            return f"type               '{(action.text or '')[:24]}'"
        if t == "paste":
            return f"paste              '{(action.text or '')[:24]}'"
        if t == "key":
            return f"key                {'+'.join(action.keys)}"
        if t == "date_step":
            return f"DATE_STEP          {action.date_field}  [{action.date_format}]"
        if t == "wait_image":
            return f"wait_image         {action.image_template}"
        if t == "delay":
            return f"delay              {action.delay}s"
        return t
