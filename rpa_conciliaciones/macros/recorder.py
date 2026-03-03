"""
Grabador de macros de automatización usando pynput.

Por qué existe: Permite al técnico grabar bots sin escribir código.
El técnico abre Chrome, navega manualmente por la plataforma y
MacroRecorder registra cada clic y tecla como una lista de Action.
La grabación se guarda como JSON y luego el contador la reproduce
con MacroPlayer, que inyecta las fechas dinámicas en los DateStep.

Modelo mental:
    Técnico navega → Recorder captura cada clic/tecla como Action
    → stop() retorna Recording → MacroStorage.save() guarda el JSON
    → Runner carga el JSON → MacroPlayer reproduce con fechas reales

Filtros implementados para reducir ruido:
    - on_move ignorado completamente (genera miles de acciones inútiles)
    - multi-clic colapsado: dos clicks rápidos en el mismo lugar → double_click
    - teclas modificadoras solas no grabadas (solo combos como Ctrl+C)
    - DateStep pendiente: teclas ignoradas mientras el técnico escribe
      el placeholder de fecha (el player reemplazará esa parte)

Límites de grabación (señales de advertencia):
    > 400 acciones: logger.warning (grabación muy larga, considerar dividir)
    > 600 acciones: logger.error (el botón Detener parpadea en rojo en la UI)
"""

from __future__ import annotations

import logging
import math
import time
from datetime import datetime

import pynput
import pynput.keyboard
import pynput.mouse
from pynput.mouse import Button

from macros.exceptions import MacroRecorderError
from macros.models import Action, Recording

logger = logging.getLogger(__name__)

# Conjunto de teclas modificadoras (no se graban solas, solo en combos)
_MODIFIER_KEYS = frozenset({
    pynput.keyboard.Key.ctrl,
    pynput.keyboard.Key.ctrl_l,
    pynput.keyboard.Key.ctrl_r,
    pynput.keyboard.Key.alt,
    pynput.keyboard.Key.alt_l,
    pynput.keyboard.Key.alt_r,
    pynput.keyboard.Key.shift,
    pynput.keyboard.Key.shift_l,
    pynput.keyboard.Key.shift_r,
    pynput.keyboard.Key.cmd,
    pynput.keyboard.Key.caps_lock,
})

# Teclas especiales que se graban como Action(type='key', keys=['nombre'])
_SPECIAL_KEYS = frozenset({
    "enter", "tab", "backspace", "delete", "escape",
    "home", "end", "page_up", "page_down",
    "up", "down", "left", "right",
    "f1", "f2", "f3", "f4", "f5", "f6",
    "f7", "f8", "f9", "f10", "f11", "f12",
})


