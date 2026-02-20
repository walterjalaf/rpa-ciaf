"""
Clase abstracta base para todas las tareas de automatización (bots).

Por qué existe: Define el esqueleto común de ejecución que todas las
plataformas siguen: abrir Chrome → navegar → ingresar fechas → descargar
archivo. Cada plataforma concreta solo implementa navigate() y
trigger_download() usando PyAutoExecutor para controlar la pantalla.

El método run() es concreto en BaseTask y orquesta el flujo completo:
ChromeLauncher → navegación → fechas → descarga → cleanup. Las subclases
no necesitan reimplementarlo salvo casos excepcionales.

Diferencia vs v1.2 (Playwright): navigate() y trigger_download() reciben
un PyAutoExecutor en lugar de un Page de Playwright. El motor no usa
selectores CSS — usa image templates y clicks sobre coordenadas visuales.

Uso:
    class MercadoPagoTask(BaseTask):
        task_id = "mercadopago_movimientos"
        ...
        def navigate(self, executor: PyAutoExecutor): ...
        def trigger_download(self, executor: PyAutoExecutor): ...

    task = MercadoPagoTask()
    filepath = task.run(date_from, date_to)
"""

from __future__ import annotations

import abc
import logging
import time
from datetime import date
from pathlib import Path

from config.settings import DOWNLOAD_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)

# Tiempo de espera tras ChromeLauncher.launch() para que Chrome cargue
_CHROME_LOAD_SECONDS = 2


