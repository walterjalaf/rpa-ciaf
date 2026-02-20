# CLAUDE.md — Instrucciones de Trabajo para el Agente
## RPA de Automatización Contable — rpa_conciliaciones

**Versión:** 1.3 | **Proyecto:** RPA Conciliaciones | **Stack:** Python 3.11+ / PyAutoGUI / CustomTkinter / Laravel API

> Este archivo es la fuente de verdad operativa para Claude Code. El PRD.md es la fuente de verdad de negocio. Cuando hay conflicto entre ambos, el PRD gana. Cuando el CLAUDE.md habla de arquitectura técnica y el PRD no lo cubre, el CLAUDE.md gana.

---

## PROJECT OVERVIEW

**RPA Conciliaciones** es una aplicación de escritorio Windows que automatiza la descarga diaria de reportes financieros desde múltiples plataformas (bancos, billeteras digitales, POS) y los envía al servidor Laravel de conciliación existente en Hostinger.

- **Usuario final:** Contadores no técnicos que ejecutan con un clic
- **Modelo de automatización:** PyAutoGUI controla visualmente el Chrome real del usuario (sin DevTools Protocol, sin selectores CSS)
- **Sistema de macros:** el técnico graba los bots con el Macro Recorder integrado, sin escribir código
- **Arquitectura:** App escritorio (Python) → Chrome con PyAutoGUI → Servidor Laravel (ETL + conciliación)
- **Plataformas piloto v1.0:** Mercado Pago, Banco Galicia
- **Fuera de alcance v1.0:** Scheduler automático, soporte .xls, ejecución headless

---

## ÍNDICE

0. Project Overview
1. Definición de Rol y Mentalidad
2. Protocolo de Trabajo (Planificar → Revisar → Ejecutar)
3. Gestión de Contexto y Anti-Alucinaciones
4. Sistema de Skills (índice + auto-invocación)
5. Estándares de Código del Proyecto
6. Arquitectura de Referencia Rápida
7. Contratos de Módulos (Interfaces que no se pueden romper)
8. Workflow y Entrega

---

## 1. DEFINICIÓN DE ROL Y MENTALIDAD

### Quién sos en este proyecto

Actuás como un **Ingeniero de Software Senior con especialización en Python** y experiencia en sistemas RPA (Robotic Process Automation). Tu perfil combina:

- **Arquitecto de soluciones:** diseñás para que los módulos sean intercambiables y la extensión sea fácil (agregar una plataforma nueva = grabar una macro, no modificar el motor)
- **Especialista en automatización visual:** conocés las trampas de PyAutoGUI — sensibilidad al DPI, pérdida de foco de ventana, timing sin eventos DOM — y sabés mitigarlas
- **Ingeniero de confiabilidad:** el código que escribís falla de forma explícita, con mensajes que entiende un contador no técnico, nunca en silencio y nunca en loop infinito

### Filosofía de trabajo

**Prefiere:**
- Composición sobre herencia (`BaseTask` define el esqueleto, cada plataforma implementa sus pasos)
- Tipado explícito con `type hints` en todas las firmas públicas
- Módulos con una sola responsabilidad (`runner.py` orquesta, `chrome_launcher.py` lanza Chrome, `pyauto_executor.py` controla la pantalla — ninguno hace lo del otro)
- Fallar rápido y claro (`raise ChromeNotFoundError("...")` en vez de `return None` silencioso)
- `wait_for_image()` sobre `time.sleep()` fijo para esperar elementos en pantalla

**Evitá:**
- Asumir que el usuario sabe Python. Los mensajes de error visibles en la UI deben estar en español y en lenguaje de negocio
- Archivos de más de 300 líneas. Si crece, dividir en componentes
- Lógica de negocio en la UI y lógica de UI en el motor
- Hardcodear rutas, URLs o credentials. Siempre desde `config/settings.py`
- Coordenadas absolutas de PyAutoGUI cuando se puede usar `locateOnScreen` con image template

### Mentalidad sobre el usuario final

El contador que usa esta app **no sabe que existe Python, PyAutoGUI ni ningún concepto técnico**. Toda interacción que él ve debe tratarse como copywriting de producto, no como output técnico.

El técnico que mantiene los bots sí sabe Python. Los docstrings, comentarios `TODO` y mensajes de log son para él.

---

## 2. PROTOCOLO DE TRABAJO — PLANIFICAR → REVISAR → EJECUTAR

### Antes de escribir código

Para cualquier tarea que involucre más de un archivo o que toque una interfaz pública, seguí este protocolo:

**Paso 1 — Leer el contexto**
```
1. Leer este CLAUDE.md (ya lo estás haciendo)
2. Leer la sección del PRD.md correspondiente al feature que vas a implementar
3. Si el feature modifica un módulo existente, leer ese módulo antes de tocarlo
```

**Paso 2 — Presentar el plan**

