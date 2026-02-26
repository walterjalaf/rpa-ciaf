"""
Panel de estado de sesiones (health check) en el dashboard.

Por qué existe: Muestra al contador el resultado del pre-flight check de
sesiones. Cada plataforma aparece como una mini-card con un pill badge
verde (sesión activa) o rojo (necesita login), y un botón para abrir el
sitio web cuando requiere re-autenticación.

Rediseño v2.0: identidad visual CIAF — mini-cards horizontales con pill
badges de colores semánticos. Sin iconos emoji frágiles; texto + color
comunican el estado con claridad.

Uso:
    panel = SessionPanel(parent)
    panel.update_results(session_results)
"""

from __future__ import annotations

import logging
import webbrowser

import customtkinter as ctk

logger = logging.getLogger(__name__)

# ── Paleta CIAF ────────────────────────────────────────────────
_CIAF_BLUE   = "#0F4069"
_CIAF_GRAY   = "#8A8A8D"
_COLOR_OK    = "#28A745"
_COLOR_ERROR = "#DC3545"
_COLOR_WARN  = "#E87722"


class SessionPanel(ctk.CTkFrame):
    """
    Panel que muestra el estado de sesión de cada plataforma como mini-cards.

    Por qué existe: El contador necesita saber si sus sesiones bancarias
    están activas antes de ejecutar los bots. Este panel muestra el resultado
    del health check con pill badges de colores semánticos y permite abrir
    las plataformas que necesitan login con un clic.

    Contrato público:
        update_results(results: list[SessionStatus]) — no cambia la firma.
    """

    def __init__(self, parent, **kwargs) -> None:
        super().__init__(
            parent,
            corner_radius=12,
            fg_color=("white", "#1E2530"),
            **kwargs,
        )
        self._rows: dict[str, ctk.CTkFrame] = {}
        self._build_skeleton()

    def _build_skeleton(self) -> None:
        """Construye el encabezado fijo del panel."""
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(12, 6))

        ctk.CTkLabel(
            header,
            text="Estado de sesiones",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=("gray10", "gray90"),
        ).pack(side="left")

        self._summary_pill = ctk.CTkLabel(
            header,
            text="Verificando...",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            corner_radius=10,
            fg_color=("#E8E8E9", "#3A3A3C"),
            text_color=(_CIAF_GRAY, "#AAAAAD"),
            padx=10, pady=2,
        )
        self._summary_pill.pack(side="right")

        # Separador
        ctk.CTkFrame(
            self, height=1, corner_radius=0,
            fg_color=("gray85", "gray25"),
        ).pack(fill="x", padx=16)

        # Contenedor de mini-cards (se reconstruye en cada update_results)
        self._content = ctk.CTkFrame(self, fg_color="transparent")
        self._content.pack(fill="x", padx=12, pady=(6, 12))

        # Mensaje inicial mientras carga
        self._placeholder = ctk.CTkLabel(
            self._content,
            text="Verificando sesiones activas...",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=_CIAF_GRAY,
        )
        self._placeholder.pack(anchor="w", padx=4)

    # ── API pública ─────────────────────────────────────────────

    def update_results(self, results: list) -> None:
        """
        Actualiza el panel con los resultados del health check.

        Contrato público — firma no puede cambiar.

        Args:
            results: Lista de SessionStatus del HealthChecker.
        """
        # Limpiar contenido anterior
        for widget in self._content.winfo_children():
            widget.destroy()
        self._rows.clear()

        if not results:
            ctk.CTkLabel(
                self._content,
                text="Sin plataformas configuradas.",
                font=ctk.CTkFont(family="Segoe UI", size=12),
                text_color=_CIAF_GRAY,
            ).pack(anchor="w", padx=4)
            self._summary_pill.configure(
                text="Sin datos",
                fg_color=("#E8E8E9", "#3A3A3C"),
                text_color=(_CIAF_GRAY, "#AAAAAD"),
            )
            return

        active = sum(1 for r in results if r.is_logged_in)
        total = len(results)
        all_ok = active == total

        # Actualizar pill de resumen en el header
        self._summary_pill.configure(
            text=f"{active}/{total} activas",
            fg_color=("#D4EDDA", "#143020") if all_ok else ("#FDECEA", "#3B1214"),
            text_color=(_COLOR_OK, "#5CB87A") if all_ok else (_COLOR_ERROR, "#E87070"),
        )

        # Mini-cards en fila horizontal (wrap automático)
        cards_frame = ctk.CTkFrame(self._content, fg_color="transparent")
        cards_frame.pack(fill="x")

        for result in results:
            card = self._build_session_card(cards_frame, result)
            card.pack(side="left", padx=(0, 8), pady=4)
            self._rows[result.task_id] = card

    # ── Construcción de mini-cards ──────────────────────────────

    def _build_session_card(self, parent: ctk.CTkFrame, result) -> ctk.CTkFrame:
        """
        Crea una mini-card horizontal para una sesión.

        Estructura:
            [nombre plataforma]  [pill: Activo / Requiere login]  [botón?]
        """
        is_ok = result.is_logged_in

        card = ctk.CTkFrame(
            parent,
            corner_radius=8,
            fg_color=("#F4F8FB", "#16202C"),
            border_width=1,
            border_color=(_COLOR_OK if is_ok else _COLOR_ERROR,
                          _COLOR_OK if is_ok else _COLOR_ERROR),
        )

        # Nombre de la plataforma
        ctk.CTkLabel(
            card,
            text=result.task_name,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=("gray10", "gray90"),
        ).pack(side="left", padx=(10, 6), pady=8)

        # Pill de estado semántico
        pill_text = "Activo" if is_ok else "Requiere login"
        pill_bg   = ("#D4EDDA", "#143020") if is_ok else ("#FDECEA", "#3B1214")
        pill_fg   = (_COLOR_OK, "#5CB87A") if is_ok else (_COLOR_ERROR, "#E87070")

        ctk.CTkLabel(
            card,
            text=pill_text,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            corner_radius=10,
            fg_color=pill_bg,
            text_color=pill_fg,
            padx=8, pady=2,
        ).pack(side="left", padx=(0, 6), pady=8)

        # Botón "Abrir" solo cuando requiere login
        if not is_ok and result.platform_url:
            ctk.CTkButton(
                card,
                text="Abrir sitio",
                width=76, height=24,
                font=ctk.CTkFont(family="Segoe UI", size=10),
                fg_color=_CIAF_BLUE,
                hover_color="#0A2D50",
                corner_radius=6,
                command=lambda url=result.platform_url: webbrowser.open(url),
            ).pack(side="left", padx=(0, 8), pady=8)

        # Tooltip de error (truncado) si existe
        if result.error:
            ctk.CTkLabel(
                card,
                text=f"({result.error[:35]}…)" if len(result.error) > 35
                     else f"({result.error})",
                font=ctk.CTkFont(family="Segoe UI", size=9),
                text_color=(_CIAF_GRAY, "#666670"),
            ).pack(side="left", padx=(0, 8), pady=8)

        return card
