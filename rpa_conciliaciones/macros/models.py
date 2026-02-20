"""
Modelos de datos para el sistema de macros.

Por qué existe: Define las estructuras de datos que representan
una acción grabada (Action) y una secuencia completa de acciones
(Recording). Son los DTOs que viajan entre MacroRecorder,
MacroPlayer, MacroStorage y MacroSync.

Action representa un paso atómico: un click, una tecla, una espera
por imagen o un marcador de fecha dinámica (DateStep).

Recording agrupa una secuencia de Actions con metadata de la macro
(quién la grabó, para qué tarea, cuándo).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Action:
    """
    Representa una acción atómica grabada durante una sesión de MacroRecorder.

    El campo type determina qué otros campos son relevantes:
    - 'click', 'double_click', 'triple_click', 'right_click': usa x, y
    - 'type': usa text (escribe tecla por tecla)
    - 'paste': usa text (pega con Ctrl+V)
    - 'key': usa keys (combinación de teclas, ej. ['ctrl', 'c'])
    - 'scroll': usa clicks (positivo=arriba), x, y opcionales
    - 'wait_image': usa image_template (nombre del PNG), confidence
    - 'date_step': usa date_field ('date_from'|'date_to'), date_format
    - 'delay': usa delay (segundos a esperar)
    """

    type: str
    # 'click' | 'double_click' | 'triple_click' | 'right_click' |
    # 'key' | 'type' | 'paste' | 'scroll' |
    # 'wait_image' | 'date_step' | 'delay'

    x: int | None = None
    y: int | None = None
    text: str | None = None
    keys: list[str] = field(default_factory=list)
    image_template: str | None = None  # nombre del PNG en macros/images/ para wait_image
    delay: float = 0.1
    date_field: str | None = None     # 'date_from' | 'date_to' (solo date_step)
    date_format: str | None = None    # '%d/%m/%Y' | '%Y-%m-%d' (solo date_step)
    confidence: float = 0.8


@dataclass
class Recording:
    """
    Secuencia completa de acciones que representa un bot grabado.

    Por qué existe: Agrupa las acciones con la metadata necesaria para
    reproducirlas: la URL de la plataforma (para que el runner sepa
    dónde abrir Chrome), el task_id (para vincularlo con la tarea
    en schema.json) y la fecha de creación (para auditoría).

    La versión permite detectar incompatibilidades si el formato
    cambia en futuras versiones del sistema.
    """

    macro_id: str        # Identificador único de la macro
    macro_name: str      # Nombre legible para la UI (ej: "Mercado Pago - Movimientos")
    platform_url: str    # URL donde Chrome debe abrirse al reproducir
    task_id: str         # task_id del schema.json al que pertenece esta macro
    actions: list[Action]
    created_at: datetime
    version: str = "1.0"
    description: str = ""
