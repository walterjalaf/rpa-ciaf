"""
Wrapper centralizado sobre pyautogui para todas las operaciones de automatización visual.

Por qué existe: Centralizar las llamadas a pyautogui permite ajustar delays globalmente,
hacer mocking en tests y agregar manejo de errores consistente. Es el único módulo
del proyecto que hace `import pyautogui`.

Limitaciones conocidas:
- Sensible a resolución de pantalla: los templates PNG deben grabarse en el mismo DPI
  que el equipo de producción. Si la confianza por defecto (0.8) falla, ajustar en
  settings.PYAUTOGUI_CONFIDENCE.
- Requiere que la ventana objetivo esté en foco antes de cada acción crítica.
  Llamar focus_window("Chrome") antes de click/paste cuando el foco pudo perderse.
- pyautogui.FAILSAFE = True: mover el mouse a la esquina superior izquierda aborta
  el bot con FailSafeException. Comportamiento deseado para emergencias.
- wait_for_image() no usa time.sleep() fijo; hace polling cada 0.5 segundos.
  Usar siempre wait_for_image() en lugar de sleep() para esperar elementos.

Uso:
    executor = PyAutoExecutor()
    x, y = executor.wait_for_image(template_path, timeout=10)
    executor.click(x, y)
    executor.paste_text("texto a escribir")
"""

import logging
import tempfile
import time
from pathlib import Path

import pyautogui
import pygetwindow as gw
import pyperclip

from config import settings
from core.exceptions import ImageNotFoundError

logger = logging.getLogger(__name__)


