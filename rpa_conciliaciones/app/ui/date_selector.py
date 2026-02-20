"""
Selector de período de fecha para la ejecución de tareas.

Por qué existe: El contador elige qué período descargar antes de presionar
"Ejecutar todo". Los modos rápidos (Ayer, Semana pasada, etc.) cubren el 95%
de los casos. El modo "Personalizado" permite elegir fechas específicas.

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

# Modos disponibles con sus etiquetas en español
_DATE_MODES = [
    ("yesterday", "Ayer"),
    ("current_week", "Esta semana"),
    ("last_week", "Semana pasada"),
    ("current_month", "Este mes"),
    ("last_month", "Mes anterior"),
    ("custom", "Personalizado"),
]


class DateSelector(ctk.CTkFrame):
    """
    Panel de selección de período con modos rápidos y personalizado.

    Por qué existe: Cada tarea tiene un date_mode por defecto (en schema.json),
    pero el contador puede querer descargar un período diferente. Este selector
    permite elegir el modo globalmente antes de ejecutar.

    Uso:
        selector = DateSelector(parent)
        selection = selector.get_selection()
    """

    def __init__(self, parent, **kwargs) -> None:
        super().__init__(parent, **kwargs)

        self._selected_mode = ctk.StringVar(value="yesterday")
        self._custom_from: date | None = None
        self._custom_to: date | None = None

        # Título
        title = ctk.CTkLabel(
            self, text="Período a descargar",
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        title.pack(anchor="w", padx=12, pady=(8, 4))

        # Frame de botones de radio
        radio_frame = ctk.CTkFrame(self, fg_color="transparent")
        radio_frame.pack(fill="x", padx=12, pady=4)

        for i, (mode, label) in enumerate(_DATE_MODES):
            btn = ctk.CTkRadioButton(
                radio_frame, text=label,
                variable=self._selected_mode, value=mode,
                font=ctk.CTkFont(size=12),
                command=self._on_mode_change,
            )
            btn.grid(row=0, column=i, padx=6, pady=4)

        # Frame para fechas custom (oculto por defecto)
        self._custom_frame = ctk.CTkFrame(self, fg_color="transparent")

        self._from_label = ctk.CTkLabel(
            self._custom_frame, text="Desde:",
            font=ctk.CTkFont(size=12),
        )
        self._from_label.grid(row=0, column=0, padx=(0, 4), pady=4)

        self._from_entry = ctk.CTkEntry(
            self._custom_frame, width=120,
            placeholder_text="AAAA-MM-DD",
        )
        self._from_entry.grid(row=0, column=1, padx=4, pady=4)

        self._to_label = ctk.CTkLabel(
            self._custom_frame, text="Hasta:",
            font=ctk.CTkFont(size=12),
        )
        self._to_label.grid(row=0, column=2, padx=(12, 4), pady=4)

        self._to_entry = ctk.CTkEntry(
            self._custom_frame, width=120,
            placeholder_text="AAAA-MM-DD",
        )
        self._to_entry.grid(row=0, column=3, padx=4, pady=4)

    def get_selection(self) -> dict:
        """
        Retorna la selección actual del usuario.

        Returns:
            Dict con:
            - "mode": str — modo seleccionado
            - "custom_from": date | None — solo si mode es "custom"
            - "custom_to": date | None — solo si mode es "custom"
        """
        mode = self._selected_mode.get()
        custom_from = None
        custom_to = None

        if mode == "custom":
            custom_from = self._parse_date(self._from_entry.get())
            custom_to = self._parse_date(self._to_entry.get())

        return {
            "mode": mode,
            "custom_from": custom_from,
            "custom_to": custom_to,
        }

    def _on_mode_change(self) -> None:
        """Muestra/oculta los campos de fecha custom."""
        if self._selected_mode.get() == "custom":
            self._custom_frame.pack(fill="x", padx=12, pady=(0, 8))
        else:
            self._custom_frame.pack_forget()

    def _parse_date(self, text: str) -> date | None:
        """Parsea una fecha en formato AAAA-MM-DD."""
        try:
            return date.fromisoformat(text.strip())
        except (ValueError, AttributeError):
            return None
