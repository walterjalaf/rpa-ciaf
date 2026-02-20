"""
Módulo de subida de archivos al servidor Laravel.

Por qué existe: Encapsula la lógica de envío de archivos descargados al
servidor, incluyendo el caso especial de no_filter (donde pandas filtra
filas por fecha antes de subir). Es el puente entre los bots (que descargan)
y el servidor (que recibe para ETL).

Uso:
    uploader = FileUploader(api_client)
    success = uploader.upload(task_id, filepath, date_from, date_to)
"""

from __future__ import annotations

import logging
import platform
from datetime import date
from pathlib import Path

from sync.api_client import ApiClient

logger = logging.getLogger(__name__)


class FileUploader:
    """
    Sube archivos descargados por los bots al servidor de conciliaciones.

    Por qué existe: Separa la lógica de upload de la lógica de descarga.
    El bot (BaseTask.run) solo descarga, el FileUploader solo sube.
    Esto permite reusar el uploader para carga manual desde la UI.

    Uso:
        uploader = FileUploader(api_client)
        uploader.upload("mercadopago_movimientos", path, date_from, date_to)
    """

    def __init__(self, api_client: ApiClient) -> None:
        self._api_client = api_client

    def upload(self, task_id: str, filepath: Path,
               date_from: date, date_to: date,
               no_filter_context: dict | None = None,
               manual: bool = False) -> bool:
        """
        Sube un archivo al servidor con su metadata de período.

        Args:
            task_id: Identificador de la tarea.
            filepath: Ruta al archivo .xlsx o .csv descargado.
            date_from: Fecha inicio del período.
            date_to: Fecha fin del período.
            no_filter_context: Si la tarea es de tipo no_filter, contiene
                las fechas originales para filtrar con pandas antes de subir.
            manual: True si el archivo fue cargado manualmente por el contador.

        Returns:
            True si el servidor aceptó el archivo.

        Raises:
            ApiAuthError: Si el token es inválido.
            UploadError: Si el servidor rechazó el archivo.
            ServerUnreachableError: Si no hay conexión.
        """
        filtered_path: Path | None = None
        actual_filepath = filepath

        if no_filter_context:
            actual_filepath = self._filter_by_date(
                filepath, date_from, date_to
            )
            if actual_filepath != filepath:
                filtered_path = actual_filepath

        metadata = {
            "task_id": task_id,
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "machine_id": platform.node(),
            "filename": actual_filepath.name,
            "manual_upload": manual,
        }

        file_size_kb = (
            actual_filepath.stat().st_size / 1024
            if actual_filepath.exists() else 0
        )
        logger.info(
            "Subiendo archivo: %s (task=%s, periodo=%s→%s, "
            "%.1f KB, manual=%s)",
            actual_filepath.name, task_id, date_from, date_to,
            file_size_kb, manual
        )

        result = self._api_client.upload_file(
            task_id, actual_filepath, metadata
        )

        if result:
            logger.info(
                "Archivo subido exitosamente: %s (%.1f KB)",
                actual_filepath.name, file_size_kb
            )
            self._cleanup_temp_files(filepath, filtered_path, manual=manual)

        return result

    def _filter_by_date(self, filepath: Path,
                        date_from: date,
                        date_to: date) -> Path:
        """
        Filtra un archivo Excel por rango de fechas usando pandas.

        Se usa cuando date_handler_type es 'no_filter': la plataforma no
        permite filtrar por fecha en la UI, así que se descarga todo y se
        filtra localmente antes de subir.

        Auto-detecta la columna de fecha: busca la primera columna cuyo
        dtype sea datetime o cuyo nombre contenga 'fecha' o 'date'.

        Returns:
            Path al archivo filtrado, o filepath original si no se pudo filtrar.
        """
        import pandas as pd

        logger.info("Filtrando archivo por fecha: rango=%s→%s", date_from, date_to)

        try:
            df = pd.read_excel(filepath, engine="openpyxl")
            date_column = self._detect_date_column(df)

            if date_column is None:
                logger.warning(
                    "No se detectó columna de fecha en el archivo. "
                    "Subiendo sin filtrar. Columnas: %s",
                    list(df.columns)
                )
                return filepath

            logger.info("Columna de fecha detectada: '%s'", date_column)
            df[date_column] = pd.to_datetime(
                df[date_column], errors="coerce"
            ).dt.date
            mask = (df[date_column] >= date_from) & (df[date_column] <= date_to)
            filtered = df[mask]

            filtered_path = filepath.with_stem(filepath.stem + "_filtered")
            filtered.to_excel(filtered_path, index=False, engine="openpyxl")

            logger.info(
                "Archivo filtrado: %d/%d filas en rango",
                len(filtered), len(df)
            )
            return filtered_path

        except Exception as e:
            logger.error(
                "Error filtrando archivo por fecha: %s. "
                "Subiendo archivo original sin filtrar.", e
            )
            return filepath

    def _detect_date_column(self, df) -> str | None:
        """
        Detecta la primera columna de fecha en un DataFrame.

        Busca por dtype datetime primero, luego por nombre que contenga
        'fecha' o 'date' (case insensitive).
        """
        import pandas as pd

        # Primero: columnas con dtype datetime
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                return col

        # Segundo: columnas cuyo nombre sugiere fecha
        date_keywords = ["fecha", "date", "fec_", "fecha_"]
        for col in df.columns:
            col_lower = str(col).lower()
            if any(kw in col_lower for kw in date_keywords):
                return col

        return None

    def _cleanup_temp_files(self, original: Path,
                            filtered: Path | None,
                            manual: bool = False) -> None:
        """
        Elimina archivos temporales después de un upload exitoso.

        Para uploads manuales (manual=True), el archivo original es del
        contador — no se toca. Solo se elimina el filtrado temporal si hubo.
        Para uploads automáticos, el original está en temp/ y se elimina.
        """
        try:
            if filtered and filtered.exists():
                filtered.unlink()
                logger.debug("Archivo filtrado temporal eliminado: %s", filtered)
            if not manual and original.exists():
                original.unlink()
                logger.debug("Archivo original eliminado: %s", original)
        except OSError as e:
            logger.warning("No se pudo limpiar archivos temporales: %s", e)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    client = ApiClient()
    client.load_token()
    uploader = FileUploader(client)

    test_path = Path("test_upload.xlsx")
    if not test_path.exists():
        print("Creando archivo de prueba vacío para mock...")
        test_path.touch()

    result = uploader.upload(
        "mercadopago_movimientos",
        test_path,
        date(2026, 2, 17),
        date(2026, 2, 17),
    )
    print(f"Upload resultado: {result}")