class PyAutoExecutor:
    """
    Wrapper centralizado sobre pyautogui para todas las operaciones de automatización visual.

    Todos los módulos del proyecto (MacroPlayer, DateHandlers, BaseTask) deben
    usar esta clase en lugar de llamar pyautogui directamente. Esto garantiza:
    - Un único punto para ajustar delays globales
    - Logging consistente de cada acción
    - Facilidad de mock en entornos de test

    Instanciar una vez por sesión de tarea; no es necesario crear una instancia nueva
    por cada acción.
    """

    def __init__(self) -> None:
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = settings.PYAUTOGUI_ACTION_DELAY
        self._screenshot_dir = Path(tempfile.gettempdir()) / "rpa_screenshots"
        self._screenshot_dir.mkdir(exist_ok=True)

    # ── Acciones de mouse ──────────────────────────────────────────────────

    def click(self, x: int, y: int, delay: float = 0.1) -> None:
        """Click izquierdo en las coordenadas indicadas."""
        logger.debug(f"click({x}, {y})")
        pyautogui.click(x, y)
        time.sleep(delay)

    def double_click(self, x: int, y: int) -> None:
        """Doble click izquierdo en las coordenadas indicadas."""
        logger.debug(f"double_click({x}, {y})")
        pyautogui.doubleClick(x, y)

    def triple_click(self, x: int, y: int) -> None:
        """Triple click (selecciona texto en campos de input). Tres clicks con 0.1s de intervalo."""
        logger.debug(f"triple_click({x}, {y})")
        pyautogui.click(x, y)
        time.sleep(0.1)
        pyautogui.click(x, y)
        time.sleep(0.1)
        pyautogui.click(x, y)

    def right_click(self, x: int, y: int) -> None:
        """Click derecho en las coordenadas indicadas."""
        logger.debug(f"right_click({x}, {y})")
        pyautogui.rightClick(x, y)

    def move_to(self, x: int, y: int) -> None:
        """Mueve el cursor al punto indicado sin hacer click."""
        logger.debug(f"move_to({x}, {y})")
        pyautogui.moveTo(x, y)

    def scroll(self, clicks: int, x: int | None = None, y: int | None = None) -> None:
        """
        Scroll vertical. Positivo = arriba, negativo = abajo.

        Args:
            clicks: Cantidad de unidades de scroll (positivo = arriba).
            x: Coordenada X donde hacer scroll. None = posición actual del mouse.
            y: Coordenada Y donde hacer scroll. None = posición actual del mouse.
        """
        logger.debug(f"scroll({clicks}, x={x}, y={y})")
        pyautogui.scroll(clicks, x=x, y=y)

    # ── Acciones de teclado ───────────────────────────────────────────────

    def type_text(self, text: str, interval: float = 0.05) -> None:
        """
        Escribe texto tecla por tecla.

        Preferir paste_text() para texto largo o con caracteres especiales.
        type_text() es útil cuando el campo no acepta paste (ej: CAPTCHA).

        Args:
            text: Texto a escribir.
            interval: Pausa entre teclas (segundos). 0.05 por defecto.
        """
        logger.debug(f"type_text('{text[:30]}{'...' if len(text) > 30 else ''}')")
        pyautogui.write(text, interval=interval)

    def paste_text(self, text: str) -> None:
        """
        Pega texto usando el portapapeles (Ctrl+V).

        Más fiable que type_text() para texto largo, caracteres especiales
        o campos que bloquean el ingreso tecla por tecla.

        Args:
            text: Texto a pegar.
        """
        logger.debug(f"paste_text('{text[:30]}{'...' if len(text) > 30 else ''}')")
        pyperclip.copy(text)
        pyautogui.hotkey("ctrl", "v")

    def press_key(self, *keys: str) -> None:
        """
        Presiona una tecla o combinación de teclas.

        Con una tecla: pyautogui.press(key). Con múltiples: pyautogui.hotkey(*keys).

        Args:
            *keys: Nombres de teclas según pyautogui (ej: 'enter', 'tab', 'ctrl', 'c').

        Ejemplos:
            executor.press_key('enter')
            executor.press_key('ctrl', 'a')
            executor.press_key('alt', 'f4')
        """
        logger.debug(f"press_key{keys}")
        if len(keys) == 1:
            pyautogui.press(keys[0])
        else:
            pyautogui.hotkey(*keys)

    # ── Gestión de foco de ventana ─────────────────────────────────────────

    def focus_window(self, title: str = "Chrome") -> bool:
        """
        Activa la ventana que contiene el título indicado en su barra de título.

        Llamar antes de click/paste en contextos donde el foco pudo perderse
        (entre acciones de una macro, después de interactuar con la UI del bot).

        Args:
            title: Substring del título de ventana a buscar. "Chrome" encuentra
                   cualquier ventana de Google Chrome.

        Returns:
            True si la ventana fue activada exitosamente.
            False si no hay ninguna ventana con ese título (Chrome fue cerrado).

        Nota: El OS necesita ~0.3s tras activate() para efectivizar el cambio de foco.
        """
        try:
            windows = gw.getWindowsWithTitle(title)
            if not windows:
                logger.warning(f"focus_window: no se encontró ventana con título '{title}'")
                return False
            windows[0].activate()
            time.sleep(0.3)
            logger.debug(f"focus_window: ventana '{title}' activada")
            return True
        except Exception as e:
            logger.warning(f"focus_window: error al activar ventana '{title}': {e}")
            return False

    # ── Image matching ─────────────────────────────────────────────────────

    def find_image(
        self,
        template: Path,
        confidence: float | None = None,
    ) -> tuple[int, int] | None:
        """
        Busca un template PNG en la pantalla actual (sin esperar).

        Args:
            template: Path al archivo PNG del template.
            confidence: Confianza de 0.0 a 1.0. None usa settings.PYAUTOGUI_CONFIDENCE.

        Returns:
            Tupla (x, y) del centro del template si se encontró. None si no.
        """
        conf = confidence if confidence is not None else settings.PYAUTOGUI_CONFIDENCE
        try:
            location = pyautogui.locateOnScreen(str(template), confidence=conf)
            if location is None:
                return None
            center = pyautogui.center(location)
            return (int(center.x), int(center.y))
        except pyautogui.ImageNotFoundException:
            return None
        except Exception as e:
            logger.warning(f"find_image: error inesperado buscando '{template.name}': {e}")
            return None

    def wait_for_image(
        self,
        template: Path,
        timeout: int = 30,
        confidence: float | None = None,
    ) -> tuple[int, int]:
        """
        Espera hasta que el template aparezca en pantalla. Polling cada 0.5 segundos.

        Usar siempre este método en lugar de time.sleep() para esperar que un elemento
        sea visible. Los sleeps fijos se rompen cuando la red está lenta.

        Args:
            template: Path al archivo PNG del template.
            timeout: Segundos máximos de espera. Por defecto 30.
            confidence: Confianza de 0.0 a 1.0. None usa settings.PYAUTOGUI_CONFIDENCE.

        Returns:
            Tupla (x, y) del centro del template encontrado.

        Raises:
            ImageNotFoundError: si el template no aparece dentro del timeout.
        """
        logger.info(f"wait_for_image: esperando '{template.name}' (timeout={timeout}s)")
        deadline = time.time() + timeout

        while time.time() < deadline:
            result = self.find_image(template, confidence)
            if result is not None:
                logger.info(f"wait_for_image: '{template.name}' encontrado en {result}")
                return result
            time.sleep(0.5)

        raise ImageNotFoundError(
            f"Imagen no encontrada en {timeout}s: {template.name}"
        )

    # ── Screenshots ────────────────────────────────────────────────────────

    def screenshot(self, region: tuple | None = None) -> Path:
        """
        Captura la pantalla (o una región) y guarda el PNG en un tempdir.

        Args:
            region: Tupla (x, y, width, height). None captura toda la pantalla.

        Returns:
            Path al archivo PNG guardado.
        """
        timestamp = int(time.time() * 1000)
        filepath = self._screenshot_dir / f"rpa_screenshot_{timestamp}.png"
        img = pyautogui.screenshot(region=region)
        img.save(str(filepath))
        logger.debug(f"screenshot guardado en: {filepath}")
        return filepath