class BaseTask(abc.ABC):
    """
    Clase abstracta que define el contrato y flujo de ejecución de un bot.

    Por qué existe: Agregar una plataforma nueva es crear una subclase que
    defina los atributos de clase y los dos métodos abstractos. El motor
    (runner, chrome_launcher, downloader) no cambia.

    Diferencia vs v1.2: Los métodos abstractos reciben PyAutoExecutor
    en lugar de Page de Playwright. run() usa ChromeLauncher y
    PyAutoExecutor en lugar de BrowserManager y Page.

    Atributos de clase que cada tarea concreta DEBE definir:
        task_id: Identificador único de la tarea.
        task_name: Nombre legible para la UI.
        platform_url: URL principal de la plataforma.
        date_handler_type: 'input_date' | 'datepicker_js' | 'no_filter' | 'macro'.
        date_handler_kwargs: Args extra para el handler de fechas.
        date_mode: Modo por defecto del DateResolver ('yesterday', etc.).
        session_check_url: URL post-login para health check.
        session_indicator_image: Nombre del PNG en tasks/{task_id}/images/
            que confirma sesión activa. Usado por HealthChecker.
    """

    # ── Atributos que las subclases DEBEN definir ──────────────
    task_id: str = ""
    task_name: str = ""
    platform_url: str = ""
    date_handler_type: str = "input_date"
    date_handler_kwargs: dict = {}
    date_mode: str = "yesterday"
    session_check_url: str = ""
    session_indicator_image: str = ""  # PNG en tasks/{task_id}/images/

    @abc.abstractmethod
    def navigate(self, executor) -> None:
        """
        Navega a la página de descarga de la plataforma.

        Cada subclase implementa los pasos específicos: esperar que Chrome
        cargue, hacer clic en menús, etc. Usar executor.wait_for_image()
        para esperar elementos — nunca time.sleep() fijo.

        Args:
            executor: Instancia de PyAutoExecutor.
        """

    @abc.abstractmethod
    def trigger_download(self, executor) -> None:
        """
        Hace clic en el botón de descarga de la plataforma.

        Debe llamarse DESPUÉS de navigate() y set_dates(). El watcher
        ya tomó su snapshot antes de esta llamada.

        Args:
            executor: Instancia de PyAutoExecutor.
        """

    def run(self, date_from: date, date_to: date) -> Path:
        """
        Ejecuta el flujo completo: abrir Chrome → navegar → fechas → descargar.

        Secuencia:
            1. ChromeLauncher abre Chrome en platform_url
            2. navigate() lleva a la pantalla de descarga
            3. El date_handler ingresa las fechas seleccionadas
            4. DownloadWatcher toma snapshot del estado de Downloads
            5. trigger_download() inicia la descarga
            6. DownloadWatcher detecta el archivo nuevo
            7. Si no_filter: filtrar filas por fecha con pandas
            8. cleanup() mueve el archivo a temp/

        Args:
            date_from: Fecha inicio del período a descargar.
            date_to: Fecha fin del período a descargar.

        Returns:
            Path al archivo descargado (ya movido a temp/).

        Raises:
            ChromeNotFoundError: Si Chrome no está instalado.
            ImageNotFoundError: Si un template visual no se encuentra.
            DownloadTimeoutError: Si la descarga no completó en el timeout.
        """
        # Imports lazy: evita dependencias en cascada al importar el módulo
        from core.chrome_launcher import ChromeLauncher
        from core.pyauto_executor import PyAutoExecutor
        from core.downloader import DownloadWatcher
        from date_handlers.factory import get_handler

        launcher = ChromeLauncher()
        executor: PyAutoExecutor | None = None

        try:
            logger.info(
                "Ejecutando tarea '%s' (período %s → %s)",
                self.task_name, date_from, date_to,
            )

            launcher.launch(self.platform_url)
            time.sleep(_CHROME_LOAD_SECONDS)
            executor = PyAutoExecutor()

            # Paso 1: Navegar a la pantalla de descarga
            self.navigate(executor)

            # Paso 2: Ingresar fechas según el tipo de handler
            handler = get_handler(self.date_handler_type, **self.date_handler_kwargs)
            if handler is not None:
                handler.set_dates(executor, date_from, date_to)

            # Paso 3: Snapshot ANTES de descargar
            watcher = DownloadWatcher()
            watcher.take_snapshot()

            # Paso 4: Trigger de descarga
            self.trigger_download(executor)

            # Paso 5: Esperar y capturar el archivo
            filepath = watcher.wait_for_download()

            # Paso 6: Filtrar por fecha si la plataforma no tiene filtro nativo
            if self.date_handler_type == "no_filter" and handler is not None:
                filepath = self._filter_by_date(filepath, handler.context)

            # Paso 7: Mover a carpeta de trabajo
            final_path = watcher.cleanup(filepath)
            logger.info("Tarea '%s' completada: %s", self.task_name, final_path.name)
            return final_path

        except Exception as e:
            self._take_error_screenshot(executor)
            logger.error("Error en tarea '%s': %s", self.task_name, e)
            raise

        finally:
            try:
                launcher.close()
            except Exception as close_err:
                logger.debug("Error cerrando Chrome tras tarea: %s", close_err)

    def _take_error_screenshot(self, executor) -> Path | None:
        """
        Captura screenshot del escritorio al momento del error.

        La ruta se incluye en el reporte al servidor para diagnóstico
        remoto. Si executor es None (fallo antes de instanciarlo), retorna None.
        """
        if executor is None:
            return None
        try:
            path = executor.screenshot()
            logger.debug("Screenshot de error guardado: %s", path)
            return path
        except Exception as e:
            logger.debug("No se pudo tomar screenshot de error: %s", e)
            return None

    def _filter_by_date(self, filepath: Path, context: dict) -> Path:
        """
        Filtra filas del archivo descargado por rango de fecha.

        Solo se llama cuando date_handler_type == 'no_filter': la plataforma
        no permite filtrar por fecha en la descarga, por lo que se descarga
        todo y aquí se recortan las filas fuera del período.

        Busca la columna de fecha por nombre ('fecha', 'date') o por dtype
        datetime. Si no encuentra ninguna, retorna el archivo sin modificar.

        Args:
            filepath: Path del archivo descargado en Downloads.
            context: Dict con 'date_from' y 'date_to' (date objects).

        Returns:
            Path al archivo filtrado (con sufijo '_filtered'). El archivo
            original sin filtrar es eliminado.
        """
        import pandas as pd

        date_from: date = context.get("date_from")
        date_to: date = context.get("date_to")

        try:
            if filepath.suffix == ".xlsx":
                df = pd.read_excel(filepath, engine="openpyxl")
            else:
                df = pd.read_csv(filepath)

            date_col = self._find_date_column(df)
            if date_col is None:
                logger.warning(
                    "No se encontró columna de fecha en '%s'. Se sube sin filtrar.",
                    filepath.name,
                )
                return filepath

            df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
            mask = (
                (df[date_col].dt.date >= date_from)
                & (df[date_col].dt.date <= date_to)
            )
            df_filtered = df[mask]

            filtered_path = filepath.parent / f"{filepath.stem}_filtered{filepath.suffix}"
            if filepath.suffix == ".xlsx":
                df_filtered.to_excel(filtered_path, index=False, engine="openpyxl")
            else:
                df_filtered.to_csv(filtered_path, index=False)

            logger.info(
                "Filtrado '%s': %d filas entre %s y %s",
                filepath.name, len(df_filtered), date_from, date_to,
            )
            filepath.unlink(missing_ok=True)
            return filtered_path

        except Exception as e:
            logger.warning(
                "Error filtrando '%s' por fecha: %s. Se sube sin filtrar.",
                filepath.name, e,
            )
            return filepath

    def _find_date_column(self, df) -> str | None:
        """
        Busca la columna de fecha en un DataFrame.

        Primero por nombre (contiene 'fecha' o 'date'),
        luego por dtype datetime64.

        Returns:
            Nombre de la columna, o None si no se encontró ninguna.
        """
        import pandas as pd

        for col in df.columns:
            if "fecha" in col.lower() or "date" in col.lower():
                return col
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                return col
        return None

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} task_id='{self.task_id}'>"
