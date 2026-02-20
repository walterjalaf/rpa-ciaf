# Skill: UI Development

| Campo | Valor |
|---|---|
| **Name** | UI Development |
| **Description** | Guía para construir componentes visuales con CustomTkinter en el proyecto RPA Conciliaciones. Cubre thread-safety, layouts, estados visuales y copywriting para usuario no técnico. |
| **Trigger** | El prompt contiene: "UI", "panel", "componente visual", "ventana", "dashboard", "modal" |
| **Scope** | `app/ui/` exclusivamente. Nunca lógica de negocio. |

---

## Reglas obligatorias

### 1. Thread-safety con `after()`

La UI corre en el hilo principal de tkinter. Toda actualización desde un hilo secundario (ej: TaskRunner, HealthChecker) **debe** usar `widget.after()`:

```python
# BIEN — thread-safe
def on_status_change(task_id: str, status: str, message: str) -> None:
    self.after(0, lambda: self._update_task_row(task_id, status, message))

# MAL — crash silencioso o congelamiento
def on_status_change(task_id: str, status: str, message: str) -> None:
    self._update_task_row(task_id, status, message)  # Llamado desde otro thread
```

### 2. La UI no importa del motor

Los componentes en `app/ui/` reciben callbacks tipados, nunca importan clases del motor:

```python
# BIEN
class Dashboard(ctk.CTkFrame):
    def __init__(self, parent, on_execute: Callable[[], None], ...):

# MAL
from core.runner import TaskRunner  # Prohibido en app/ui/
```

### 3. Mensajes en español, lenguaje de negocio

Todo texto visible al contador:
- Siempre en español
- Sin terminología técnica (no "timeout", "exception", "thread")
- Orientado a acción: "No se pudo descargar. Podés completar este paso manualmente."

### 4. Estados visuales de tareas

| Estado | Icono | Color | Texto |
|---|---|---|---|
| Pendiente | Reloj | Gris | "Pendiente" |
| En progreso | Spinner | Azul | "Descargando..." |
| Completado | Check | Verde | "Completado (Xs)" |
| Error | X | Rojo | "Falló — [mensaje simple]" |

### 5. Layout estándar

- Ventana principal: 900x650, no redimensionable
- Sidebar izquierdo: logo + info de sesión
- Centro: lista de tareas con scroll
- Footer: botón "Ejecutar todo" prominente + selector de período

### 6. Componentes definidos en el PRD

| Archivo | Responsabilidad |
|---|---|
| `dashboard.py` | Ventana principal, lista de tareas |
| `task_status.py` | Fila visual de cada tarea |
| `session_panel.py` | Panel de health check |
| `date_selector.py` | Selector de período |
| `manual_upload.py` | Diálogo de carga manual |
| `alert_modal.py` | Modal de error con opción manual |

---

## Anti-patrones

- No usar `grid()` y `pack()` mezclados en el mismo contenedor
- No crear ventanas nuevas (Toplevel) para estados — usar frames que se muestran/ocultan
- No bloquear el hilo principal con `time.sleep()` — usar `after()` para delays
- No hardcodear colores — usar el tema de CustomTkinter