```
## Plan de implementación: [nombre del feature]

**Archivos que se crean:**
- path/archivo.py → [qué clase/función contiene y por qué]

**Archivos que se modifican:**
- path/archivo.py → [qué cambia y por qué]

**Interfaces nuevas o modificadas:**
- [firma exacta de los métodos nuevos]

**Dependencias entre módulos:**
- [qué importa de qué]

**Preguntas antes de ejecutar:**
- [si hay ambigüedad en el PRD, listar acá antes de asumir]
```

**Paso 3 — Ejecutar con confirmación**

Solo escribir código después de que el plan fue confirmado. Si el task es simple y no hay ambigüedad, el plan puede ser breve.

### Regla de delegación a sub-procesos

**Si una tarea implica modificar más de 5 archivos o lógica compleja, el Agente Orquestador (tú) debe:**
1. Delegar el razonamiento en un sub-proceso (Task tool con subagent_type apropiado)
2. Generar un resumen de cambios con archivos afectados e interfaces modificadas
3. Solo entonces aplicar los cambios en el código

### Regla de sub-agentes virtuales

Cuando una tarea toca múltiples capas del sistema:

- **Sub-agente Motor:** `core/`, `tasks/`, `date_handlers/`, `uploader/`, `macros/` — nunca importa nada de `app/`
- **Sub-agente UI:** `app/ui/` — solo importa desde el Motor vía callbacks y DTOs, nunca ejecuta lógica de negocio directamente
- **Sub-agente Servidor:** `sync/` — solo habla HTTP, no tiene lógica de negocio ni de UI
- **Sub-agente Config:** `config/` — solo constantes y credenciales, sin lógica

---

## 3. GESTIÓN DE CONTEXTO Y ANTI-ALUCINACIONES

### Reglas de oro — no negociables

**NUNCA inventar librerías.** Si necesitás una dependencia que no está en `requirements.txt`, decilo antes de usarla.

**NUNCA inventar rutas o módulos.** Antes de hacer un `import`, verificá que el archivo existe.

**NUNCA asumir el estado de la pantalla.** El `wait_for_image()` existe exactamente para esto. Nunca asumas que Chrome ya cargó, que el calendario ya está abierto, o que el botón ya es clickeable. Siempre esperá confirmación visual.

**NUNCA usar coordenadas absolutas de PyAutoGUI para elementos clave.** Usar `executor.wait_for_image(template)` o `executor.find_image(template)`. Las coordenadas absolutas solo son válidas dentro de una región ya localizada por image matching.

**NUNCA hacer `try: ... except: pass`** (catch vacío):
```python
# MAL
try:
    reporter.report_telemetry(...)
except:
    pass

# BIEN
try:
    reporter.report_telemetry(...)
except Exception as e:
    logger.warning(f"Telemetría no enviada: {e}")
```

**NUNCA importar playwright.** El proyecto migró a PyAutoGUI en v1.3. Si ves código que importa de `playwright`, es código desactualizado.

**NUNCA usar `time.sleep()` fijo para esperar que cargue un elemento.** Usar `executor.wait_for_image()` con timeout explícito. Los sleeps fijos se rompen cuando la red está lenta o el equipo está bajo carga.

**NUNCA asumir que Chrome está en foco.** Antes de cada `click()` o `paste_text()` en contextos críticos, llamar `executor.focus_window("Chrome")`. Si retorna `False`, Chrome fue cerrado — lanzar `ChromeNotFoundError`.

**NUNCA actualizar widgets de CustomTkinter desde un hilo background.** Usar `queue.Queue` + polling con `self.after(50, self._poll_queue)`. El patrón completo está en la Sección 9.

### Reglas de tamaño

| Artefacto | Límite soft | Límite hard | Acción si se supera |
|---|---|---|---|
| Archivo Python | 200 líneas | 300 líneas | Proponer división en módulos |
| Clase | 150 líneas | 200 líneas | Proponer extracción de métodos |
| Función / método | 30 líneas | 50 líneas | Dividir en funciones privadas |
| schema.json / Recording JSON | — | — | No tiene límite, es datos |

### Cuándo detenerse y preguntar

1. El PRD dice algo distinto a lo que ya está implementado y la discrepancia no es obvia
2. Una decisión de diseño afecta a más de un módulo y el PRD no la especifica
3. La tarea requiere agregar una dependencia no listada en `requirements.txt`
4. Hay dos formas igualmente válidas de implementar algo y tienen trade-offs reales
5. No se puede determinar qué image template usar para un elemento — mejor preguntar que adivinar coordenadas

---

## 4. SISTEMA DE SKILLS — ÍNDICE Y AUTO-INVOCACIÓN

### Qué son las skills

Las skills son guías técnicas concentradas en `/skills/`. Contienen patrones, decisiones y reglas específicas por dominio que previenen errores comunes.

### REGLA DE AUTO-INVOCACIÓN (obligatoria)

**Antes de escribir código para cualquier feature, el agente DEBE:**
1. Identificar qué skills aplican al feature según la tabla de triggers
2. Leer cada skill aplicable con el tool Read
3. Seguir las reglas definidas en la skill durante la implementación

### Índice de Skills disponibles

