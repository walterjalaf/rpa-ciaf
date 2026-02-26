"""
Selector de período de fecha para la ejecución de tareas.

Por qué existe: El contador elige qué período descargar antes de presionar
"Ejecutar todo". Los modos rápidos cubren el 95% de los casos. El modo
"Personalizado" permite elegir fechas específicas con campos de entrada.

Rediseño v2.0: identidad visual CIAF — reemplaza los RadioButtons por un
CTkSegmentedButton horizontal moderno. Los campos de fecha custom aparecen
suavemente debajo cuando se selecciona "Personalizado".

Uso:
    selector = DateSelector(parent)
    selector.pack()
    selection = selector.get_selection()
    # {"mode": "yesterday", "custom_from": None, "custom_to": None}
"""

from __future__ import annotations

import logging
from datetime import date

import customtkinter as ctk

logger = logging.getLogger(__name__)

# ── Paleta CIAF ────────────────────────────────────────────────
_CIAF_BLUE  = "#0F4069"
_CIAF_GRAY  = "#8A8A8D"
_COLOR_WARN = "#E87722"

# Modos disponibles: (valor_interno, etiqueta_visible)
_DATE_MODES: list[tuple[str, str]] = [
    ("yesterday",     "Ayer"),
    ("current_week",  "Esta semana"),
    ("last_week",     "Sem. anterior"),
    ("current_month", "Este mes"),
    ("last_month",    "Mes anterior"),
    ("custom",        "Personalizado"),
]

# Mapeo etiqueta → valor interno (para CTkSegmentedButton que trabaja con labels)
_LABEL_TO_MODE: dict[str, str] = {label: mode for mode, label in _DATE_MODES}
_MODE_TO_LABEL: dict[str, str] = {mode: label for mode, label in _DATE_MODES}


class DateSelector(ctk.CTkFrame):
    """
    Panel de selección de período con CTkSegmentedButton y modo personalizado.

    Por qué existe: Centraliza la elección del rango de fechas antes de
    ejecutar los bots. El CTkSegmentedButton moderno reemplaza los
    RadioButtons tradicionales para una experiencia más limpia y táctil.

    Contrato público:
        get_selection() -> dict — no cambia la firma.
    """

    def __init__(self, parent, **kwargs) -> None:
        super().__init__(
            parent,
            corner_radius=12,
            fg_color=("white", "#1E2530"),
            **kwargs,
        )
        self._custom_from: date | None = None
        self._custom_to: date | None = None

        self._build()

    def _build(self) -> None:
        """Construye el layout completo del selector."""
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(12, 8))

        ctk.CTkLabel(
            header,
            text="Período a descargar",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=("gray10", "gray90"),
        ).pack(side="left")

        # Separador
        ctk.CTkFrame(
            self, height=1, corner_radius=0,
            fg_color=("gray85", "gray25"),
        ).pack(fill="x", padx=16)

        # CTkSegmentedButton — reemplaza los RadioButtons
        labels = [label for _, label in _DATE_MODES]
        self._segment = ctk.CTkSegmentedButton(
            self,
            values=labels,
            selected_color=_CIAF_BLUE,
            selected_hover_color="#0A2D50",
            unselected_color=("gray92", "#2A3340"),
            unselected_hover_color=("gray85", "#323E4D"),
            text_color=("gray10", "gray90"),
            text_color_disabled=_CIAF_GRAY,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            corner_radius=8,
            command=self._on_segment_change,
        )
        self._segment.pack(fill="x", padx=16, pady=(10, 8))
        self._segment.set(_MODE_TO_LABEL["yesterday"])  # selección por defecto

        # Frame de fechas personalizadas (oculto hasta elegir "Personalizado")
        self._custom_frame = ctk.CTkFrame(
            self,
            corner_radius=8,
            fg_color=("#F4F8FB", "#16202C"),
            border_width=1,
            border_color=(_CIAF_BLUE, "#0A2D50"),
        )
        # No se hace pack aquí — se muestra solo cuando mode == "custom"

        self._build_custom_fields()

    def _build_custom_fields(self) -> None:
        """Construye los campos de fecha personalizada dentro de _custom_frame."""
        ctk.CTkLabel(
            self._custom_frame,
            text="Seleccionar rango de fechas",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=(_CIAF_BLUE, "#5BA3D9"),
        ).pack(anchor="w", padx=14, pady=(10, 4))

        fields_row = ctk.CTkFrame(self._custom_frame, fg_color="transparent")
        fields_row.pack(fill="x", padx=14, pady=(0, 12))

        # Campo "Desde"
        ctk.CTkLabel(
            fields_row,
            text="Desde",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=("gray30", "gray70"),
        ).pack(side="left", padx=(0, 6))

        self._from_entry = ctk.CTkEntry(
            fields_row,
            width=130, height=32,
            corner_radius=6,
            placeholder_text="AAAA-MM-DD",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            border_color=(_CIAF_BLUE, "#0A2D50"),
        )
        self._from_entry.pack(side="left", padx=(0, 16))

        # Campo "Hasta"
        ctk.CTkLabel(
            fields_row,
            text="Hasta",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=("gray30", "gray70"),
        ).pack(side="left", padx=(0, 6))

        self._to_entry = ctk.CTkEntry(
            fields_row,
            width=130, height=32,
            corner_radius=6,
            placeholder_text="AAAA-MM-DD",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            border_color=(_CIAF_BLUE, "#0A2D50"),
        )
        self._to_entry.pack(side="left")

        # Aviso de formato
        ctk.CTkLabel(
            self._custom_frame,
            text="Formato: año-mes-día  (ej. 2025-01-31)",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=_CIAF_GRAY,
        ).pack(anchor="w", padx=14, pady=(0, 10))

    # ── API pública ─────────────────────────────────────────────

    def get_selection(self) -> dict:
        """
        Retorna la selección actual del usuario.

        Contrato público — firma no puede cambiar.

        Returns:
            Dict con:
            - "mode": str — modo seleccionado (interno, ej. "yesterday")
            - "custom_from": date | None — solo si mode es "custom"
            - "custom_to": date | None — solo si mode es "custom"
        """
        label = self._segment.get()
        mode = _LABEL_TO_MODE.get(label, "yesterday")

        custom_from: date | None = None
        custom_to: date | None = None

        if mode == "custom":
            custom_from = self._parse_date(self._from_entry.get())
            custom_to   = self._parse_date(self._to_entry.get())

        return {
            "mode":        mode,
            "custom_from": custom_from,
            "custom_to":   custom_to,
        }

    # ── Handlers privados ───────────────────────────────────────

    def _on_segment_change(self, label: str) -> None:
        """Muestra u oculta el panel de fechas custom según la selección."""
        mode = _LABEL_TO_MODE.get(label, "yesterday")
        if mode == "custom":
            self._custom_frame.pack(
                fill="x", padx=16, pady=(0, 12),
            )
        else:
            self._custom_frame.pack_forget()

    @staticmethod
    def _parse_date(text: str) -> date | None:
        """Parsea una fecha en formato AAAA-MM-DD. Retorna None si inválida."""
        try:
            return date.fromisoformat(text.strip())
        except (ValueError, AttributeError):
            return None