class MacroRecorder:
    """
    Graba interacciones de mouse y teclado como una secuencia de Action.

    Por qué existe: El técnico no debería escribir código para agregar
    una plataforma nueva. MacroRecorder convierte la navegación manual
    en una macro reproducible por MacroPlayer.

    Ciclo de vida:
        recorder = MacroRecorder()
        recorder.start(macro_id, macro_name, platform_url, task_id)
        # ... técnico navega Chrome ...
        recorder.mark_date_step(DATE_FROM, FORMATS_COMUNES['Argentino'])
        # ... técnico escribe la fecha placeholder ...
        recorder.stop() → Recording

    Limitaciones:
        - No captura movimientos de mouse (solo clics).
        - Sensible al orden de los listeners: detener antes de llamar stop().
        - Si el equipo está bajo carga alta, puede perder algunos eventos
          de teclado entre el on_press y el procesamiento.
    """

    def __init__(self) -> None:
        self._actions: list[Action] = []
        self._recording: bool = False
        self._current_recording_meta: dict = {}
        self._last_click_time: float = 0.0
        self._last_click_pos: tuple[int, int] = (0, 0)
        self._mouse_listener: pynput.mouse.Listener | None = None
        self._keyboard_listener: pynput.keyboard.Listener | None = None
        self._pending_date_step: bool = False      # True mientras el técnico escribe el placeholder
        self._current_modifiers: set[str] = set()  # Modificadores actualmente presionados

    def start(
        self,
        macro_id: str,
        macro_name: str,
        platform_url: str,
        task_id: str,
    ) -> None:
        """
        Inicia la grabación de una nueva macro.

        Lanza los listeners de mouse y teclado de pynput en threads daemon.
        El método retorna inmediatamente; la captura ocurre en background.

        Args:
            macro_id: Identificador único (ej: 'mercadopago_movimientos_v2').
            macro_name: Nombre legible para la UI.
            platform_url: URL donde Chrome estará abierto durante la grabación.
            task_id: task_id del schema.json al que pertenece esta macro.

        Raises:
            MacroRecorderError: Si ya hay una grabación activa.
        """
        if self._recording:
            raise MacroRecorderError(
                "Ya hay una grabación en curso. Detenerla antes de iniciar una nueva."
            )

        self._actions = []
        self._pending_date_step = False
        self._current_modifiers = set()
        self._last_click_time = 0.0
        self._last_click_pos = (0, 0)
        self._current_recording_meta = {
            "macro_id": macro_id,
            "macro_name": macro_name,
            "platform_url": platform_url,
            "task_id": task_id,
        }

        # on_move=None: los movimientos generan miles de eventos inútiles
        self._mouse_listener = pynput.mouse.Listener(
            on_click=self._on_click,
        )
        self._keyboard_listener = pynput.keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release,
        )

        self._mouse_listener.start()
        self._keyboard_listener.start()
        self._recording = True
        logger.info("Grabación iniciada: %s", macro_name)

    def stop(self) -> Recording:
        """
        Detiene la grabación y retorna el Recording con todas las acciones.

        Raises:
            MacroRecorderError: Si no hay grabación activa.

        Returns:
            Recording listo para pasar a MacroStorage.save().
        """
        if not self._recording:
            raise MacroRecorderError(
                "No hay grabación activa. Llamar start() antes de stop()."
            )

        if self._mouse_listener:
            self._mouse_listener.stop()
        if self._keyboard_listener:
            self._keyboard_listener.stop()

        self._recording = False

        recording = Recording(
            macro_id=self._current_recording_meta["macro_id"],
            macro_name=self._current_recording_meta["macro_name"],
            platform_url=self._current_recording_meta["platform_url"],
            task_id=self._current_recording_meta["task_id"],
            actions=list(self._actions),
            created_at=datetime.now(),
        )

        logger.info(
            "Grabación detenida: %s. %d acciones grabadas.",
            recording.macro_name, len(self._actions),
        )
        return recording

    def mark_date_step(self, date_field: str, date_format: str) -> None:
        """
        Inserta un marcador de fecha dinámica en la secuencia de acciones.

        El técnico debe llamar este método DESPUÉS de hacer clic en el
        campo de fecha en Chrome y ANTES de escribir la fecha placeholder.
        MacroPlayer reemplazará este Action con la fecha real calculada
        por DateResolver al momento de reproducir.

        Las teclas que el técnico escriba después de este método serán
        ignoradas por el grabador (son el placeholder de fecha).
        El flag se limpia automáticamente en el siguiente clic.

        Args:
            date_field: 'date_from' o 'date_to' (ver macros.date_step).
            date_format: Formato strftime (ej: '%d/%m/%Y').

        Raises:
            MacroRecorderError: Si no hay grabación activa.
        """
        if not self._recording:
            raise MacroRecorderError(
                "No hay grabación activa. Llamar start() antes de mark_date_step()."
            )

        self._actions.append(
            Action(type="date_step", date_field=date_field, date_format=date_format)
        )
        self._pending_date_step = True
        logger.info(
            "Marcador de fecha insertado: %s formato %s", date_field, date_format
        )

    def mark_wait_image_or_reload(
        self,
        image_template: str,
        max_retries: int = 10,
        retry_interval_seconds: float = 15.0,
        reload_key: str = "f5",
    ) -> None:
        """
        Inserta manualmente una acción wait_image_or_reload en la grabación activa.

        Uso: el técnico configura esta acción en el panel cuando la plataforma
        genera el reporte en background. MacroPlayer buscará el template PNG
        y recargará la página entre intentos hasta encontrarlo.

        El PNG debe capturarse manualmente (Win+Shift+S) y guardarse en:
            %LOCALAPPDATA%/rpa_conciliaciones/macros/images/

        Args:
            image_template: Nombre del archivo PNG (ej: 'boton_descargar_listo.png').
            max_retries: Intentos máximos antes de lanzar PlaybackError.
            retry_interval_seconds: Segundos de espera entre cada intento.
            reload_key: Tecla que simula la recarga de página (default 'f5').

        Raises:
            MacroRecorderError: Si no hay grabación activa.
        """
        if not self._recording:
            raise MacroRecorderError(
                "No hay grabación activa. Llamar start() antes de mark_wait_image_or_reload()."
            )
        self._actions.append(Action(
            type="wait_image_or_reload",
            image_template=image_template,
            max_retries=max_retries,
            retry_interval_seconds=retry_interval_seconds,
            reload_key=reload_key,
        ))
        logger.info(
            "Acción wait_image_or_reload insertada: template='%s', %d reintentos, "
            "intervalo=%.1fs, tecla='%s'",
            image_template, max_retries, retry_interval_seconds, reload_key,
        )

    def mark_wait_download_or_reload(
        self,
        max_retries: int = 10,
        retry_interval_seconds: float = 30.0,
        reload_key: str = "f5",
        file_extensions: list[str] | None = None,
    ) -> None:
        """
        Inserta una acción wait_download_or_reload en la grabación activa.

        Uso: el técnico configura esta acción después de hacer clic en "Exportar"
        cuando la plataforma procesa el reporte en background. MacroPlayer esperará
        que aparezca un archivo nuevo en la carpeta Downloads, recargando la página
        entre intentos. No requiere un PNG template — detecta directamente en el
        filesystem.

        Diferencia con mark_wait_image_or_reload: no requiere captura manual
        de ninguna imagen. El default de retry_interval_seconds es 30s
        (más largo que wait_image_or_reload) porque el procesamiento server-side
        puede tardar minutos.

        Args:
            max_retries: Intentos máximos antes de lanzar PlaybackError.
            retry_interval_seconds: Segundos de espera por intento.
            reload_key: Tecla que simula recarga de página (default 'f5').
            file_extensions: Extensiones a monitorear (ej: ['.xlsx']). Si None,
                DownloadWatcher usa su default ['.xlsx', '.csv'].

        Raises:
            MacroRecorderError: Si no hay grabación activa.
        """
        if not self._recording:
            raise MacroRecorderError(
                "No hay grabación activa. Llamar start() antes de mark_wait_download_or_reload()."
            )
        self._actions.append(Action(
            type="wait_download_or_reload",
            max_retries=max_retries,
            retry_interval_seconds=retry_interval_seconds,
            reload_key=reload_key,
            file_extensions=file_extensions or [],
        ))
        logger.info(
            "Acción wait_download_or_reload insertada: %d reintentos, "
            "intervalo=%.1fs, tecla='%s', extensiones=%s",
            max_retries, retry_interval_seconds, reload_key,
            file_extensions or ["default (.xlsx, .csv)"],
        )

    @property
    def is_recording(self) -> bool:
        """True si hay una grabación activa."""
        return self._recording

    @property
    def action_count(self) -> int:
        """Número de acciones grabadas hasta el momento."""
        return len(self._actions)

    # ── Callbacks de pynput ────────────────────────────────────────────────

    def _on_click(
        self,
        x: int,
        y: int,
        button: Button,
        pressed: bool,
    ) -> None:
        """Captura clics izquierdos. Colapsa multi-clic en double/triple."""
        if not pressed or button != Button.left:
            return

        # El técnico hizo clic → fecha placeholder terminada
        self._pending_date_step = False

        now = time.time()
        dist = math.sqrt(
            (x - self._last_click_pos[0]) ** 2 + (y - self._last_click_pos[1]) ** 2
        )

        if dist < 5 and (now - self._last_click_time) < 0.3:
            # Colapsar multi-clic
            if self._actions and self._actions[-1].type == "click":
                self._actions[-1] = Action(type="double_click", x=x, y=y)
            elif self._actions and self._actions[-1].type == "double_click":
                self._actions[-1] = Action(type="triple_click", x=x, y=y)
        else:
            self._actions.append(Action(type="click", x=x, y=y))

        self._last_click_time = now
        self._last_click_pos = (x, y)

        count = len(self._actions)
        if count > 600:
            logger.error(
                "Grabación con %d acciones. El bot es demasiado largo. "
                "Detener y dividir en macros más cortas.",
                count,
            )
        elif count > 400:
            logger.warning(
                "Grabación con %d acciones. Considerar dividirla en pasos más cortos.",
                count,
            )

    def _on_key_press(self, key: pynput.keyboard.Key) -> None:
        """Captura teclas. Ignora modificadoras solas y placeholders de DateStep."""
        if not self._recording:
            return

        # Actualizar estado de modificadores
        if key in _MODIFIER_KEYS:
            if key in (
                pynput.keyboard.Key.ctrl,
                pynput.keyboard.Key.ctrl_l,
                pynput.keyboard.Key.ctrl_r,
            ):
                self._current_modifiers.add("ctrl")
            elif key in (
                pynput.keyboard.Key.alt,
                pynput.keyboard.Key.alt_l,
                pynput.keyboard.Key.alt_r,
            ):
                self._current_modifiers.add("alt")
            elif key in (
                pynput.keyboard.Key.shift,
                pynput.keyboard.Key.shift_l,
                pynput.keyboard.Key.shift_r,
            ):
                self._current_modifiers.add("shift")
            return  # No grabar modificadores solos

        # Ignorar teclas mientras el técnico escribe el placeholder de fecha
        if self._pending_date_step:
            return

        # Combinación con modificadores (ej: Ctrl+C)
        if self._current_modifiers:
            char = (
                key.char
                if hasattr(key, "char") and key.char
                else (key.name if hasattr(key, "name") else str(key))
            )
            keys = sorted(self._current_modifiers) + [char]
            self._actions.append(Action(type="key", keys=keys))
            return

        # Tecla especial sin modificadores
        if hasattr(key, "name") and key.name in _SPECIAL_KEYS:
            self._actions.append(Action(type="key", keys=[key.name]))
            return

        # Carácter normal
        if hasattr(key, "char") and key.char:
            self._actions.append(Action(type="type", text=key.char))

    def _on_key_release(self, key: pynput.keyboard.Key) -> None:
        """Limpia el estado de modificadores al soltar una tecla."""
        if key in (
            pynput.keyboard.Key.ctrl,
            pynput.keyboard.Key.ctrl_l,
            pynput.keyboard.Key.ctrl_r,
        ):
            self._current_modifiers.discard("ctrl")
        elif key in (
            pynput.keyboard.Key.alt,
            pynput.keyboard.Key.alt_l,
            pynput.keyboard.Key.alt_r,
        ):
            self._current_modifiers.discard("alt")
        elif key in (
            pynput.keyboard.Key.shift,
            pynput.keyboard.Key.shift_l,
            pynput.keyboard.Key.shift_r,
        ):
            self._current_modifiers.discard("shift")