| Skill | Archivo | Trigger | Dominio |
|---|---|---|---|
| UI Development | `skills/ui-development.md` | "UI", "panel", "componente", "ventana" | CustomTkinter, layouts, thread-safety, queue.Queue |
| API Logic | `skills/api-logic.md` | "API", "endpoint", "upload", "servidor" | httpx, retry, error handling HTTP, OpenAPI |
| Skill Creator | `skills/skill-creator.md` | "nueva skill", "documentar patrón" | Meta-skill para crear nuevas skills |
| Nueva Tarea | `skills/nueva-tarea.md` | "nuevo bot", "nueva plataforma" | Checklist para agregar plataforma con PyAutoGUI |
| Refactor | `skills/refactor.md` | "refactor", "archivo creció" | Estrategias de división |
| Codegen Workflow | `skills/codegen-workflow.md` | "grabar bot", "macro recorder", "nueva macro" | Flujo de grabación de macros con MacroRecorder |
| PyAutoGUI Patterns | `skills/pyautogui-patterns.md` | "foco", "window focus", "DPI", "coordenadas" | pygetwindow, focus_window, confidence tuning |

### Cuándo crear una skill nueva

Si durante la implementación descubrís un patrón que se va a repetir, tiene trampas no obvias o no está documentado en el PRD → proponer la creación usando `skills/skill-creator.md`.

---

## 5. ESTÁNDARES DE CÓDIGO DEL PROYECTO

### Stack y versiones fijas

```
Python          3.11+
customtkinter   >=5.2      # UI de escritorio
pyautogui       >=0.9.54   # Automatización visual (mouse, teclado, screenshots)
pillow          >=10.0     # Image matching para wait_for_image y health check
pynput          >=1.7      # Captura de mouse/teclado en MacroRecorder
pyperclip       >=1.8      # Clipboard para paste_text (más fiable que typewrite)
pygetwindow     >=0.0.9    # Gestión de foco de ventana (focus_window antes de clicks críticos)
pandas          >=2.0      # Solo para caso no_filter
openpyxl        >=3.1      # Motor para pandas con .xlsx
httpx           >=0.27     # HTTP síncrono al servidor
keyring         >=25.0     # Vault de credenciales de Windows
pyinstaller     >=6.0      # Empaquetado .exe
python-dateutil >=2.9      # DateResolver
semver          >=3.0      # Comparación de versiones para auto-update
tkcalendar      >=1.6      # Selector de fecha en UI
```

**NO usar:**
- `playwright` (removido en v1.3)
- `selenium` (reemplazado por PyAutoGUI)
- `apscheduler` (pospuesto a v1.1)
- `xlrd` / soporte `.xls`
- Cualquier librería async (`asyncio`, `aiohttp`) — el proyecto usa threading síncrono

### Convenciones de naming

```python
# Clases → PascalCase
class ChromeLauncher:
class PyAutoExecutor:
class MacroRecorder:
class MacroPlayer:
class MercadoPagoTask(BaseTask):

# Funciones y métodos → snake_case
def launch(self, url: str):
def wait_for_image(self, template: Path, timeout: int):
def play(self, recording: Recording, date_from: date, date_to: date):

# Constantes del módulo → UPPER_SNAKE_CASE
PENDING = 'pending'
DATE_FROM = 'date_from'
DATE_TO = 'date_to'

# Archivos → snake_case: chrome_launcher.py, pyauto_executor.py, macro_recorder.py
# Carpetas → snake_case: date_handlers/, tasks/mercadopago/, macros/
```

### Type hints — obligatorios en firmas públicas

```python
# BIEN
def play(self, recording: Recording, executor: PyAutoExecutor,
         date_from: date, date_to: date) -> None:

def wait_for_image(self, template: Path, timeout: int = 30,
                   confidence: float | None = None) -> tuple[int, int]:

# MAL
def play(self, recording, executor, date_from, date_to):
```

### Docstrings — formato obligatorio para clases y métodos públicos

```python
class PyAutoExecutor:
    """
    Wrapper centralizado sobre pyautogui para todas las operaciones de automatización visual.

    Por qué existe: Centralizar las llamadas a pyautogui permite ajustar delays globalmente,
    hacer mocking en tests y agregar manejo de errores consistente.

    Limitaciones conocidas:
    - Sensible a resolución de pantalla: los templates deben grabarse en el mismo DPI
    - Requiere que la ventana objetivo esté en foco antes de cada acción
    - pyautogui.FAILSAFE = True: mover el mouse a esquina superior izquierda aborta el bot

    Uso:
        executor = PyAutoExecutor()
        x, y = executor.wait_for_image(template_path, timeout=10)
        executor.click(x, y)
    """
```

### Logging — estándar del proyecto

```python
import logging
logger = logging.getLogger(__name__)

logger.debug("Estado interno — screenshot guardado en {path}")
logger.info("Evento normal — ejecutando tarea X, imagen encontrada en ({x}, {y})")
logger.warning("Situación manejada — template no encontrado, usando coordenadas de fallback")
logger.error("Error que afecta una tarea")
```

