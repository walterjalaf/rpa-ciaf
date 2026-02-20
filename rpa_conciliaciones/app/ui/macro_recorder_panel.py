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
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import customtkinter as ctk
import pygetwindow as gw

from macros.date_step import DATE_FROM, DATE_TO, FORMATS_COMUNES
from macros.exceptions import MacroRecorderError
from macros.models import Recording
from macros.recorder import MacroRecorder
from macros.storage import MacroStorage

logger = logging.getLogger(__name__)

# Estados del panel
_IDLE = "idle"
_COUNTDOWN = "countdown"
_RECORDING = "recording"
_REVIEW = "review"


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
        super().__init__(parent)
        self._recorder = recorder
        self._storage = storage
        self._on_saved = on_saved
        self._on_publish = on_publish
        self._state = _IDLE
        self._recording: Recording | None = None
        self._timer_start: float = 0.0
        self._countdown_val = 5
        self._timer_job: str | None = None

        self._build_idle_state()

    # ── Construcción por estado ─────────────────────────────────────────

    def _build_idle_state(self) -> None:
        """Formulario inicial con campos de nombre, URL y botón iniciar."""
        self._clear_frame()

        ctk.CTkLabel(
            self, text="Nueva grabación",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(anchor="w", padx=8, pady=(8, 4))

        # Campo nombre
        ctk.CTkLabel(self, text="Nombre *", font=ctk.CTkFont(size=11)).pack(
            anchor="w", padx=8,
        )
        self._name_entry = ctk.CTkEntry(
            self, placeholder_text="ej: Mercado Pago - Movimientos",
            width=380,
        )
        self._name_entry.pack(anchor="w", padx=8, pady=(0, 6))

        # Campo URL
        ctk.CTkLabel(self, text="URL * (debe empezar con https://)",
                     font=ctk.CTkFont(size=11)).pack(anchor="w", padx=8)
        self._url_entry = ctk.CTkEntry(
            self, placeholder_text="https://www.mercadopago.com.ar/activities",
            width=380,
        )
        self._url_entry.pack(anchor="w", padx=8, pady=(0, 6))

        # Label de error
        self._error_label = ctk.CTkLabel(
            self, text="", font=ctk.CTkFont(size=11),
            text_color="#CC0000",
        )
        self._error_label.pack(anchor="w", padx=8)

        # Botón iniciar
        self._start_btn = ctk.CTkButton(
            self, text="⏺  Iniciar grabación",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#28a745", hover_color="#1e7e34",
            height=40, width=200,
            command=self._on_start_click,
        )
        self._start_btn.pack(pady=8)

    def _build_countdown_state(self) -> None:
        """Cuenta regresiva de 5 segundos con botón cancelar."""
        self._clear_frame()

        self._countdown_label = ctk.CTkLabel(
            self, text="Iniciando grabación en: 5",
            font=ctk.CTkFont(size=20, weight="bold"),
        )
        self._countdown_label.pack(pady=20)

        ctk.CTkButton(
            self, text="Cancelar",
            fg_color="#dc3545", hover_color="#c82333",
            height=34, width=120,
            command=self._on_cancel_countdown,
        ).pack()

        self._countdown_val = 5
        self._run_countdown()

    def _build_recording_state(self) -> None:
        """Indicador de grabación activa + controles."""
        self._clear_frame()

        # Indicador pulsante
        self._recording_indicator = ctk.CTkLabel(
            self, text="● Grabando...",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#dc3545",
        )
        self._recording_indicator.pack(pady=(10, 4))

        # Contador de acciones + timer
        self._action_count_label = ctk.CTkLabel(
            self, text="0 acciones grabadas",
            font=ctk.CTkFont(size=12),
        )
        self._action_count_label.pack()

        self._timer_label = ctk.CTkLabel(
            self, text="Tiempo: 0:00",
            font=ctk.CTkFont(size=11), text_color="gray",
        )
        self._timer_label.pack(pady=(0, 8))

        # Controles de grabación
        controls = ctk.CTkFrame(self, fg_color="transparent")
        controls.pack(fill="x", padx=8)

        ctk.CTkButton(
            controls, text="↩ Deshacer última acción",
            height=30, font=ctk.CTkFont(size=11),
            command=self._on_undo,
        ).grid(row=0, column=0, padx=4, pady=3)

        ctk.CTkButton(
            controls, text="📅 Marcar fecha inicio",
            height=30, font=ctk.CTkFont(size=11),
            command=lambda: self._show_format_picker(DATE_FROM),
        ).grid(row=0, column=1, padx=4, pady=3)

        ctk.CTkButton(
            controls, text="📅 Marcar fecha fin",
            height=30, font=ctk.CTkFont(size=11),
            command=lambda: self._show_format_picker(DATE_TO),
        ).grid(row=1, column=1, padx=4, pady=3)

        # Botón detener
        self._stop_btn = ctk.CTkButton(
            self, text="⏹  Detener y guardar",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#dc3545", hover_color="#c82333",
            height=40, width=200,
            command=self._on_stop_click,
        )
        self._stop_btn.pack(pady=10)

        # Iniciar actualizaciones periódicas
        self._timer_start = time.monotonic()
        self._update_recording_ui()

    def _build_review_state(self, recording: Recording) -> None:
        """Lista de acciones grabadas + opciones de guardado."""
        self._clear_frame()

        ctk.CTkLabel(
            self, text=f"Grabación completa: {len(recording.actions)} acciones",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(anchor="w", padx=8, pady=(8, 4))

        # Lista scrollable de acciones
        scroll = ctk.CTkScrollableFrame(self, height=120)
        scroll.pack(fill="x", padx=8, pady=(0, 8))

        for i, action in enumerate(recording.actions):
            summary = self._action_summary(action)
            ctk.CTkLabel(
                scroll, text=f"{i+1:3}. {summary}",
                font=ctk.CTkFont(size=10, family="Courier"),
                anchor="w",
            ).pack(anchor="w", pady=1)

        # Campo de descripción
        ctk.CTkLabel(self, text="Descripción (opcional):",
                     font=ctk.CTkFont(size=11)).pack(anchor="w", padx=8)
        self._desc_entry = ctk.CTkEntry(self, width=380)
        self._desc_entry.pack(anchor="w", padx=8, pady=(0, 8))

        # Botones de acción
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=4)

        ctk.CTkButton(
            btn_frame, text="💾  Guardar localmente",
            fg_color="#28a745", hover_color="#1e7e34",
            height=36, command=self._on_save_local,
        ).grid(row=0, column=0, padx=4)

        ctk.CTkButton(
            btn_frame, text="💾📤  Guardar y publicar",
            height=36, command=self._on_save_publish,
        ).grid(row=0, column=1, padx=4)

        ctk.CTkButton(
            btn_frame, text="🗑  Descartar",
            fg_color="#dc3545", hover_color="#c82333",
            height=36, command=self._on_discard,
        ).grid(row=0, column=2, padx=4)

    # ── Handlers de botones ─────────────────────────────────────────────

    def _on_start_click(self) -> None:
        """Valida el formulario y arranca el countdown."""
        name = self._name_entry.get().strip()
        url = self._url_entry.get().strip()

        # Validación de nombre
        if not name:
            self._error_label.configure(text="El nombre es obligatorio")
            self._name_entry.configure(border_color="red")
            return

        # Validación de URL
        if not (url.startswith("http://") or url.startswith("https://")):
            self._error_label.configure(
                text="La URL debe empezar con https://"
            )
            self._url_entry.configure(border_color="red")
            return

        # Verificar que Chrome está abierto
        if not gw.getWindowsWithTitle("Chrome"):
            self._error_label.configure(
                text="Abri Chrome en la plataforma antes de iniciar la grabación"
            )
            return

        # Guardar meta para la grabación
        self._pending_name = name
        self._pending_url = url
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
        """Descarta la grabación con confirmación si hay acciones."""
        if self._recording and len(self._recording.actions) > 0:
            # TODO: mostrar modal de confirmación en lugar de descartar directo
            logger.info("Grabación descartada: %d acciones", len(self._recording.actions))
        self._recording = None
        self._state = _IDLE
        self._build_idle_state()

    def _show_format_picker(self, date_field: str) -> None:
        """Abre un menú para elegir el formato de fecha del DateStep."""
        popup = ctk.CTkToplevel(self)
        popup.title("Seleccionar formato")
        popup.geometry("260x220")
        popup.resizable(False, False)
        popup.grab_set()

        ctk.CTkLabel(
            popup,
            text=f"Formato para {'fecha inicio' if date_field == DATE_FROM else 'fecha fin'}:",
            font=ctk.CTkFont(size=12),
        ).pack(pady=8)

        for format_name, format_str in FORMATS_COMUNES.items():
            example = datetime.now().strftime(format_str)
            ctk.CTkButton(
                popup,
                text=f"{format_name}: {example}",
                height=32,
                command=lambda f=format_str, p=popup: self._apply_date_step(
                    date_field, f, p
                ),
            ).pack(fill="x", padx=12, pady=2)

    def _apply_date_step(self, date_field: str, date_format: str, popup) -> None:
        """Inserta el DateStep en la grabación y cierra el popup."""
        popup.destroy()
        try:
            self._recorder.mark_date_step(date_field, date_format)
        except MacroRecorderError as e:
            logger.warning("mark_date_step falló: %s", e)

    # ── Actualización periódica durante la grabación ────────────────────

    def _run_countdown(self) -> None:
        """Actualiza el label de countdown cada segundo."""
        if self._countdown_val <= 0:
            self._start_recording()
            return
        self._countdown_label.configure(
            text=f"Iniciando grabación en: {self._countdown_val}"
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
                task_id="",  # Se asigna en el schema.json después de grabar
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
        self._action_count_label.configure(
            text=f"{count} acciones grabadas",
            text_color="#FFA500" if count > 400 else ("white" if ctk.get_appearance_mode() == "Dark" else "black"),
        )

        elapsed = int(time.monotonic() - self._timer_start)
        mins, secs = divmod(elapsed, 60)
        self._timer_label.configure(text=f"Tiempo: {mins}:{secs:02d}")

        # Pulsar indicador rojo (alternating)
        current = self._recording_indicator.cget("text_color")
        next_color = "#FF6B6B" if current == "#dc3545" else "#dc3545"
        self._recording_indicator.configure(text_color=next_color)

        self._timer_job = self.after(500, self._update_recording_ui)

    # ── Helpers ────────────────────────────────────────────────────────

    def _clear_frame(self) -> None:
        """Elimina todos los widgets del frame."""
        for widget in self.winfo_children():
            widget.destroy()

    @staticmethod
    def _action_summary(action) -> str:
        """Genera un resumen legible de una Action para la lista de revisión."""
        t = action.type
        if t in ("click", "double_click", "triple_click", "right_click"):
            return f"{t:15} @ ({action.x}, {action.y})"
        if t == "type":
            text = (action.text or "")[:20]
            return f"type            '{text}'"
        if t == "paste":
            text = (action.text or "")[:20]
            return f"paste           '{text}'"
        if t == "key":
            return f"key             {'+'.join(action.keys)}"
        if t == "date_step":
            return f"DATE_STEP       {action.date_field} [{action.date_format}]"
        if t == "wait_image":
            return f"wait_image      {action.image_template}"
        if t == "delay":
            return f"delay           {action.delay}s"
        return f"{t}"
