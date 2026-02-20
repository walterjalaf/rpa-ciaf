"""
Pre-flight check de sesiones para todas las plataformas configuradas.

Por qué existe: El Riesgo #4 del PRD (sesion expirada) es de probabilidad Alta
en banca argentina. Este modulo verifica si cada plataforma tiene sesion activa
ANTES de que los bots corran, transformando el riesgo en informacion accionable.

Diferencia vs v1.2 (Playwright): el checker ya no usa Playwright ni selectores
CSS. En su lugar:
    1. ChromeLauncher abre Chrome en la session_check_url del usuario real.
    2. PyAutoExecutor toma un screenshot del escritorio.
    3. pyautogui.locate() busca el session_indicator_image (PNG capturado por
       el tecnico) dentro del screenshot usando PIL.
    4. Si lo encuentra: sesion activa. Si no: sesion expirada.

Limitaciones conocidas:
- El template PNG debe capturarse en el mismo DPI que el equipo de produccion.
  Si cambia la resolucion o el zoom del navegador, el matching fallara.
- Las verificaciones se serializan con _screen_lock porque PyAutoGUI trabaja
  sobre la pantalla fisica (solo una ventana a la vez).
- La comparacion es exacta (sin confidence/opencv). Si el diseno de la
  plataforma cambia, el tecnico debe re-capturar el template con el Macro
  Recorder.

Uso:
    from core.chrome_launcher import ChromeLauncher
    from core.pyauto_executor import PyAutoExecutor
    launcher = ChromeLauncher()
    executor = PyAutoExecutor()
    checker = HealthChecker(launcher, executor)
    results = checker.check_all(task_list)
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from config import settings
from core.chrome_launcher import ChromeLauncher
from core.pyauto_executor import PyAutoExecutor

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Carpeta raiz del proyecto para resolver tasks/{task_id}/images/
_PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Tiempo de espera tras launch() para que la pagina cargue
_PAGE_LOAD_SECONDS = 2


@dataclass
class SessionStatus:
    """
    Resultado de la verificacion de sesion de una plataforma.

    Por que existe: Es el DTO que comunica el estado de cada plataforma
    entre el HealthChecker, la UI (SessionPanel) y el servidor
    (reporter.report_session_check).

    Campos:
        task_id: Identificador de la tarea verificada.
        task_name: Nombre legible para mostrar en la UI.
        platform_url: URL de la plataforma. Usado por el boton "Abrir" en UI.
        is_logged_in: True si se detecto sesion activa, False si no.
        checked_at: Momento de la verificacion.
        error: Mensaje si la verificacion en si fallo (timeout, DNS, etc.).
    """

    task_id: str
    task_name: str
    platform_url: str
    is_logged_in: bool
    checked_at: datetime = field(default_factory=datetime.now)
    error: str | None = None


class HealthChecker:
    """
    Verifica el estado de sesion de cada plataforma ANTES de ejecutar los bots.

    Por que existe: Transforma el Riesgo #4 del PRD (sesion expirada) en
    informacion accionable. Usa ChromeLauncher + PIL image matching en lugar
    de Playwright. Cada verificacion abre Chrome, toma un screenshot y busca
    el session_indicator_image del task.

    Limitaciones conocidas:
    - Las verificaciones se serializan con _screen_lock porque PyAutoGUI
      trabaja sobre la pantalla fisica (solo una ventana a la vez).
    - Si session_indicator_image no existe para un task, retorna
      is_logged_in=False con mensaje explicativo.
    - La comparacion no usa opencv: el template debe capturarse en el mismo
      DPI que la pantalla del equipo de produccion.

    Uso:
        launcher = ChromeLauncher()
        executor = PyAutoExecutor()
        checker = HealthChecker(launcher, executor)
        results = checker.check_all(task_list)
    """

    # Lock de clase: serializa operaciones visuales de todos los threads
    _screen_lock = threading.Lock()

    def __init__(
        self,
        chrome_launcher: ChromeLauncher,
        executor: PyAutoExecutor,
    ) -> None:
        """
        Args:
            chrome_launcher: Instancia de ChromeLauncher para abrir Chrome.
            executor: Instancia de PyAutoExecutor para tomar screenshots.
        """
        self._launcher = chrome_launcher
        self._executor = executor

    def check_all(self, task_list: list) -> list[SessionStatus]:
        """
        Verifica las sesiones de todas las tareas con threads paralelos.

        Para cada tarea con session_check_url definida, lanza un thread que
        abre Chrome, toma screenshot y busca el session_indicator_image.
        Las operaciones visuales se serializan con _screen_lock.

        Args:
            task_list: Lista de objetos con atributos task_id, task_name,
                platform_url, session_check_url y session_indicator_image.

        Returns:
            Lista de SessionStatus, uno por cada tarea en task_list.
            Las tareas sin session_check_url retornan is_logged_in=False
            con error explicativo.
        """
        results: list[SessionStatus | None] = [None] * len(task_list)
        threads: list[threading.Thread] = []
        checkable_count = 0

        for idx, task in enumerate(task_list):
            check_url = getattr(task, "session_check_url", "")
            if not check_url:
                results[idx] = SessionStatus(
                    task_id=task.task_id,
                    task_name=task.task_name,
                    platform_url=getattr(task, "platform_url", ""),
                    is_logged_in=False,
                    error="Sin URL de verificacion configurada",
                )
                logger.info(
                    "Tarea '%s' no tiene session_check_url, omitiendo",
                    task.task_name,
                )
                continue

            checkable_count += 1
            t = threading.Thread(
                target=self._check_one_into,
                args=(task, results, idx),
                daemon=True,
                name=f"health-{task.task_id}",
            )
            threads.append(t)

        logger.info(
            "Verificando sesiones: %d tareas (%d con URL de verificacion)",
            len(task_list),
            checkable_count,
        )

        for t in threads:
            t.start()

        for t in threads:
            t.join(timeout=15)

        # Construir lista final: threads que superaron timeout quedan con None
        final: list[SessionStatus] = []
        for i, task in enumerate(task_list):
            if results[i] is None:
                final.append(
                    SessionStatus(
                        task_id=task.task_id,
                        task_name=task.task_name,
                        platform_url=getattr(task, "platform_url", ""),
                        is_logged_in=False,
                        error="Timeout: verificacion supero 15 segundos",
                    )
                )
            else:
                final.append(results[i])

        logger.info(
            "Verificacion completada: %d/%d con sesion activa",
            sum(1 for r in final if r.is_logged_in),
            len(final),
        )
        return final

    def _check_one_into(
        self, task, results: list, idx: int
    ) -> None:
        """Wrapper de thread: escribe el resultado en results[idx]."""
        results[idx] = self._check_one(task)

    def _check_one(self, task) -> SessionStatus:
        """
        Verifica la sesion de una sola plataforma.

        Secuencia (dentro de _screen_lock para serializar con otros threads):
            1. Abrir Chrome en session_check_url con ChromeLauncher.
            2. Esperar _PAGE_LOAD_SECONDS para que la pagina cargue.
            3. Tomar screenshot con PyAutoExecutor.
            4. Buscar session_indicator_image en el screenshot con PIL.
            5. Cerrar Chrome (siempre en try/finally).

        Args:
            task: Objeto con task_id, task_name, platform_url,
                session_check_url y session_indicator_image.

        Returns:
            SessionStatus con el resultado de la verificacion.
        """
        logger.debug("Verificando sesion de '%s'...", task.task_name)

        with self._screen_lock:
            try:
                self._launcher.launch(task.session_check_url)
                time.sleep(_PAGE_LOAD_SECONDS)
                screenshot_path = self._executor.screenshot()

                indicator_image = getattr(task, "session_indicator_image", "")
                if not indicator_image:
                    logger.warning(
                        "session_indicator_image no configurado para '%s'",
                        task.task_name,
                    )
                    return SessionStatus(
                        task_id=task.task_id,
                        task_name=task.task_name,
                        platform_url=getattr(task, "platform_url", ""),
                        is_logged_in=False,
                        error="session_indicator_image no configurado en schema.json",
                    )

                template_path = (
                    _PROJECT_ROOT
                    / "tasks"
                    / task.task_id
                    / "images"
                    / indicator_image
                )

                if not template_path.exists():
                    logger.warning(
                        "Template de sesion no encontrado: '%s'",
                        template_path,
                    )
                    return SessionStatus(
                        task_id=task.task_id,
                        task_name=task.task_name,
                        platform_url=getattr(task, "platform_url", ""),
                        is_logged_in=False,
                        error=(
                            f"Template no encontrado: {template_path.name}. "
                            f"El tecnico debe capturarlo con el Macro Recorder."
                        ),
                    )

                is_logged_in = self._find_template_in_screenshot(
                    screenshot_path, template_path
                )

                estado = "activa" if is_logged_in else "expirada"
                logger.info("Sesion %s: %s", task.task_name, estado)

                return SessionStatus(
                    task_id=task.task_id,
                    task_name=task.task_name,
                    platform_url=getattr(task, "platform_url", ""),
                    is_logged_in=is_logged_in,
                )

            except Exception as e:
                logger.warning(
                    "Error verificando sesion de '%s': %s",
                    task.task_name,
                    e,
                )
                return SessionStatus(
                    task_id=task.task_id,
                    task_name=task.task_name,
                    platform_url=getattr(task, "platform_url", ""),
                    is_logged_in=False,
                    error=str(e),
                )
            finally:
                try:
                    self._launcher.close()
                except Exception as e:
                    logger.debug(
                        "Error cerrando Chrome en health check: %s", e
                    )

    def _find_template_in_screenshot(
        self, screenshot_path: Path, template_path: Path
    ) -> bool:
        """
        Busca el template PNG dentro del screenshot usando PIL + pyautogui.

        Usa pyautogui.locate(needle, haystack) que internamente compara
        pixeles con PIL. No toma un nuevo screenshot: trabaja sobre las
        imagenes en disco.

        Limitacion: comparacion exacta (sin confidence). El template debe
        capturarse en el mismo DPI que la pantalla del equipo de produccion.
        Si el diseno de la plataforma cambia, re-capturar el template con
        el Macro Recorder.

        Args:
            screenshot_path: Path al screenshot del escritorio.
            template_path: Path al PNG del indicador de sesion activa.

        Returns:
            True si el template aparece en el screenshot.
        """
        import pyautogui
        from PIL import Image

        try:
            screenshot_img = Image.open(screenshot_path)
            template_img = Image.open(template_path)
            location = pyautogui.locate(template_img, screenshot_img)
            return location is not None
        except Exception as e:
            logger.debug("Error en image matching para sesion: %s", e)
            return False


if __name__ == "__main__":
    # Prueba manual: ejecutar desde rpa_conciliaciones/
    # Requiere Chrome instalado y session_indicator_image capturado.
    import logging as _logging

    _logging.basicConfig(level=_logging.DEBUG)

    from core.chrome_launcher import ChromeLauncher
    from core.pyauto_executor import PyAutoExecutor

    class _MockTask:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    launcher = ChromeLauncher()
    executor = PyAutoExecutor()
    checker = HealthChecker(launcher, executor)

    tasks = [
        _MockTask(
            task_id="mercadopago_movimientos",
            task_name="Mercado Pago (prueba)",
            platform_url="https://www.mercadopago.com.ar",
            session_check_url="https://www.mercadopago.com.ar/home",
            session_indicator_image="mercadopago_session_ok.png",
        ),
        _MockTask(
            task_id="sin_url",
            task_name="Sin verificacion",
            platform_url="https://example.com",
            session_check_url="",
            session_indicator_image="",
        ),
    ]

    print("=== Prueba de HealthChecker (PyAutoGUI) ===")
    for s in checker.check_all(tasks):
        estado = "ACTIVA" if s.is_logged_in else "INACTIVA"
        print(f"  {s.task_name}: {estado}" + (f" ({s.error})" if s.error else ""))
    print("=== Fin ===")