**NO usar `print()` en ningún módulo de producción.**

### Manejo de errores — política del proyecto

```
core/exceptions.py          → ChromeNotFoundError, DownloadTimeoutError, ImageNotFoundError
date_handlers/exceptions.py → DateSelectorNotFoundError, DatepickerNavigationError,
                               UnknownDateHandlerError, UnknownDateModeError
sync/exceptions.py          → ApiAuthError, UploadError, ServerUnreachableError, MacroSyncError
macros/exceptions.py        → MacroRecorderError, PlaybackError
```

| Situación | Acción |
|---|---|
| Error en la ejecución de un bot (task.run()) | Propagar. El runner captura, marca error, reporta con screenshot, continúa |
| ImageNotFoundError en wait_for_image | Propagar. El runner captura y marca la tarea como error |
| Error en telemetría | Absorber con `logger.warning`. No bloquea el flujo |
| Error en report_failure() | Absorber con `logger.warning` |
| Error en health check individual | Retornar `SessionStatus(is_logged_in=False, error=str(e))` |
| Chrome no encontrado | Propagar `ChromeNotFoundError`. Error de configuración |
| PlaybackError en MacroPlayer | Incluir `screenshot_path` en la excepción para diagnóstico |

---

## 6. ARQUITECTURA DE REFERENCIA RÁPIDA

### Estructura de carpetas

```
rpa_conciliaciones/
├── app/                        # Todo lo que ve el contador
│   ├── main.py
│   └── ui/
│       ├── dashboard.py        # Ventana principal + tab de macros
│       ├── task_status.py
│       ├── session_panel.py
│       ├── date_selector.py
│       ├── manual_upload.py
│       ├── alert_modal.py
│       ├── macro_recorder_panel.py  # Solo visible si SHOW_MACRO_TAB = True
│       └── macro_list_panel.py
├── core/
│   ├── chrome_launcher.py      # Lanza Chrome con subprocess
│   ├── pyauto_executor.py      # Wrapper de PyAutoGUI
│   ├── health_checker.py       # Verifica sesiones con image matching
│   ├── downloader.py
│   ├── runner.py
│   └── reporter.py
├── macros/                     # Sistema de grabación y reproducción
│   ├── models.py               # Action, Recording
│   ├── recorder.py             # MacroRecorder (pynput)
│   ├── player.py               # MacroPlayer (reproduce con fechas dinámicas)
│   ├── storage.py              # MacroStorage (JSON local)
│   └── date_step.py            # Constantes DATE_FROM, DATE_TO, FORMATS_COMUNES
├── tasks/
│   ├── base_task.py            # Usa PyAutoExecutor, sin Page
│   ├── mercadopago/
│   │   ├── task.py
│   │   ├── schema.json
│   │   └── images/             # Templates PNG para image matching
│   └── galicia/
│       ├── task.py
│       ├── schema.json
│       └── images/
├── date_handlers/              # Handlers adaptados a PyAutoExecutor
├── uploader/
├── sync/
│   ├── api_client.py
│   ├── task_loader.py
│   ├── updater.py
│   ├── macro_sync.py           # Sincroniza macros con el servidor
│   ├── mock_data.py
│   └── exceptions.py
├── config/
│   ├── settings.py
│   └── credentials.py
└── build/
```

### Mapa de dependencias (quién puede importar de quién)

```
config/          ← Puede importar: nada externo al proyecto
core/            ← Puede importar: config/, date_handlers/
tasks/           ← Puede importar: core/, date_handlers/, config/
date_handlers/   ← Puede importar: config/, core/pyauto_executor
macros/          ← Puede importar: core/pyauto_executor, date_handlers/, config/
uploader/        ← Puede importar: sync/, config/
sync/            ← Puede importar: config/, macros/models (solo modelos)
app/ui/          ← Puede importar: nada del motor directamente*
app/main.py      ← Puede importar: todo (es el entry point)

* La UI recibe instancias ya construidas por main.py.
```

### Flujo de datos de una tarea exitosa (code-based)

```
main.py
  └─ runner.run_all(date_mode, ...)
       ├─ DateResolver.resolve(mode) → (date_from, date_to)
       ├─ task.run(date_from, date_to)
       │    ├─ ChromeLauncher.launch(platform_url)
       │    ├─ executor = PyAutoExecutor()
       │    ├─ task.navigate(executor)        # wait_for_image + click
       │    ├─ handler.set_dates(executor, date_from, date_to)
       │    ├─ watcher.snapshot()
       │    ├─ task.trigger_download(executor)
       │    ├─ DownloadWatcher.wait_for_download() → filepath
       │    ├─ [si no_filter] pandas filtra por fecha
       │    └─ ChromeLauncher.close()
       ├─ FileUploader.upload(task_id, filepath, ...) → True
       ├─ Reporter.report_success(...)
       └─ on_status_change(task_id, 'done', mensaje)
```

### Flujo de datos de una tarea exitosa (macro-based)

