"""
Módulo de carga manual de archivos por el contador.

Por qué existe: Es el fallback universal cuando la descarga automática falla
o cuando la plataforma envía el archivo por email (delivery: "email").
En ambos casos el contador tiene el archivo en su computadora y quiere
subirlo al servidor sin que el bot intervenga.

Uso:
    manual = ManualUploader(file_uploader)
    success = manual.prompt_and_upload(task_id, task_name, date_from, date_to)
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

from uploader.file_uploader import FileUploader

logger = logging.getLogger(__name__)


class ManualUploader:
    """
    Permite al contador seleccionar y subir un archivo manualmente.

    Por qué existe: Cubre dos escenarios del PRD:
    1. La plataforma tiene delivery="email" y el bot no descarga.
    2. El bot falló y el contador completó la descarga a mano.

    En ambos casos se abre un selector de archivos del sistema operativo,
    el contador elige el archivo, y se sube con el flag manual=True.

    Uso:
        manual = ManualUploader(file_uploader)
        manual.prompt_and_upload("mercadopago_movimientos", "Mercado Pago",
                                 date_from, date_to)
    """

    def __init__(self, file_uploader: FileUploader) -> None:
        self._file_uploader = file_uploader

    def prompt_and_upload(self, task_id: str, task_name: str,
                          date_from: date, date_to: date) -> bool:
        """
        Abre un selector de archivos y sube el archivo seleccionado.

        Muestra un diálogo nativo del sistema operativo para que el
        contador seleccione un archivo Excel o CSV.

        Args:
            task_id: Identificador de la tarea.
            task_name: Nombre legible de la tarea (para el título del diálogo).
            date_from: Fecha inicio del período.
            date_to: Fecha fin del período.

        Returns:
            True si el archivo se subió correctamente.
            False si el contador canceló o hubo un error.
        """
        filepath = self._ask_file(task_name)
        if filepath is None:
            logger.info(
                "Carga manual cancelada por el usuario (task=%s)", task_id
            )
            return False

        logger.info(
            "Carga manual: %s (task=%s, periodo=%s→%s)",
            filepath.name, task_id, date_from, date_to
        )

        try:
            result = self._file_uploader.upload(
                task_id=task_id,
                filepath=filepath,
                date_from=date_from,
                date_to=date_to,
                manual=True,
            )
            if result:
                logger.info(
                    "Archivo cargado manualmente: %s", filepath.name
                )
            return result

        except Exception as e:
            logger.error(
                "Error en carga manual de '%s': %s", task_name, e
            )
            return False

    def _ask_file(self, task_name: str) -> Path | None:
        """
        Abre el diálogo nativo de selección de archivos.

        Returns:
            Path al archivo seleccionado, o None si el usuario canceló.
        """
        from tkinter import filedialog, Tk

        # Crear ventana raíz invisible para el diálogo
        root = Tk()
        root.withdraw()

        selected = filedialog.askopenfilename(
            title=f"Seleccionar archivo — {task_name}",
            filetypes=[
                ("Excel y CSV", "*.xlsx *.csv"),
                ("Todos los archivos", "*.*"),
            ],
        )

        root.destroy()

        if not selected:
            return None

        path = Path(selected)
        if not path.exists():
            logger.error("Archivo seleccionado no existe: %s", path)
            return None

        return path
