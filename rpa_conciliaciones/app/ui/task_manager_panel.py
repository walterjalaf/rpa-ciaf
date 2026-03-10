"""
Panel de gestión del plan de ejecución de tareas.

Por qué existe: Reemplaza la lista estática de tareas del dashboard con
un panel interactivo donde el usuario puede ver todas las tareas (schema +
macros grabadas), reordenarlas con botones ↑↓ y ver el semáforo de estado
persistente de cada una.

El semáforo (dot de 12px) comunica al contador el resultado de la última
ejecución de cada tarea:
  ● gris  (#8A8A8D) — pendiente / nunca ejecutado
  ● verde (#28A745) — completado exitosamente
  ● rojo  (#DC3545) — falló en la última ejecución
  ● azul  (#0F4069) — ejecutando actualmente

Thread-safety: update_task_status() SOLO se llama desde el hilo UI
(via _poll_queue del dashboard). Los métodos privados de reordenamiento
también corren en el hilo UI (son handlers de botones CTk).
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from pathlib import Path

import customtkinter as ctk

from macros.storage import MacroStorage
from macros.task_plan_store import TaskPlanEntry, TaskPlanStore

logger = logging.getLogger(__name__)

# ── Paleta CIAF (duplicada para independencia de módulo) ────────
_CIAF_BLUE       = "#0F4069"
_CIAF_BLUE_HOVER = "#0A2D50"
_CIAF_GRAY       = "#8A8A8D"
_COLOR_OK        = "#28A745"
_COLOR_ERROR     = "#DC3545"

# Colores del semáforo
_DOT_COLORS: dict[str, str] = {
    "pending":    _CIAF_GRAY,
    "done":       _COLOR_OK,
    "error":      _COLOR_ERROR,
    "running":    _CIAF_BLUE,
    "done_manual": _COLOR_OK,
}


class TaskManagerPanel(ctk.CTkFrame):
    """
    Panel con la lista ordenable de tareas del plan de ejecución.

    Por qué existe: Centraliza la visualización y gestión del plan —
    qué tareas se ejecutan, en qué orden, y cuál fue el resultado de
    la última ejecución (semáforo persistente).

    Responsabilidades:
    - Mostrar filas con semáforo, nombre y botones ↑↓✕
    - Persistir cambios en TaskPlanStore
    - Exponer get_plan() para que el runner reciba el orden correcto
    - Exponer update_task_status() para el dashboard (desde hilo UI)
    - Exponer set_executing() para congelar/descongelar durante ejecución
    """

    def __init__(
        self,
        parent,
        plan_store: TaskPlanStore,
        macro_storage: MacroStorage,
        task_schemas: list[dict],
        on_manual_upload: Callable | None,
    ) -> None:
        """
        Args:
            parent: Widget padre CTk.
            plan_store: Persistencia del plan de ejecución.
            macro_storage: Acceso a macros grabadas.
            task_schemas: Lista de dicts con task_id/task_name/platform_url.
            on_manual_upload: Callback(task_id, task_name) para carga manual.
        """
        super().__init__(parent, fg_color="transparent")

        self._plan_store      = plan_store
        self._macro_storage   = macro_storage
        self._task_schemas    = task_schemas
        self._on_manual_upload = on_manual_upload

        self._plan: list[TaskPlanEntry] = []
        self._executing: bool = False

        # Mapa task_id → dict con widgets de la fila
        self._entry_rows: dict[str, dict] = {}

        self._load_or_init_plan()
        self._build_header()
        self._list_frame = self._build_list_container()
        self._rebuild_list()

    # ══════════════════════════════════════════════════════════
    # API pública
    # ══════════════════════════════════════════════════════════

    def update_task_status(self, task_id: str, status: str, message: str) -> None:
        """
        Actualiza el semáforo de una tarea. Llamar SOLO desde hilo UI.

        Args:
            task_id: ID de la tarea (task_id del schema o macro_id).
            status: "pending" | "running" | "done" | "done_manual" | "error".
            message: Mensaje descriptivo (no se muestra en el panel, solo para log).
        """
        row_data = self._entry_rows.get(task_id)
        if row_data is None:
            logger.debug("update_task_status: task_id '%s' no en panel", task_id)
            return
        color = _DOT_COLORS.get(status, _CIAF_GRAY)
        row_data["dot"].configure(text_color=color)

    def get_plan(self) -> list[TaskPlanEntry]:
        """Retorna el plan actual en el orden de la lista."""
        return list(self._plan)

    @property
    def plan_count(self) -> int:
        """Cantidad de entradas en el plan (para la barra de progreso)."""
        return len(self._plan)

    def set_executing(self, executing: bool) -> None:
        """
        Congela o descongela los botones ↑↓✕ durante la ejecución.

        Args:
            executing: True = deshabilitar botones; False = habilitarlos.
        """
        self._executing = executing
        new_state = "disabled" if executing else "normal"
        for row_data in self._entry_rows.values():
            for key in ("btn_up", "btn_down", "btn_remove"):
                btn = row_data.get(key)
                if btn:
                    btn.configure(state=new_state)
        # También el botón de agregar
        if hasattr(self, "_add_btn"):
            self._add_btn.configure(state=new_state)

    # ══════════════════════════════════════════════════════════
    # Construcción del layout
    # ══════════════════════════════════════════════════════════

    def _build_header(self) -> None:
        """Encabezado de sección con título y botón '+ Agregar'."""
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=0, pady=(10, 4))

        ctk.CTkLabel(
            header,
            text="Plan de ejecución",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=("gray10", "gray90"),
        ).pack(side="left")

        self._add_btn = ctk.CTkButton(
            header,
            text="+ Agregar tarea",
            width=130, height=28,
            corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color=(_CIAF_BLUE, _CIAF_BLUE),
            hover_color=_CIAF_BLUE_HOVER,
            command=self._show_add_modal,
        )
        self._add_btn.pack(side="right")

        self._count_label = ctk.CTkLabel(
            header,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            corner_radius=10,
            fg_color=("#E8E8E9", "#3A3A3C"),
            text_color=(_CIAF_GRAY, "#AAAAAD"),
            padx=10, pady=2,
        )
        self._count_label.pack(side="right", padx=(0, 8))

    def _build_list_container(self) -> ctk.CTkFrame:
        """Card blanca que contendrá las filas de tareas."""
        card = ctk.CTkFrame(
            self,
            corner_radius=12,
            fg_color=("white", "#1E2530"),
        )
        card.pack(fill="x", pady=(0, 12))
        return card

    def _rebuild_list(self) -> None:
        """Destruye y reconstruye todas las filas del plan."""
        # Limpiar widgets anteriores
        for widget in self._list_frame.winfo_children():
            widget.destroy()
        self._entry_rows.clear()

        for i, entry in enumerate(self._plan):
            is_last = (i == len(self._plan) - 1)
            self._build_row(entry, i, is_last)

        # Espacio inferior
        ctk.CTkFrame(
            self._list_frame, fg_color="transparent", height=4
        ).pack()

        self._count_label.configure(
            text=f"{len(self._plan)} tarea{'s' if len(self._plan) != 1 else ''}"
        )

    def _build_row(
        self, entry: TaskPlanEntry, index: int, is_last: bool
    ) -> None:
        """Construye una fila individual con semáforo + nombre + botones."""
        row_frame = ctk.CTkFrame(
            self._list_frame,
            fg_color="transparent",
            corner_radius=8,
        )
        row_frame.pack(
            fill="x",
            padx=8,
            pady=(8 if index == 0 else 2, 2),
        )
        row_frame.columnconfigure(1, weight=1)

        # Semáforo (dot de 12px)
        dot_color = _DOT_COLORS.get(entry.last_status, _CIAF_GRAY)
        dot = ctk.CTkLabel(
            row_frame,
            text="●",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=dot_color,
            width=18,
        )
        dot.grid(row=0, column=0, padx=(4, 6), pady=6, sticky="w")

        # Badge de tipo (schema / macro)
        badge_text = "macro" if entry.item_type == "macro" else "schema"
        badge_color = ("#E8F0FE", "#1A2A4A") if entry.item_type == "macro" else ("#F0F0F0", "#2A2A2A")
        badge_fg    = (_CIAF_BLUE, "#5BA3D9") if entry.item_type == "macro" else (_CIAF_GRAY, "#AAAAAD")

        badge = ctk.CTkLabel(
            row_frame,
            text=badge_text,
            font=ctk.CTkFont(family="Segoe UI", size=9),
            corner_radius=4,
            fg_color=badge_color,
            text_color=badge_fg,
            padx=6, pady=1,
            width=42,
        )
        badge.grid(row=0, column=1, padx=(0, 8), pady=6, sticky="w")

        # Nombre de la tarea
        name_label = ctk.CTkLabel(
            row_frame,
            text=entry.display_name,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=("gray15", "gray85"),
            anchor="w",
        )
        name_label.grid(row=0, column=2, padx=(0, 8), pady=6, sticky="ew")
        row_frame.columnconfigure(2, weight=1)

        # Botones de control
        btn_state = "disabled" if self._executing else "normal"

        btn_up = ctk.CTkButton(
            row_frame,
            text="↑",
            width=30, height=26,
            corner_radius=6,
            font=ctk.CTkFont(size=13),
            fg_color=("gray88", "gray25"),
            hover_color=("gray75", "gray35"),
            text_color=("gray20", "gray80"),
            state="disabled" if index == 0 else btn_state,
            command=lambda eid=entry.entry_id: self._on_move_up(eid),
        )
        btn_up.grid(row=0, column=3, padx=2, pady=4)

        btn_down = ctk.CTkButton(
            row_frame,
            text="↓",
            width=30, height=26,
            corner_radius=6,
            font=ctk.CTkFont(size=13),
            fg_color=("gray88", "gray25"),
            hover_color=("gray75", "gray35"),
            text_color=("gray20", "gray80"),
            state="disabled" if is_last else btn_state,
            command=lambda eid=entry.entry_id: self._on_move_down(eid),
        )
        btn_down.grid(row=0, column=4, padx=2, pady=4)

        btn_remove = ctk.CTkButton(
            row_frame,
            text="✕",
            width=30, height=26,
            corner_radius=6,
            font=ctk.CTkFont(size=11),
            fg_color=("#FDECEA", "#3A1A1A"),
            hover_color=("#F5C6C6", "#5A2A2A"),
            text_color=(_COLOR_ERROR, "#FF6B6B"),
            state=btn_state,
            command=lambda eid=entry.entry_id: self._on_remove(eid),
        )
        btn_remove.grid(row=0, column=5, padx=(2, 4), pady=4)

        self._entry_rows[entry.task_id] = {
            "dot":        dot,
            "name":       name_label,
            "btn_up":     btn_up,
            "btn_down":   btn_down,
            "btn_remove": btn_remove,
            "frame":      row_frame,
        }

    # ══════════════════════════════════════════════════════════
    # Handlers de reordenamiento
    # ══════════════════════════════════════════════════════════

    def _on_move_up(self, entry_id: str) -> None:
        """Mueve la entrada una posición hacia arriba."""
        idx = self._find_index(entry_id)
        if idx is None or idx == 0:
            return
        self._plan[idx - 1], self._plan[idx] = self._plan[idx], self._plan[idx - 1]
        self._plan_store.save(self._plan)
        self._rebuild_list()

    def _on_move_down(self, entry_id: str) -> None:
        """Mueve la entrada una posición hacia abajo."""
        idx = self._find_index(entry_id)
        if idx is None or idx == len(self._plan) - 1:
            return
        self._plan[idx + 1], self._plan[idx] = self._plan[idx], self._plan[idx + 1]
        self._plan_store.save(self._plan)
        self._rebuild_list()

    def _on_remove(self, entry_id: str) -> None:
        """Elimina la entrada del plan."""
        self._plan = [e for e in self._plan if e.entry_id != entry_id]
        self._plan_store.save(self._plan)
        self._rebuild_list()

    # ══════════════════════════════════════════════════════════
    # Modal "Agregar tarea"
    # ══════════════════════════════════════════════════════════

    def _show_add_modal(self) -> None:
        """Abre el modal para agregar schema tasks o macros al plan."""
        modal = ctk.CTkToplevel(self)
        modal.title("Agregar tarea al plan")
        modal.geometry("460x420")
        modal.resizable(False, False)
        modal.grab_set()   # Modal bloqueante

        ctk.CTkLabel(
            modal,
            text="Seleccioná una tarea para agregar al plan:",
            font=ctk.CTkFont(family="Segoe UI", size=13),
        ).pack(padx=20, pady=(16, 8))

        # IDs ya en el plan (para excluirlos)
        existing_ids = {e.task_id for e in self._plan}

        # Scroll con candidatos
        scroll = ctk.CTkScrollableFrame(modal, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=16, pady=(0, 12))

        added_any = False

        # 1. Schema tasks disponibles
        for schema in self._task_schemas:
            tid = schema.get("task_id", "")
            if tid in existing_ids:
                continue
            self._add_modal_row(
                scroll, modal,
                display_name=schema.get("task_name", tid),
                item_type="schema",
                task_id=tid,
                macro_id=None,
                platform_url=schema.get("platform_url", ""),
            )
            added_any = True

        # 2. Macros grabadas disponibles
        try:
            macros = self._macro_storage.list_all()
        except Exception as e:
            logger.warning("No se pudieron listar macros: %s", e)
            macros = []

        for recording in macros:
            if recording.macro_id in existing_ids:
                continue
            self._add_modal_row(
                scroll, modal,
                display_name=recording.macro_name,
                item_type="macro",
                task_id=recording.macro_id,
                macro_id=recording.macro_id,
                platform_url=recording.platform_url,
            )
            added_any = True

        if not added_any:
            ctk.CTkLabel(
                scroll,
                text="No hay tareas disponibles para agregar.\nTodas ya están en el plan.",
                font=ctk.CTkFont(family="Segoe UI", size=12),
                text_color=_CIAF_GRAY,
                justify="center",
            ).pack(pady=20)

        ctk.CTkButton(
            modal,
            text="Cancelar",
            width=100, height=32,
            fg_color=("gray85", "gray25"),
            hover_color=("gray75", "gray35"),
            text_color=("gray20", "gray80"),
            command=modal.destroy,
        ).pack(pady=(0, 16))

    def _add_modal_row(
        self,
        parent,
        modal,
        display_name: str,
        item_type: str,
        task_id: str,
        macro_id: str | None,
        platform_url: str,
    ) -> None:
        """Fila clickeable en el modal de agregar."""
        row = ctk.CTkFrame(
            parent,
            fg_color=("gray93", "#1E2530"),
            corner_radius=8,
        )
        row.pack(fill="x", pady=3)

        badge_text  = "macro" if item_type == "macro" else "schema"
        badge_color = ("#E8F0FE", "#1A2A4A") if item_type == "macro" else ("#F0F0F0", "#2A2A2A")
        badge_fg    = (_CIAF_BLUE, "#5BA3D9") if item_type == "macro" else (_CIAF_GRAY, "#AAAAAD")

        ctk.CTkLabel(
            row,
            text=badge_text,
            font=ctk.CTkFont(family="Segoe UI", size=9),
            corner_radius=4,
            fg_color=badge_color,
            text_color=badge_fg,
            padx=6, pady=1,
            width=42,
        ).pack(side="left", padx=(10, 6), pady=8)

        ctk.CTkLabel(
            row,
            text=display_name,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            anchor="w",
        ).pack(side="left", fill="x", expand=True, pady=8)

        def _on_add(
            dn=display_name, it=item_type,
            tid=task_id, mid=macro_id, pu=platform_url,
        ) -> None:
            new_entry = TaskPlanEntry(
                entry_id=str(uuid.uuid4()),
                display_name=dn,
                item_type=it,
                task_id=tid,
                macro_id=mid,
                platform_url=pu,
                last_status="pending",
                last_run_at=None,
            )
            self._plan.append(new_entry)
            self._plan_store.save(self._plan)
            self._rebuild_list()
            modal.destroy()

        ctk.CTkButton(
            row,
            text="+ Agregar",
            width=85, height=26,
            corner_radius=6,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color=_CIAF_BLUE,
            hover_color=_CIAF_BLUE_HOVER,
            command=_on_add,
        ).pack(side="right", padx=10, pady=8)

    # ══════════════════════════════════════════════════════════
    # Utilidades privadas
    # ══════════════════════════════════════════════════════════

    def _load_or_init_plan(self) -> None:
        """
        Carga el plan desde disco. Si está vacío, lo inicializa con los schemas.

        La inicialización automática garantiza continuidad UX: el primer
        arranque muestra las mismas tareas que antes (las de los schemas).
        """
        plan = self._plan_store.load()

        if not plan:
            logger.info("task_plan.json vacío — inicializando con schemas")
            plan = [
                TaskPlanEntry(
                    entry_id=str(uuid.uuid4()),
                    display_name=s.get("task_name", s.get("task_id", "Sin nombre")),
                    item_type="schema",
                    task_id=s.get("task_id", ""),
                    macro_id=None,
                    platform_url=s.get("platform_url", ""),
                    last_status="pending",
                    last_run_at=None,
                )
                for s in self._task_schemas
                if s.get("task_id")
            ]
            self._plan_store.save(plan)

        self._plan = plan

    def _find_index(self, entry_id: str) -> int | None:
        """Retorna el índice de la entrada con el entry_id dado, o None."""
        for i, entry in enumerate(self._plan):
            if entry.entry_id == entry_id:
                return i
        return None