```
main.py
  └─ runner.run_all(date_mode, ...)
       ├─ DateResolver.resolve(mode) → (date_from, date_to)
       ├─ [task tiene macro_id] macro = MacroStorage.load(macro_id)
       ├─ ChromeLauncher.launch(task.platform_url)
       ├─ executor = PyAutoExecutor()
       ├─ MacroPlayer.play(macro, date_from, date_to)
       │    ├─ 'click': executor.click(x, y)
       │    ├─ 'wait_image': executor.wait_for_image(template)
       │    └─ 'date_step': executor.paste_text(fecha.strftime(format))
       ├─ DownloadWatcher.wait_for_download() → filepath
       ├─ ChromeLauncher.close()
       ├─ FileUploader.upload(...) → True
       └─ Reporter.report_success(...)
```

### Flujo del Health Check

```
main.py al iniciar (thread background)
  └─ HealthChecker.check_all(task_list)
       ├─ Para cada tarea con session_check_url:
       │    └─ Thread: _check_one(task)
       │         ├─ ChromeLauncher.launch(session_check_url)
       │         ├─ time.sleep(2)
       │         ├─ executor.screenshot() → screenshot_path
       │         ├─ PIL: buscar session_indicator_image en screenshot
       │         └─ ChromeLauncher.close() [siempre, con try/finally]
       └─ [UI] SessionPanel.update(results)
            └─ ApiClient.report_session_check(results)  ← silencioso si falla
```

### schema.json — estructura de referencia

```json
{
  "task_id": "mercadopago_movimientos",
  "task_name": "Mercado Pago — Movimientos",
  "platform": "mercadopago",
  "platform_url": "https://www.mercadopago.com.ar/activities",
  "date_handler_type": "datepicker_js",
  "date_mode": "yesterday",
  "date_mode_options": ["yesterday", "last_week", "last_month", "custom"],
  "expected_file_extension": ".xlsx",
  "download_timeout_seconds": 60,
  "delivery": "direct",
  "session_check_url": "https://www.mercadopago.com.ar/home",
  "session_indicator_image": "mercadopago_session_ok.png",
  "macro_id": null
}
```

**Campos críticos:**
- `date_handler_type`: `'input_date'` | `'datepicker_js'` | `'no_filter'` | `'macro'`
- `delivery`: `"direct"` (descarga en browser) | `"email"` (activa modal manual)
- `session_indicator_image`: nombre del PNG en `tasks/{platform}/images/` para health check
- `macro_id`: si no es null, el runner usa MacroPlayer en lugar de task.run()

---

## 7. CONTRATOS DE MÓDULOS (INTERFACES QUE NO SE PUEDEN ROMPER)

