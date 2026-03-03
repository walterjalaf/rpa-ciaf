"""
Reproductor de macros grabadas con inyección de fechas dinámicas.

Por qué existe: Dado un Recording grabado por MacroRecorder, MacroPlayer
reproduce cada acción usando PyAutoExecutor. Las Action de tipo 'date_step'
son reemplazadas por la fecha real calculada por DateResolver: el Recording
almacena solo el tipo de fecha (date_from/date_to) y el formato, no el valor.

Esto permite que la misma macro sirva para cualquier período: ayer, la semana
pasada, un rango custom. El técnico graba una sola vez; el sistema rellena
las fechas en cada ejecución.

Manejo de errores:
    Si un wait_image supera el timeout, se lanza PlaybackError con screenshot
    para diagnóstico. El runner captura esto y reporta el fallo al servidor.

Foco de ventana:
    Antes de cada 'click' y 'paste'/'type' se llama executor.focus_window()
    para garantizar que Chrome esté en foco. Si retorna False, Chrome fue
    cerrado y se lanza ChromeNotFoundError.

Uso:
    player = MacroPlayer(executor)
    player.play(recording, date_from=date(2024, 1, 1), date_to=date(2024, 1, 31))
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import date
from pathlib import Path

from core.downloader import DownloadWatcher
from core.exceptions import ChromeNotFoundError, DownloadTimeoutError, ImageNotFoundError
from core.pyauto_executor import PyAutoExecutor
from macros.date_step import DATE_FROM, DATE_TO
from macros.exceptions import PlaybackError
from macros.models import Action, Recording

logger = logging.getLogger(__name__)

# Directorio por defecto para templates de imágenes de macros
_DEFAULT_IMAGES_DIR = (
    Path.home() / "AppData" / "Local" / "rpa_conciliaciones" / "macros" / "images"
)


class MacroPlayer:
    """
    Reproduce una Recording usando PyAutoExecutor.

    Por qué existe: Separa la lógica de reproducción del almacenamiento
    y la grabación. El runner solo necesita saber: "tengo una macro
    y un executor — reproducila con estas fechas".

    Modelo mental de DateStep:
        Recording tiene Action(type='date_step', date_field='date_from',
                               date_format='%d/%m/%Y')
        MacroPlayer reemplaza esto por executor.paste_text('31/01/2024')

    Uso:
        player = MacroPlayer(executor)
        player.play(recording, date(2024, 1, 1), date(2024, 1, 31))
    """

    def __init__(
        self,
        executor: PyAutoExecutor,
        images_dir: Path | None = None,
    ) -> None:
        """
        Args:
            executor: Instancia de PyAutoExecutor para ejecutar acciones.
            images_dir: Carpeta con los PNG templates para acciones wait_image.
                Defaults al directorio AppData de macros del usuario.
        """
        self._executor = executor
        self._images_dir = images_dir or _DEFAULT_IMAGES_DIR

    def play(
        self,
        recording: Recording,
        date_from: date,
        date_to: date,
        on_progress: Callable[[str], None] | None = None,
    ) -> None:
        """
        Reproduce todas las acciones de la Recording.

        Para cada Action:
            - Aplica el delay configurado en la acción (default 0.1s)
            - Ejecuta la acción usando el PyAutoExecutor
            - Para 'click' y 'paste': verifica foco de Chrome primero
            - Para 'date_step': inyecta la fecha formateada vía paste_text
            - Para 'wait_image_or_reload' / 'wait_download_or_reload': emite
              progreso vía on_progress(f"{attempt}|||{max_retries}|||desc")

        Args:
            recording: Recording cargada desde MacroStorage.
            date_from: Fecha inicio del período (para DateStep DATE_FROM).
            date_to: Fecha fin del período (para DateStep DATE_TO).
            on_progress: Callback opcional que recibe mensajes de progreso con
                formato "attempt|||max_retries|||descripción". La UI lo usa para
                actualizar el indicador de reintentos en tiempo real.

        Raises:
            PlaybackError: Si un wait_image falla o Chrome no responde.
            ChromeNotFoundError: Si Chrome fue cerrado durante la reproducción.
        """
        logger.info(
            "Reproduciendo macro '%s' (%d acciones, %s → %s)",
            recording.macro_name, len(recording.actions), date_from, date_to,
        )

        for index, action in enumerate(recording.actions):
            try:
                time.sleep(action.delay)
                self._execute_action(action, index, date_from, date_to, on_progress)
            except PlaybackError:
                raise
            except ChromeNotFoundError:
                raise
            except ImageNotFoundError as e:
                screenshot_path = self._safe_screenshot()
                raise PlaybackError(
                    f"Imagen no encontrada en paso {index} ({action.type}): {e}",
                    screenshot_path=screenshot_path,
                ) from e
            except Exception as e:
                screenshot_path = self._safe_screenshot()
                raise PlaybackError(
                    f"Error inesperado en paso {index} ({action.type}): {e}",
                    screenshot_path=screenshot_path,
                ) from e

        logger.info("Macro '%s' completada exitosamente", recording.macro_name)

    # ── Ejecución por tipo de acción ───────────────────────────────────────

    def _execute_action(
        self,
        action: Action,
        index: int,
        date_from: date,
        date_to: date,
        on_progress: Callable[[str], None] | None = None,
    ) -> None:
        """Ejecuta una acción individual según su type."""
        t = action.type

        if t in ("click", "double_click", "triple_click", "right_click"):
            self._ensure_chrome_focus()
            if t == "click":
                self._executor.click(action.x, action.y)
            elif t == "double_click":
                self._executor.double_click(action.x, action.y)
            elif t == "triple_click":
                self._executor.triple_click(action.x, action.y)
            elif t == "right_click":
                self._executor.right_click(action.x, action.y)

        elif t == "type":
            self._ensure_chrome_focus()
            self._executor.type_text(action.text or "")

        elif t == "paste":
            self._ensure_chrome_focus()
            self._executor.paste_text(action.text or "")

        elif t == "key":
            self._executor.press_key(*action.keys)

        elif t == "scroll":
            # Convención para scroll: action.text = clicks como string (ej: "3" o "-3")
            # action.x/y = coordenadas de pantalla donde hacer scroll (opcionales)
            # TODO: agregar captura de scroll en MacroRecorder._on_scroll (pynput on_scroll)
            try:
                clicks = int(action.text or "3")
            except (ValueError, TypeError):
                clicks = 3
            self._executor.scroll(clicks, x=action.x, y=action.y)

        elif t == "wait_image":
            template = self._images_dir / action.image_template
            self._executor.wait_for_image(
                template, timeout=30, confidence=action.confidence
            )

        elif t == "wait_image_or_reload":
            self._play_wait_image_or_reload(action, index, on_progress)

        elif t == "wait_download_or_reload":
            self._play_wait_download_or_reload(action, index, on_progress)

        elif t == "date_step":
            self._play_date_step(action, date_from, date_to)

        elif t == "delay":
            time.sleep(action.delay)

        else:
            logger.warning("Tipo de acción desconocido en paso %d: '%s'. Ignorando.", index, t)

    def _play_wait_image_or_reload(
        self,
        action: Action,
        index: int,
        on_progress: Callable[[str], None] | None = None,
    ) -> None:
        """
        Busca un template PNG en pantalla y recarga la página entre intentos.

        Por qué existe: Algunas plataformas generan reportes en background;
        el botón "Descargar" puede tardar entre 30s y 5 minutos en aparecer.
        Este método evita que el bot falle por timeout fijo.

        Args:
            action: Action con image_template, max_retries, retry_interval_seconds,
                    reload_key y confidence configurados.
            index: Posición en la secuencia (para mensajes de error).
            on_progress: Callback opcional que recibe progreso en formato
                "attempt|||max_retries|||descripción".

        Raises:
            PlaybackError: Si la imagen no aparece tras max_retries intentos.
        """
        template = self._images_dir / action.image_template
        for attempt in range(1, action.max_retries + 1):
            if on_progress:
                on_progress(
                    f"{attempt}|||{action.max_retries}|||"
                    f"Esperando: {action.image_template}"
                )
            result = self._executor.find_image(template, confidence=action.confidence)
            if result is not None:
                logger.info(
                    "wait_image_or_reload: imagen encontrada en intento %d/%d",
                    attempt, action.max_retries,
                )
                return
            logger.info(
                "wait_image_or_reload: intento %d/%d — imagen no encontrada, recargando",
                attempt, action.max_retries,
            )
            self._executor.press_key(action.reload_key)
            time.sleep(action.retry_interval_seconds)

        screenshot_path = self._safe_screenshot()
        raise PlaybackError(
            f"Imagen '{action.image_template}' no apareció tras {action.max_retries} recargas "
            f"(paso {index}). Verificar que el PNG está en {self._images_dir} y que la "
            f"plataforma generó el archivo.",
            screenshot_path=screenshot_path,
        )

    def _play_wait_download_or_reload(
        self,
        action: Action,
        index: int,
        on_progress: Callable[[str], None] | None = None,
    ) -> None:
        """
        Espera que aparezca un archivo nuevo en Downloads, recargando entre intentos.

        Por qué existe: Algunas plataformas generan reportes server-side sin dar
        ninguna señal visual — el archivo simplemente aparece en Downloads cuando
        el servidor termina de procesarlo. A diferencia de wait_image_or_reload,
        este método detecta la descarga vía filesystem (DownloadWatcher) en lugar
        de image matching, por lo que no requiere un PNG template.

        Estrategia:
            1. Toma snapshot del estado actual de Downloads al inicio del intento.
            2. Llama wait_for_download() con timeout = retry_interval_seconds.
            3. Si el archivo aparece → retorna (el runner lo detectará igualmente).
            4. Si hay DownloadTimeoutError → recarga con reload_key y repite.
            5. Si se agotan max_retries → PlaybackError con screenshot.

        Args:
            action: Action con max_retries, retry_interval_seconds, reload_key
                    y file_extensions configurados.
            index: Posición en la secuencia (para mensajes de error).
            on_progress: Callback opcional que recibe progreso en formato
                "attempt|||max_retries|||descripción".

        Raises:
            PlaybackError: Si el archivo no aparece tras max_retries intentos.
        """
        exts = action.file_extensions if action.file_extensions else None
        interval = int(action.retry_interval_seconds)

        for attempt in range(1, action.max_retries + 1):
            if on_progress:
                on_progress(
                    f"{attempt}|||{action.max_retries}|||"
                    f"Esperando descarga en Downloads"
                )
            watcher = DownloadWatcher(timeout_seconds=interval)
            watcher.take_snapshot(extensions=exts)
            try:
                filepath = watcher.wait_for_download(extensions=exts)
                logger.info(
                    "wait_download_or_reload: archivo detectado en intento %d/%d: %s",
                    attempt, action.max_retries, filepath.name,
                )
                return
            except DownloadTimeoutError:
                logger.info(
                    "wait_download_or_reload: intento %d/%d — sin archivo, recargando",
                    attempt, action.max_retries,
                )
                self._executor.press_key(action.reload_key)

        screenshot_path = self._safe_screenshot()
        exts_str = ", ".join(exts) if exts else ".xlsx, .csv"
        total_secs = action.max_retries * action.retry_interval_seconds
        raise PlaybackError(
            f"El archivo no apareció en Downloads tras {action.max_retries} recargas "
            f"(paso {index}). Tiempo total de espera: {total_secs:.0f}s. "
            f"Extensiones monitoreadas: {exts_str}. "
            f"Verificar que la plataforma generó el archivo.",
            screenshot_path=screenshot_path,
        )

    def _play_date_step(
        self,
        action: Action,
        date_from: date,
        date_to: date,
    ) -> None:
        """
        Inyecta la fecha dinámica en el campo activo.

        Usa paste_text() para garantizar compatibilidad con campos que
        no aceptan typewrite (ej: date pickers personalizados).
        """
        if action.date_field == DATE_FROM:
            target_date = date_from
        elif action.date_field == DATE_TO:
            target_date = date_to
        else:
            logger.warning(
                "date_field desconocido en date_step: '%s'. Ignorando.",
                action.date_field,
            )
            return

        fmt = action.date_format or "%d/%m/%Y"
        fecha_str = target_date.strftime(fmt)
        self._ensure_chrome_focus()
        self._executor.paste_text(fecha_str)
        logger.debug("DateStep: '%s' → '%s'", action.date_field, fecha_str)

    # ── Helpers internos ───────────────────────────────────────────────────

    def _ensure_chrome_focus(self) -> None:
        """
        Verifica que Chrome esté en foco antes de una acción crítica.

        Raises:
            ChromeNotFoundError: Si Chrome no está abierto.
        """
        if not self._executor.focus_window("Chrome"):
            raise ChromeNotFoundError(
                "Chrome fue cerrado durante la ejecución del bot. "
                "Abrir Chrome y volver a ejecutar."
            )

    def _safe_screenshot(self) -> Path | None:
        """Captura screenshot para diagnóstico. Retorna None si falla."""
        try:
            return self._executor.screenshot()
        except Exception as e:
            logger.warning("No se pudo capturar screenshot de error: %s", e)
            return None