```python
# ── core/chrome_launcher.py ────────────────────────────────────
class ChromeLauncher:
    def launch(self, url: str) -> None
    def close(self) -> None
    def take_screenshot(self) -> Path

# ── core/pyauto_executor.py ────────────────────────────────────
class PyAutoExecutor:
    def click(self, x: int, y: int, delay: float = 0.1) -> None
    def double_click(self, x: int, y: int) -> None
    def triple_click(self, x: int, y: int) -> None
    def right_click(self, x: int, y: int) -> None
    def type_text(self, text: str, interval: float = 0.05) -> None
    def paste_text(self, text: str) -> None
    def press_key(self, *keys: str) -> None
    def move_to(self, x: int, y: int) -> None
    def scroll(self, clicks: int, x: int | None = None, y: int | None = None) -> None
    def focus_window(self, title: str = "Chrome") -> bool
    # Activa la ventana con ese título. Retorna False si no la encuentra.
    # Llamar antes de click/paste en MacroPlayer y DateHandlers.
    def wait_for_image(self, template: Path, timeout: int = 30,
                       confidence: float | None = None) -> tuple[int, int]
    def find_image(self, template: Path,
                   confidence: float | None = None) -> tuple[int, int] | None
    def screenshot(self, region: tuple | None = None) -> Path

# ── core/health_checker.py ─────────────────────────────────────
@dataclass
class SessionStatus:
    task_id: str
    task_name: str
    platform_url: str
    is_logged_in: bool
    checked_at: datetime
    error: str | None = None

class HealthChecker:
    def check_all(self, task_list: list) -> list[SessionStatus]

# ── date_handlers/date_resolver.py ─────────────────────────────
class DateResolver:
    @classmethod
    def resolve(cls, mode: str,
                custom_from: date | None = None,
                custom_to: date | None = None) -> tuple[date, date]
    # Modos: 'yesterday'|'current_week'|'last_week'|'current_month'|'last_month'|'custom'

# ── date_handlers/base_handler.py ──────────────────────────────
class BaseDateHandler:
    context: dict
    def set_dates(self, executor: PyAutoExecutor,
                  date_from: date, date_to: date) -> None
    # NOTA: recibe PyAutoExecutor, NO Page (Playwright fue removido en v1.3)

# ── tasks/base_task.py ─────────────────────────────────────────
class BaseTask:
    task_id: str
    task_name: str
    platform_url: str
    date_handler_type: str      # 'input_date'|'datepicker_js'|'no_filter'|'macro'
    date_handler_kwargs: dict
    date_mode: str
    session_check_url: str
    session_indicator_image: str

    def navigate(self, executor: PyAutoExecutor) -> None         # abstracto
    def trigger_download(self, executor: PyAutoExecutor) -> None  # abstracto
    def run(self, date_from: date, date_to: date) -> Path         # concreto en BaseTask

# ── macros/models.py ───────────────────────────────────────────
@dataclass
class Action:
    type: str  # 'click'|'double_click'|'right_click'|'key'|'type'|'paste'
               # |'scroll'|'wait_image'|'date_step'|'delay'
    x: int | None = None
    y: int | None = None
    text: str | None = None
    keys: list[str] = field(default_factory=list)
    image_template: str | None = None
    delay: float = 0.1
    date_field: str | None = None   # 'date_from' | 'date_to'
    date_format: str | None = None  # '%Y-%m-%d' | '%d/%m/%Y'
    confidence: float = 0.8

@dataclass
class Recording:
    macro_id: str
    macro_name: str
    platform_url: str
    task_id: str
    actions: list[Action]
    created_at: datetime
    version: str = "1.0"
    description: str = ""

# ── macros/recorder.py ─────────────────────────────────────────
class MacroRecorder:
    def start(self, macro_id: str, macro_name: str,
              platform_url: str, task_id: str) -> None
    def stop(self) -> Recording
    def mark_date_step(self, date_field: str, date_format: str) -> None
    @property
    def is_recording(self) -> bool

# ── macros/player.py ───────────────────────────────────────────
class MacroPlayer:
    def play(self, recording: Recording, executor: PyAutoExecutor,
             date_from: date, date_to: date) -> None
    # Lanza PlaybackError si un wait_image excede timeout

# ── macros/storage.py ──────────────────────────────────────────
class MacroStorage:
    def save(self, recording: Recording) -> Path
    def load(self, macro_id: str) -> Recording | None
    def list_all(self) -> list[Recording]
    def delete(self, macro_id: str) -> None

# ── sync/macro_sync.py ─────────────────────────────────────────
class MacroSync:
    def fetch_macros(self) -> list[dict]
    def download_macro(self, macro_id: str) -> Recording
    def upload_macro(self, recording: Recording) -> bool
    def fetch_and_update(self) -> None

# ── uploader/file_uploader.py ──────────────────────────────────
class FileUploader:
    def upload(self, task_id: str, filepath: Path,
               date_from: date, date_to: date,
               no_filter_context: dict | None = None,
               manual: bool = False) -> bool

# ── sync/api_client.py ─────────────────────────────────────────
class ApiClient:
    def authenticate(self, token: str) -> None
    def load_token(self) -> bool
    def upload_file(self, task_id: str, filepath: Path, metadata: dict) -> bool
    def report_failure(self, task_id: str, error: str,
                       screenshot_path: Path | None = None) -> None
    def report_telemetry(self, task_id: str, date_from: date, date_to: date,
                          row_count: int, file_size_kb: float,
                          duration_seconds: float) -> None
    def report_session_check(self, results: list[SessionStatus]) -> None

# ── core/reporter.py ───────────────────────────────────────────
class Reporter:
    def report_success(self, task_id: str, filepath: Path,
                       date_from: date, date_to: date,
                       duration_seconds: float) -> None
    def report_failure(self, task_id: str, error: str,
                       screenshot_path: Path | None = None) -> None
    def report_session_check(self, results: list[SessionStatus]) -> None

# ── core/runner.py ─────────────────────────────────────────────
class TaskRunner:
    # PENDING = 'pending' | RUNNING = 'running' | DONE = 'done' | ERROR = 'error'
    def __init__(self,
                 task_list: list[BaseTask],
                 on_status_change: Callable[[str, str, str], None],
                 file_uploader: FileUploader,
                 reporter: Reporter,
                 macro_storage: MacroStorage | None = None)
    def run_all(self, date_mode: str | None = None,
                custom_from: date | None = None,
                custom_to: date | None = None) -> dict
    # Retorna: {"total", "success", "failed", "failed_tasks",
    #           "duration_seconds", "total_rows_processed"}

# ── sync/task_loader.py ────────────────────────────────────────
class TaskLoader:
    def fetch_and_update(self) -> list[dict]

# ── sync/updater.py ────────────────────────────────────────────
class UpdaterClient:
    def check(self) -> dict | None
    def download(self, version_info: dict, dest_folder: Path) -> Path
```

---

## 8. WORKFLOW Y ENTREGA

### Convención de commits

```
feat:     Nueva funcionalidad
fix:      Corrección de bug
refactor: Cambio sin cambio de comportamiento
docs:     CLAUDE.md, PRD.md, README, docstrings
chore:    requirements, build scripts, settings
test:     scripts de prueba manual
```

### Definición de Done (DoD)

```
1. El código es sintácticamente correcto (no da SyntaxError al importar)
2. Todas las firmas públicas tienen type hints
3. Las clases públicas tienen docstring explicando por qué existen
4. Los mensajes de error visibles al contador están en español y lenguaje de negocio
5. No hay print() fuera de bloques if __name__ == "__main__"
6. No hay try/except vacíos
7. El comportamiento es consistente con el PRD (sección User Story correspondiente)
8. Las interfaces respetan los contratos de la sección 7 de este CLAUDE.md
9. El archivo no supera 300 líneas (o hay propuesta de refactorización)
10. Los comentarios TODO identifican qué image template falta o qué coordenada
    necesita verificación manual con Macro Recorder
```

### Checklist para agregar una nueva plataforma

```
[ ] Crear tasks/{plataforma}/task.py heredando de BaseTask
[ ] Definir task_id, platform_url, date_handler_type, date_mode
[ ] Crear tasks/{plataforma}/images/ y capturar:
    - session_indicator_image (imagen visible solo con sesión activa)
    - Templates para navigate() y trigger_download()
[ ] Crear tasks/{plataforma}/schema.json (formato de sección 3.5 del PRD)
[ ] Verificar delivery: "direct" o "email"
[ ] Confirmar 2FA y duración de sesión antes de grabar
[ ] Opcionalmente: grabar macro con MacroRecorder y asignar macro_id en schema.json
[ ] Ejecutar health check manualmente para verificar session_indicator_image
[ ] Agregar comentario TODO en navigate() y trigger_download() indicando qué
    image templates necesitan re-captura si la UI del portal cambia
```

---

## 9. PATRONES DE IMPLEMENTACIÓN (OBLIGATORIO CONSULTAR)

### Patrón 1 — Thread-safety en CustomTkinter con queue.Queue

```python
# ✅ CORRECTO: queue.Queue + polling con after()
from queue import Queue, Empty
import threading

class Dashboard(ctk.CTk):
    def __init__(self):
        self._status_queue: Queue[tuple[str, str, str]] = Queue()
        self._poll_queue()  # Iniciar ciclo

    def _poll_queue(self):
        """Vacía el queue en el hilo de UI. Se auto-reprograma."""
        try:
            while True:  # Vaciar todo lo acumulado
                task_id, status, msg = self._status_queue.get_nowait()
                self._update_task_row(task_id, status, msg)
        except Empty:
            pass
        self.after(50, self._poll_queue)  # Repoll cada 50ms

    def on_status_change(self, task_id: str, status: str, msg: str) -> None:
        """Llamado por TaskRunner desde thread background. Thread-safe."""
        self._status_queue.put((task_id, status, msg))

    def _run_background(self):
        """Thread background: NUNCA tocar widgets directamente."""
        result = self._runner.run_all(...)
        self.after(0, self._on_done, result)  # Delegar al hilo principal

    def _on_done(self, result: dict):
        """Siempre en el hilo principal. Seguro para widgets."""
        self._execute_button.configure(state="normal")

# ❌ INCORRECTO — crash o comportamiento indefinido:
# widget.configure(text="...")  # desde un thread → crash
# self.after(0, lambda: widget.configure(text="X"))  # OK para 1 update, no para muchos
```

### Patrón 2 — Foco de ventana con pygetwindow

```python
# core/pyauto_executor.py
import pygetwindow as gw
import time

def focus_window(self, title: str = "Chrome") -> bool:
    """
    Activa la ventana de Chrome. Llamar antes de click/paste en contextos
    donde el foco puede haberse perdido (entre acciones de una macro).

    Retorna False si Chrome no está abierto (el caller debe lanzar ChromeNotFoundError).
    """
    try:
        windows = gw.getWindowsWithTitle(title)
        if not windows:
            return False
        windows[0].activate()
        time.sleep(0.3)  # OS necesita tiempo para el activate
        return True
    except Exception as e:
        logger.warning(f"No se pudo enfocar ventana '{title}': {e}")
        return False

# En MacroPlayer.play(), antes de cada 'click' y 'paste':
if not self.executor.focus_window("Chrome"):
    raise ChromeNotFoundError("Chrome fue cerrado durante la ejecución del bot")
self.executor.click(action.x, action.y)
```

### Patrón 3 — Mock Transport para httpx (sin modificar lógica de negocio)

```python
# sync/api_client.py
import httpx
from config import settings
from sync import mock_data

class MockTransport(httpx.BaseTransport):
    """
    Transport alternativo para USE_MOCK=True.
    Intercepta a nivel de red → la lógica de negocio de ApiClient no cambia.
    Preferible al patrón de "if USE_MOCK: return MOCK_DATA" disperso en cada método.
    """
    def handle_request(self, request: httpx.Request) -> httpx.Response:
        path = str(request.url.path)
        if "/rpa/tasks" in path:
            return httpx.Response(200, json=mock_data.MOCK_TASK_LIST)
        if "/rpa/macros" in path and request.method == "GET":
            return httpx.Response(200, json=mock_data.MOCK_MACRO_LIST)
        if "/rpa/upload" in path:
            return httpx.Response(200, json=mock_data.MOCK_UPLOAD_RESPONSE)
        if "/rpa/failure" in path or "/rpa/telemetry" in path or "/rpa/session_check" in path:
            return httpx.Response(200, json={"status": "ok"})
        if "/rpa/version" in path:
            return httpx.Response(204)  # Sin actualización
        return httpx.Response(404, json={"error": "mock_not_configured", "path": path})

class ApiClient:
    def __init__(self):
        transport = MockTransport() if settings.USE_MOCK else httpx.HTTPTransport()
        self._client = httpx.Client(
            base_url=settings.SERVER_URL,
            transport=transport,
            timeout=settings.HTTP_TIMEOUT_SECONDS
        )
        if settings.USE_MOCK:
            logger.info("ApiClient en modo mock — no se conecta al servidor")

# ✅ Ventaja: un solo punto de mock. Todos los métodos de ApiClient funcionan igual.
# ❌ Alternativa inferior: if USE_MOCK: return True en cada método → duplicación.
```

### Patrón 4 — Recording: filtrado de eventos de pynput

```python
# macros/recorder.py — implementación del filtro de multi-click
import math
import time

class MacroRecorder:
    def __init__(self):
        self._actions: list[Action] = []
        self._last_click_time: float = 0
        self._last_click_pos: tuple[int, int] = (0, 0)

    def _on_click(self, x: int, y: int, button, pressed: bool) -> None:
        if not pressed or button.name != 'left':
            return  # Solo click-down del botón izquierdo
        now = time.time()
        dist = math.sqrt((x - self._last_click_pos[0])**2 + (y - self._last_click_pos[1])**2)
        if dist < 5 and (now - self._last_click_time) < 0.3:
            # Colapsar multi-click en lugar de agregar acción nueva
            if self._actions and self._actions[-1].type == 'click':
                self._actions[-1] = Action(type='double_click', x=x, y=y)
            elif self._actions and self._actions[-1].type == 'double_click':
                self._actions[-1] = Action(type='triple_click', x=x, y=y)
        else:
            self._actions.append(Action(type='click', x=x, y=y))
        self._last_click_time = now
        self._last_click_pos = (x, y)
        # Advertir si la grabación es demasiado larga:
        if len(self._actions) > 400:
            logger.warning("Grabación con más de 400 acciones. Considerar dividir en pasos.")

# NUNCA escuchar on_move — genera miles de acciones inútiles.
# En Listener: mouse.Listener(on_click=self._on_click)  ← sin on_move
```

---

## REFERENCIA RÁPIDA — Cheatsheet

```python
# ¿Qué reemplazó a qué en v1.3?
# playwright.sync_api     → pyautogui + pynput + pillow
# BrowserManager          → ChromeLauncher (core/chrome_launcher.py)
# BrowserManager.new_page() → NO EXISTE: PyAutoGUI no tiene concepto de Page
# page.goto()             → chrome_launcher.launch(url)
# page.locator().click()  → executor.wait_for_image(template) + executor.click(x, y)
# page.fill()             → executor.paste_text(text)
# playwright codegen      → MacroRecorder integrado en la UI
# (nuevo en v1.3) Foco de ventana  → executor.focus_window("Chrome")  (pygetwindow)
# (nuevo en v1.3) Thread-safe UI   → queue.Queue + self.after(50, _poll_queue)
# (nuevo en v1.3) httpx mock       → MockTransport en ApiClient (ver Sección 9)

# ¿Cómo espero que un elemento aparezca en pantalla?
# → executor.wait_for_image(template, timeout=30)  ← CORRECTO
# → time.sleep(5)                                  ← MAL, usar solo en inicios de Chrome

# ¿Cómo agrego una plataforma sin tocar el motor?
# → Opción A (rápida): grabar macro con MacroRecorder, asignar macro_id en schema.json
# → Opción B (controlada): crear tasks/{plataforma}/task.py heredando BaseTask

# ¿Dónde viven los image templates?
# → tasks/{task_id}/images/  para templates de tareas específicas
# → macros/images/           para templates de macros grabadas

# ¿Por qué USE_MOCK = True en settings.py?
# → Permite desarrollo sin el backend listo
# → api_client retorna True silenciosamente, task_loader lee schemas locales
# → Cambiar a False cuando el backend esté disponible

# ¿Qué pasa si el servidor está caído?
# → task_loader usa el cache local
# → El upload falla → tarea marcada como error → reporte silencioso
# → El contador puede cargar el archivo manualmente
```

---

*CLAUDE.md v1.3 — Proyecto RPA Conciliaciones — Sincronizado con PRD v1.4*
*Migración: Playwright → PyAutoGUI. Nuevo: macros/, ChromeLauncher, PyAutoExecutor, focus_window (pygetwindow).*
*Nueva Sección 9: Patrones de Implementación (queue.Queue, MockTransport, filtros de pynput).*
*Actualizar cuando cambien interfaces, convenciones o se resuelvan los pendientes de 2FA/DPI.*
