# PRD — RPA de Automatización Contable
### Plataforma de Descarga y Conciliación Automatizada
**Versión 1.3 | Febrero 2026 | Confidencial — Uso Interno**

> **Changelog v1.4:** Mejoras basadas en investigación de mejores prácticas: (1) Sección 3.6 reemplazada por especificación OpenAPI 3.0 con schemas de request/response y códigos de error. (2) Patrón `queue.Queue` documentado en Feature 9 para thread-safety en UI. (3) Filtros de grabación de macros en Feature 11 (no capturar mouse moves, colapso de multi-clic). (4) UX del grabador mejorado en Feature 12 (validaciones, countdown, undo). (5) `pygetwindow` agregado al stack para manejo de foco de ventana. (6) CLAUDE.md actualizado con patrones de implementación concretos.

> **Changelog v1.3:** Migración de Playwright a PyAutoGUI como motor de automatización visual. Nuevo módulo `macros/` para grabación y reproducción de bots sin código (UC-15, UC-16). ChromeLauncher reemplaza a BrowserManager. Date handlers adaptados a PyAutoExecutor. Features 11-12 agregados. Riesgos actualizados con los específicos de automatización visual (resolución de pantalla, foco de ventana, timing).

> **Changelog v1.2:** Health Check de sesiones agregado como pre-flight check (UC-14). Sistema de Telemetría de Negocio agregado en reporter.py. Scheduler automático movido fuera del alcance de v1.0. Soporte .xls eliminado. Riesgo crítico de 2FA documentado.

---

## INSTRUCCIONES PARA CLAUDE CODE

Este documento es la referencia única y completa del proyecto. Cada sección contiene:
- Contexto detallado del problema y la solución
- Decisiones de arquitectura ya tomadas (no proponer alternativas)
- El prompt exacto a ejecutar para construir esa parte del sistema

**Reglas de trabajo:**
1. Leer la sección completa antes de ejecutar el prompt
2. Respetar las interfaces definidas entre módulos exactamente como están documentadas
3. No avanzar al siguiente feature sin confirmación explícita
4. Si algo no está claro en el prompt, preguntar antes de asumir
5. Cada módulo debe tener docstrings completos porque otros módulos dependen de ellos

---

## ÍNDICE

1. Resumen Ejecutivo
2. Alineación Estratégica
3. Stack Técnico y Arquitectura
4. Supuestos, Riesgos y Cuellos de Botella
5. Requisitos y User Stories
6. Métricas de Éxito
7. Guía de Desarrollo con Claude Code (12 Features)
8. Alcance y Fuera de Alcance
9. Decisiones Resueltas

---

## 1. RESUMEN EJECUTIVO

### 1.1 Qué es este proyecto

RPA Conciliaciones es una **aplicación de escritorio para Windows** que permite a contadores no técnicos ejecutar, con un solo clic, la descarga automatizada de reportes y extractos de múltiples plataformas financieras. Los archivos descargados son enviados al servidor de conciliación existente, eliminando el trabajo manual diario.

El término RPA significa Robotic Process Automation: software que imita las acciones que haría un humano en una computadora (hacer clic, escribir, navegar webs, descargar archivos) pero de forma automática y sin errores.

### 1.2 El problema concreto que resuelve

La consultora gestiona cuentas en múltiples plataformas financieras simultáneamente:

- **Bancos**: Banco San Juan, Banco Galicia
- **Billeteras digitales**: Mercado Pago, Payway
- **Sistemas de punto de venta**: Toteat, Clover, Foodo
- **Plataformas propias de clientes**: Dragonfish, entre otras

Cada una tiene su propio portal web, su propio sistema de login, su propio formato de exportación y sus propios filtros de fecha. El equipo contable debe ingresar manualmente a cada portal, navegar hasta la sección de reportes, configurar el rango de fechas, descargar el archivo y subirlo al sistema de conciliación. Este proceso se repite todos los días hábiles por cada plataforma y por cada cliente.

**Por qué no se puede resolver con APIs:** Las APIs de bancos requieren habilitación especial y acuerdos formales. Plataformas como Toteat o Dragonfish no ofrecen API pública. Inviable en tiempo y costo.

**La solución elegida:** La aplicación controla visualmente el escritorio usando PyAutoGUI, exactamente como lo haría un operador humano. Mueve el mouse, hace clic, escribe texto y toma capturas de pantalla para verificar el estado. El Chrome que se automatiza es el mismo que el contador tiene abierto con sus sesiones activas. Para el banco o la plataforma, no hay ninguna diferencia entre el humano y el bot.

### 1.3 Quién usa la aplicación y cómo

**El contador (usuario primario):**
- No tiene conocimientos técnicos
- Abre la app al llegar a la oficina
- Ve una lista de tareas con los nombres de las plataformas
- Presiona un botón "Ejecutar todo"
- Se va a tomar un café
- Vuelve y los datos ya están procesados en el servidor de conciliación
- Si algo falla, ve un mensaje claro en lenguaje simple y puede completar ese paso manualmente

**El equipo técnico de la consultora (usuario secundario):**
- Graba los bots una vez por plataforma usando el **Macro Recorder** integrado en la app
- Publica las macros grabadas en el servidor
- Cuando una plataforma cambia su interfaz, re-graba el bot y lo republica en minutos
- Los contadores reciben la macro actualizada automáticamente en el próximo inicio de la app
- No necesita conocer selectores CSS ni código Playwright

**El servidor Laravel en VPS Hostinger (sistema receptor y de control):**
- Receptor de datos: recibe los archivos Excel tal como se descargaron y corre su ETL
- Servidor de actualizaciones: distribuye macros y versiones del .exe a la app de escritorio

### 1.4 Flujo completo en palabras simples

```
El contador abre la app
  → La app se conecta al servidor de actualizaciones
  → Descarga macros actualizadas si hay cambios
  → [PRE-FLIGHT CHECK] La app verifica en background qué sesiones están activas
  → El contador ve el estado de cada sesión: ✅ Galicia activa | ⚠️ Mercado Pago expirada
  → El contador refresca manualmente las sesiones expiradas (30 segundos en Chrome)
  → El contador selecciona el período de fecha
  → Presiona "Ejecutar todo" sabiendo que todas las sesiones están listas
  → Para cada plataforma en la lista:
      → ChromeLauncher abre Chrome en la URL de la plataforma
      → MacroPlayer reproduce los clicks y escrituras grabados
      → Las fechas dinámicas se inyectan en los pasos marcados como DateStep
      → PyAutoExecutor espera la descarga monitoreando la carpeta Downloads
      → Cierra Chrome
      → La app sube el archivo Excel crudo al servidor
      → El servidor corre su ETL y registra telemetría
  → El contador ve: todas las tareas completadas
  → El servidor tiene los datos y ejecuta la conciliación
```

---

## 2. ALINEACIÓN ESTRATÉGICA

### 2.1 Por qué este proyecto existe ahora

El negocio tiene un cuello de botella operativo: la cantidad de clientes que puede atender está limitada por las horas que el equipo contable dedica a tareas manuales repetitivas. Agregar un cliente nuevo significa más tiempo de descarga manual, más posibilidad de error humano, más horas de trabajo.

Este proyecto rompe ese límite. Los bots son reutilizables: una vez grabada la macro de Mercado Pago, sirve para todos los clientes que tengan cuenta en Mercado Pago.

### 2.2 Relación con el sistema existente

El servidor Laravel con el sistema de conciliación ya está construido y funcionando. Este proyecto es la **capa de ingesta de datos** que le faltaba.

```
[App de escritorio]
    ↕ descarga macros + versiones de .exe
[Módulo de actualizaciones — Laravel/Hostinger]  ← NUEVO, parte de este proyecto
    ↕ recibe archivos Excel crudos
[Módulo de conciliación — Laravel/Hostinger]     ← EXISTENTE, no se modifica
    ↓ ETL propio: mapea columnas, detecta errores, notifica
[Sistema de conciliación y arqueos]
```

### 2.3 Impacto esperado

| Objetivo | Situación actual | Con este proyecto |
|---|---|---|
| Tiempo diario en descarga | ~2 horas por contador | < 5 minutos |
| Escalabilidad de clientes | Limitada por horas disponibles | Ilimitada dentro de las plataformas soportadas |
| Tiempo de grabación de nuevo bot | Horas (codegen + debug) | < 15 minutos (macro recorder) |
| Errores en datos | Frecuentes (copia manual) | Mínimos (proceso automatizado) |
| Capacitación de contador nuevo | 1 semana | Menos de 1 hora |

---

## 3. STACK TÉCNICO Y ARQUITECTURA

### 3.1 Por qué este stack y no otro

**Python** es el lenguaje elegido por sus librerías de automatización de escritorio (PyAutoGUI), procesamiento de Excel (pandas), e interfaces de escritorio (CustomTkinter). El equipo técnico ya conoce Python.

**PyAutoGUI** reemplaza a Playwright como motor de automatización. La razón es la universalidad: PyAutoGUI controla cualquier aplicación de escritorio y cualquier sitio web visualmente, sin depender del DevTools Protocol de Chrome. Esto significa:
- No hay selectores CSS frágiles que se rompen con cada update del portal
- El técnico graba el bot como si fuera un ser humano: mueve el mouse, hace clic, escribe
- Una macro grabada funciona en cualquier plataforma que muestre una UI, web o nativa
- Debugging visual: se puede ver exactamente qué está haciendo el bot
- El modelo mental es más simple: "grabé lo que hice y el bot lo repite"

La contra de PyAutoGUI (sensibilidad a resolución de pantalla y posición de ventanas) se mitiga usando detección de imágenes (`pyautogui.locateOnScreen`) en lugar de coordenadas absolutas donde sea posible.

**CustomTkinter** para la UI porque es simple, se ve moderno, no requiere conocer frameworks complejos y el resultado es un .exe que instala cualquier persona.

**No se usa una base de datos local** porque el estado de la app es efímero: las macros del día se descargan del servidor al iniciar, se ejecutan, y los resultados van al servidor.

### 3.2 Stack completo con versiones mínimas

| Capa | Librería | Versión mínima | Rol exacto en el sistema |
|---|---|---|---|
| UI de escritorio | customtkinter | 5.2 | Panel principal, lista de tareas, health check panel, macro recorder |
| Automatización visual | pyautogui | 0.9.54 | Mueve mouse, hace clic, escribe texto, toma screenshots |
| Reconocimiento de imágenes | pillow | 10.0 | Image templates para localizar elementos en pantalla |
| Captura de eventos | pynput | 1.7 | Escucha mouse y teclado durante la grabación de macros |
| Clipboard | pyperclip | 1.8 | Pegar texto en campos de fecha (más fiable que typewrite) |
| Variables de fecha | python-dateutil | 2.9 | DateResolver: calcula date_from/date_to según el modo |
| Procesamiento archivos | pandas + openpyxl | 2.0 / 3.1 | Solo para caso no_filter: filtrar filas por fecha. Solo .xlsx y .csv. |
| HTTP cliente | httpx | 0.27 | Sube archivos al servidor, descarga actualizaciones, reporta errores |
| Seguridad | keyring | 25.0 | Vault de Windows para el token de API |
| Empaquetado | pyinstaller | 6.0 | Genera el .exe distribuible |
| Calendario UI | tkcalendar | 1.6 | Selector de fecha custom en la UI |
| Semver | semver | 3.0 | Comparación de versiones del .exe para auto-update |
| **Servidor actualizaciones** | **Laravel (VPS Hostinger)** | **Existente** | **Endpoints /rpa/: macros, upload de archivos, telemetría, versiones del .exe** |

> **Eliminado de v1.0:** playwright (reemplazado por pyautogui), apscheduler (pospuesto a v1.1).

> **NO usar:** selenium, asyncio/aiohttp (el proyecto es síncrono), xlrd/.xls.

### 3.3 Estructura de carpetas del proyecto

```
rpa_conciliaciones/
│
├── app/                        ← Todo lo que ve el contador
│   ├── main.py                 ← Entry point. Arranca la UI y el health check inicial
│   └── ui/
│       ├── dashboard.py        ← Ventana principal con lista de tareas
│       ├── task_status.py      ← Componente visual de estado por tarea
│       ├── session_panel.py    ← Panel de health check: estado de sesiones
│       ├── date_selector.py    ← Selector de período: día / semana / mes / custom
│       ├── manual_upload.py    ← Carga manual de archivo como fallback
│       ├── alert_modal.py      ← Modal de error con opción manual
│       ├── macro_recorder_panel.py  ← Panel de grabación de macros  ← NUEVO
│       └── macro_list_panel.py      ← Lista de macros guardadas      ← NUEVO
│
├── core/                       ← Motor de ejecución. No tiene UI
│   ├── chrome_launcher.py      ← Lanza Chrome con subprocess a una URL  ← NUEVO (reemplaza browser.py)
│   ├── health_checker.py       ← Verifica sesiones con screenshot + image matching
│   ├── downloader.py           ← Detecta y captura archivos descargados
│   ├── pyauto_executor.py      ← Wrapper de PyAutoGUI (clic, typewrite, screenshot)  ← NUEVO
│   ├── runner.py               ← Orquestador: ejecuta la cola de tareas
│   └── reporter.py             ← Reporta estado, errores y telemetría de negocio
│
├── macros/                     ← Sistema de grabación y reproducción de bots  ← NUEVO
│   ├── __init__.py
│   ├── models.py               ← Dataclasses: Action, Recording, DateStep
│   ├── recorder.py             ← Graba acciones de mouse/teclado a JSON
│   ├── player.py               ← Reproduce una Recording con fechas dinámicas
│   ├── storage.py              ← Guarda/carga macros desde JSON local
│   └── date_step.py            ← Marcador especial de paso de fecha en la macro
│
├── tasks/                      ← Una subcarpeta por plataforma
│   ├── base_task.py            ← Clase abstracta. Usa PyAutoExecutor, sin Page
│   ├── mercadopago/
│   │   ├── task.py
│   │   └── schema.json
│   ├── galicia/
│   │   ├── task.py
│   │   └── schema.json
│   └── [plataforma]/
│
├── date_handlers/              ← Manejan la inyección de fechas con PyAutoGUI
│   ├── base_handler.py         ← Clase abstracta. Recibe executor, no Page
│   ├── input_date.py           ← Tipea la fecha en un campo <input type="date">
│   ├── datepicker_js.py        ← Navega un calendario visual usando image templates
│   ├── no_date_filter.py       ← Sin interacción, guarda fechas en contexto
│   ├── date_resolver.py        ← Calcula date_from/date_to según el modo
│   ├── factory.py
│   └── exceptions.py
│
├── uploader/
│   ├── file_uploader.py
│   └── manual_uploader.py
│
├── sync/
│   ├── api_client.py
│   ├── task_loader.py          ← Ahora también sincroniza macros del servidor
│   ├── updater.py
│   └── macro_sync.py           ← Sube/descarga macros al servidor  ← NUEVO
│
├── config/
│   ├── settings.py
│   └── credentials.py
│
├── build/
│   └── installer.spec
│
├── requirements.txt
└── README.md
```

**Eliminado de la estructura:** `core/browser.py` (reemplazado por `core/chrome_launcher.py`). El health checker ya no usa Playwright.

### 3.4 Interfaces entre módulos (contratos que no se pueden romper)

**ChromeLauncher (core/chrome_launcher.py)** ← REEMPLAZA BrowserManager
```python
class ChromeLauncher:
    def launch(self, url: str) -> None
    # Abre Chrome con subprocess apuntando a la URL dada.
    # Usa el perfil real del usuario (rutas de Windows).
    # Si Chrome no está instalado: lanza ChromeNotFoundError.

    def close(self) -> None
    # Cierra la instancia de Chrome lanzada.

    def take_screenshot(self) -> Path
    # Captura pantalla completa. Retorna Path al archivo PNG temporal.
```

**PyAutoExecutor (core/pyauto_executor.py)** ← NUEVO
```python
class PyAutoExecutor:
    def click(self, x: int, y: int, delay: float = 0.1) -> None
    def double_click(self, x: int, y: int) -> None
    def type_text(self, text: str, interval: float = 0.05) -> None
    def paste_text(self, text: str) -> None   # via pyperclip + ctrl+v
    def press_key(self, *keys: str) -> None   # e.g. 'ctrl', 'a'
    def wait_for_image(self, template: Path, timeout: int = 30,
                       confidence: float = 0.8) -> tuple[int, int]
    # Espera hasta encontrar la imagen en pantalla. Retorna (x, y) del centro.
    # Lanza ImageNotFoundError si supera timeout.

    def find_image(self, template: Path,
                   confidence: float = 0.8) -> tuple[int, int] | None
    # Busca imagen en pantalla. Retorna (x, y) o None si no la encuentra.

    def screenshot(self, region: tuple | None = None) -> Path
    # Toma screenshot (completo o de región). Guarda en temp/, retorna Path.

    def move_to(self, x: int, y: int) -> None
    def scroll(self, clicks: int, x: int | None = None, y: int | None = None) -> None
```

**HealthChecker (core/health_checker.py)**
```python
@dataclass
class SessionStatus:
    task_id: str
    task_name: str
    platform_url: str
    is_logged_in: bool
    checked_at: datetime
    error: str | None = None

class HealthChecker:
    # Ahora usa ChromeLauncher + PyAutoExecutor para verificar sesiones.
    # Navega a session_check_url, toma screenshot,
    # busca session_indicator_image (template PNG) en la captura.
    def check_all(self, task_list: list) -> list[SessionStatus]
```

**DateResolver (date_handlers/date_resolver.py)**
```python
class DateResolver:
    @classmethod
    def resolve(cls, mode: str,
                custom_from: date | None = None,
                custom_to: date | None = None) -> tuple[date, date]
    # Modos: 'yesterday' | 'current_week' | 'last_week'
    #        | 'current_month' | 'last_month' | 'custom'
```

**BaseDateHandler (date_handlers/base_handler.py)**
```python
class BaseDateHandler:
    context: dict   # NoDateFilterHandler guarda fechas acá para el uploader
    def set_dates(self, executor: PyAutoExecutor,
                  date_from: date, date_to: date) -> None
    # Recibe executor (PyAutoGUI), no Page (Playwright)
```

**BaseTask (tasks/base_task.py)**
```python
class BaseTask:
    task_id: str
    task_name: str
    platform_url: str
    date_handler_type: str      # 'input_date' | 'datepicker_js' | 'no_filter'
    date_handler_kwargs: dict
    date_mode: str
    session_check_url: str
    session_indicator_image: str  # Ruta a imagen PNG template para health check
                                  # (reemplaza session_indicator de texto/CSS)

    def navigate(self, executor: PyAutoExecutor) -> None    # abstracto
    def trigger_download(self, executor: PyAutoExecutor) -> None  # abstracto
    def run(self, date_from: date, date_to: date) -> Path   # concreto en BaseTask
```

**Recording y MacroPlayer (macros/)**
```python
@dataclass
class Action:
    type: str           # 'click' | 'double_click' | 'type' | 'key' | 'scroll' | 'wait_image' | 'date_step'
    x: int | None = None
    y: int | None = None
    text: str | None = None
    keys: list[str] | None = None
    image_template: str | None = None   # nombre de imagen en macros/images/
    delay: float = 0.1
    date_field: str | None = None       # 'date_from' | 'date_to' | None (solo para date_step)
    date_format: str | None = None      # '%Y-%m-%d' | '%d/%m/%Y' | etc.

@dataclass
class Recording:
    macro_id: str
    macro_name: str
    platform_url: str
    task_id: str
    actions: list[Action]
    created_at: datetime
    version: str

class MacroPlayer:
    def play(self, recording: Recording, executor: PyAutoExecutor,
             date_from: date, date_to: date) -> None
    # Reproduce la Recording. Cuando encuentra un Action de tipo 'date_step',
    # aplica la fecha según date_field y date_format en lugar del texto grabado.
```

**MacroRecorder (macros/recorder.py)**
```python
class MacroRecorder:
    def start(self, macro_id: str, macro_name: str,
              platform_url: str, task_id: str) -> None
    def stop(self) -> Recording
    def mark_date_step(self, date_field: str, date_format: str) -> None
    # Inserta un marcador DateStep en la grabación actual.
    # El próximo texto que el técnico escriba se reemplazará por la fecha dinámica.
    @property
    def is_recording(self) -> bool
```

**MacroStorage (macros/storage.py)**
```python
class MacroStorage:
    def save(self, recording: Recording) -> Path
    def load(self, macro_id: str) -> Recording | None
    def list_all(self) -> list[Recording]
    def delete(self, macro_id: str) -> None
```

**FileUploader (uploader/file_uploader.py)**
```python
class FileUploader:
    def upload(self, task_id: str, filepath: Path,
               date_from: date, date_to: date,
               no_filter_context: dict | None = None,
               manual: bool = False) -> bool
```

**ApiClient (sync/api_client.py)**
```python
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
```

**MacroSync (sync/macro_sync.py)** ← NUEVO
```python
class MacroSync:
    def fetch_macros(self) -> list[dict]
    # GET /rpa/macros → lista de macros con macro_id, version, hash
    def download_macro(self, macro_id: str) -> Recording
    # GET /rpa/macros/{id} → descarga Recording completo
    def upload_macro(self, recording: Recording) -> bool
    # POST /rpa/macros → publica macro grabada en el servidor
```

**Reporter (core/reporter.py)**
```python
class Reporter:
    def report_success(self, task_id: str, filepath: Path,
                       date_from: date, date_to: date,
                       duration_seconds: float) -> None
    def report_failure(self, task_id: str, error: str,
                       screenshot_path: Path | None = None) -> None
    def report_session_check(self, results: list[SessionStatus]) -> None
```

**TaskRunner (core/runner.py)**
```python
class TaskRunner:
    # PENDING = 'pending' | RUNNING = 'running' | DONE = 'done' | ERROR = 'error'
    def __init__(self,
                 task_list: list[BaseTask],
                 on_status_change: Callable[[str, str, str], None],
                 file_uploader: FileUploader,
                 reporter: Reporter)
    def run_all(self, date_mode: str | None = None,
                custom_from: date | None = None,
                custom_to: date | None = None) -> dict
    # Retorna: {"total": int, "success": int, "failed": int,
    #           "failed_tasks": list[str], "duration_seconds": float,
    #           "total_rows_processed": int}
```

**TaskLoader (sync/task_loader.py)**
```python
class TaskLoader:
    def fetch_and_update(self) -> list[dict]
    # Retorna lista de metadata de tareas activas.
    # También llama MacroSync para sincronizar macros.
```

**UpdaterClient (sync/updater.py)**
```python
class UpdaterClient:
    def check(self) -> dict | None
    def download(self, version_info: dict, dest_folder: Path) -> Path
```

### 3.5 schema.json — Metadata de la tarea (no mapeo de columnas)

**DECISIÓN ARQUITECTÓNICA:** El schema.json no define mapeo de columnas (el ETL del servidor se encarga). Define el comportamiento de la tarea: cómo manejar fechas, qué imagen usa para el health check, si tiene macro asociada.

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
- `date_handler_type`: `'input_date'` | `'datepicker_js'` | `'no_filter'` | `'macro'` (si la tarea usa MacroPlayer)
- `delivery`: `"direct"` (descarga en browser) | `"email"` (activa modal manual)
- `session_indicator_image`: nombre del PNG template en `tasks/{platform}/images/` para health check
- `macro_id`: si no es null, la tarea ejecuta la macro correspondiente en lugar de task.py

### 3.6 Contratos de API — Especificación OpenAPI 3.0 (referencia para backend)

> **Autenticación:** Todos los endpoints requieren `Authorization: Bearer {api_token}`.
> El token se almacena en el vault de Windows via `keyring`. Respuesta `401` = limpiar token y mostrar error.

---

#### `POST /rpa/upload` — Subir archivo Excel descargado

```yaml
Request:
  Content-Type: multipart/form-data
  Body:
    file:          binary   # Archivo .xlsx o .csv tal como se descargó
    task_id:       string   # "mercadopago_movimientos"
    date_from:     string   # ISO 8601: "2025-02-18"
    date_to:       string   # ISO 8601: "2025-02-18"
    machine_id:    string   # hostname del equipo
    manual_upload: boolean  # true si el contador subió manualmente

Responses:
  200: { "status": "ok", "message": "Archivo recibido", "record_id": 1234 }
  401: { "error": "unauthorized", "message": "Token inválido o expirado" }
  422: { "error": "validation_failed", "details": { "task_id": ["required"] } }
  500: { "error": "server_error", "message": "Error interno al procesar el archivo" }
```

#### `GET /rpa/tasks` — Lista de tareas activas

```yaml
Request: (sin body)

Response 200:
  {
    "tasks": [
      {
        "task_id":    "mercadopago_movimientos",
        "hash":       "abc123def",
        "schema_url": "/rpa/tasks/mercadopago_movimientos/schema",
        "script_url": "/rpa/tasks/mercadopago_movimientos/script"
      }
    ]
  }
# El cliente compara el hash local vs el del servidor para detectar cambios.
# Si el hash difiere: descargar el schema/script actualizado.
```

#### `GET /rpa/macros` — Lista de macros disponibles ← NUEVO

```yaml
Response 200:
  {
    "macros": [
      {
        "macro_id":   "macro_mp_001",
        "macro_name": "Mercado Pago — Movimientos",
        "task_id":    "mercadopago_movimientos",
        "version":    "1.0",
        "hash":       "def456abc",
        "created_at": "2025-02-18T10:00:00Z"
      }
    ]
  }
```

#### `GET /rpa/macros/{macro_id}` — Descargar Recording completa ← NUEVO

```yaml
Response 200: Recording JSON completo (schema: ver macros/models.py sección 3.4)
Response 404: { "error": "not_found", "macro_id": "macro_mp_001" }
```

#### `POST /rpa/macros` — Publicar macro grabada ← NUEVO

```yaml
Request:
  Content-Type: application/json
  Body: Recording completo (schema: ver macros/models.py sección 3.4)

Responses:
  200: { "status": "ok", "macro_id": "macro_mp_001", "version": "1.0" }
  409: { "error": "conflict", "message": "Ya existe una macro con ese macro_id y versión" }
  422: { "error": "validation_failed", "details": { "actions": ["No puede estar vacío"] } }
```

#### `POST /rpa/failure` — Reportar fallo de bot

```yaml
Request:
  Content-Type: multipart/form-data
  Body:
    task_id:    string           # "mercadopago_movimientos"
    error:      string           # Mensaje de error completo (stack trace técnico)
    screenshot: binary (opt.)   # PNG del escritorio al momento del fallo

Response 200: { "status": "ok" }
# El cliente absorbe errores de este endpoint (logger.warning, no propagar)
```

#### `POST /rpa/telemetry` — Reportar telemetría de tarea exitosa

```yaml
Request:
  Content-Type: application/json
  Body:
    {
      "task_id":          "mercadopago_movimientos",
      "date_from":        "2025-02-18",
      "date_to":          "2025-02-18",
      "row_count":        47,
      "file_size_kb":     23.4,
      "duration_seconds": 35.2,
      "machine_id":       "WORKSTATION-01",
      "timestamp":        "2025-02-19T08:15:00Z"
    }

Response 200: { "status": "ok" }
# El cliente absorbe errores de este endpoint (logger.warning, no propagar)
```

#### `POST /rpa/session_check` — Reportar resultados del health check

```yaml
Request:
  Content-Type: application/json
  Body:
    {
      "results": [
        {
          "task_id":     "mercadopago_movimientos",
          "task_name":   "Mercado Pago — Movimientos",
          "is_logged_in": true,
          "checked_at":  "2025-02-19T08:00:00Z",
          "error":       null
        }
      ]
    }

Response 200: { "status": "ok" }
```

#### `GET /rpa/version` — Verificar nueva versión del .exe

```yaml
Response 200 (hay actualización):
  {
    "version":      "1.1.0",
    "download_url": "/rpa/download/1.1.0",
    "release_notes": "MacroPlayer mejorado. Soporte multi-monitor."
  }
Response 204: (sin body) → No hay actualización disponible
```

#### Política de reintentos y manejo de errores HTTP

| Código | Condición | Acción del cliente |
|---|---|---|
| `401` | Token inválido | Limpiar token de keyring. Mostrar error de autenticación al contador. |
| `404` | Recurso no encontrado | Para tasks/macros: usar cache local. Para upload: marcar tarea como error. |
| `422` | Validación fallida | Propagar detalle al log. No reintentar automáticamente. |
| `500` | Error del servidor | Reintentar 1 vez después de 5 segundos, luego reportar como error de tarea. |
| Timeout | Servidor no responde | Para tasks/macros: usar cache local. Para upload: marcar como pendiente de reintento manual. |

---

## 4. SUPUESTOS, RIESGOS Y CUELLOS DE BOTELLA

### 4.1 Supuestos del sistema

- **Chrome es obligatorio por política interna.** No hay soporte para Edge o Firefox en v1.0.
- **Sesiones activas al momento de ejecutar.** No hay scheduler desatendido. El Health Check confirma el estado.
- **Exportación en .xlsx o .csv exclusivamente.** Sin .xls.
- **La app corre en el equipo del contador, no en un servidor.** PyAutoGUI requiere una pantalla real.
- **El equipo del contador tiene resolución ≥ 1280×720.** Las image templates se generan en 100% DPI. Si el sistema usa escalado de pantalla (125%, 150%), la app advierte al técnico durante la grabación.
- **ETL completamente en el servidor.** La app sube el archivo sin transformarlo.
- **Windows como sistema operativo.** Paths de Chrome y empaquetado son específicos de Windows.

### 4.2 Riesgos ordenados por probabilidad e impacto

**RIESGO 1 — Cambio de UI en plataforma externa (Probabilidad: Alta | Impacto: Alto)**

Este es el riesgo principal de cualquier sistema RPA. Cuando Mercado Pago actualiza su portal y mueve un botón, el bot falla.

Mitigación:
- Con macros + image templates: el técnico re-graba el bot en 10-15 minutos.
- Timeout estricto de 60 segundos por tarea. Fallo visible, nunca silencioso.
- reporter.py envía screenshot del estado del escritorio al momento del fallo.
- MacroSync permite redistribuir la macro corregida sin actualizar el .exe.

**RIESGO 2 — Resolución de pantalla y DPI Scaling (Probabilidad: Alta | Impacto: Medio)**  ← NUEVO

PyAutoGUI trabaja con coordenadas de píxeles. Si la macro fue grabada en un equipo con 100% DPI y se ejecuta en uno con 125%, las coordenadas absolutas quedan desplazadas.

Mitigación:
- Usar `pyautogui.locateOnScreen(template, confidence=0.8)` (detección por imagen) en lugar de coordenadas absolutas para elementos clave.
- Las coordenadas absolutas solo para acciones dentro de una región ya localizada.
- config/settings.py almacena el DPI del sistema al grabar. Si difiere al reproducir, la app advierte.
- La UI de grabación avisa al técnico: "Grabás en DPI 100%. Asegurate de que los contadores también usen DPI 100%."

**RIESGO 3 — Pérdida de foco de ventana (Probabilidad: Alta | Impacto: Alto)**  ← NUEVO

PyAutoGUI envía clicks y teclas a la posición actual del cursor. Si durante la ejecución otra ventana toma el foco (notificación, alerta, Teams, etc.), el bot escribe/hace clic en el lugar equivocado.

Mitigación:
- `PyAutoExecutor.focus_window()` usa `pygetwindow` para activar Chrome antes de acciones críticas.
- Implementación concreta (incluida en Feature 2):
  ```python
  import pygetwindow as gw
  def focus_window(self, title: str = "Chrome") -> bool:
      windows = gw.getWindowsWithTitle(title)
      if not windows:
          return False
      windows[0].activate()
      time.sleep(0.3)  # El OS necesita tiempo para procesar el activate
      return True
  # Llamar antes de cada click y paste_text en MacroPlayer y DateHandlers
  ```
- Si `focus_window()` retorna False: lanzar `ChromeNotFoundError` (Chrome fue cerrado por el usuario).
- La UI del contador muestra overlay bloqueante: "Bot en ejecución — no uses el mouse ni el teclado."
- Agregar `pygetwindow>=0.0.9` a `requirements.txt`.

**RIESGO 4 — Timing y esperas (Probabilidad: Alta | Impacto: Medio)**  ← NUEVO

A diferencia de Playwright (que puede esperar a que el DOM cargue), PyAutoGUI no tiene API para esperar eventos de la página. Una espera muy corta causa que el bot haga clic antes de que el elemento aparezca.

Mitigación:
- PyAutoExecutor usa `wait_for_image()` con polling de image templates en lugar de `time.sleep()` fijo.
- Cada action tiene un `delay` configurable por el técnico al grabar.
- El técnico puede insertar "wait_image" steps que bloquean hasta que aparezca un elemento visual en pantalla.

**RIESGO 5 — Sesión expirada al momento de ejecutar (Probabilidad: Alta en banca argentina | Impacto: Medio)**

Igual que en v1.2. Health Check verifica antes de ejecutar.

Mitigación: igual que v1.2. El botón "Ejecutar todo" se activa solo cuando las sesiones están verificadas.

**RIESGO 6 — 2FA obligatorio en bancos (Probabilidad: Alta para algunos bancos | Impacto: Crítico)**

Igual que en v1.2. Mapear antes de iniciar Feature 5.

| Plataforma | ¿Requiere 2FA en cada login? | ¿La sesión puede durar días? | Estado |
|---|---|---|---|
| Banco Galicia | A confirmar | A confirmar | Pendiente |
| Mercado Pago | A confirmar | A confirmar | Pendiente |

**RIESGO 7 — Plataforma que genera el archivo por email (Probabilidad: Baja | Impacto: Bajo)**

Igual que v1.2. `"delivery": "email"` en schema.json activa el flujo de carga manual.

**RIESGO 8 — El contador interactúa con el equipo mientras el bot corre (Probabilidad: Alta | Impacto: Medio)**

Si el contador mueve el mouse o escribe mientras el bot está corriendo, interfiere directamente con PyAutoGUI.

Mitigación:
- UI del contador muestra modal bloqueante: "Bot en ejecución. No uses el mouse ni el teclado."
- El runner puede pausarse si detecta input del usuario (pynput listener que activa pausa de 2 segundos).
- Botón de "Pausar" visible en la UI que detiene el bot de forma controlada.

---

## 5. REQUISITOS Y USER STORIES

### ÉPICA 1: Panel del Contador

**UC-01: Ver lista de tareas del día**

Como contador, quiero ver al abrir la app la lista de tareas de descarga del día, para saber qué plataformas se van a procesar.

Criterios de aceptación:
- La app muestra las tareas asignadas al perfil del usuario autenticado
- Cada tarea muestra: ícono de la plataforma, nombre, y estado inicial "Pendiente"
- La lista se sincroniza con el servidor cada vez que se abre la app (task_loader.py)
- Si el servidor no está disponible, la app usa las tareas de la última sincronización exitosa

---

**UC-02: Ejecutar todas las tareas con un clic**

Como contador, quiero presionar un botón "Ejecutar todo" para que todos los bots corran en secuencia sin que yo tenga que intervenir.

Contexto actualizado v1.3: El botón lanza TaskRunner en un thread separado. Las tareas corren en secuencia. **El bot controla visualmente el escritorio (PyAutoGUI): el contador no debe mover el mouse ni escribir durante la ejecución.** Un overlay semitransparente sobre la UI lo recuerda durante la ejecución.

Criterios de aceptación:
- El botón "Ejecutar todo" es el elemento más prominente de la UI
- Al presionarlo: el botón se desactiva y aparece un overlay "Bot en ejecución — no toques el mouse ni el teclado"
- Las tareas corren una por una en el orden definido en el servidor
- Al terminar todas las tareas el overlay desaparece y el botón vuelve a activarse

---

**UC-03: Ver estado de cada tarea en tiempo real**

Como contador, quiero ver el progreso de cada tarea mientras se ejecuta.

Criterios de aceptación:
- Estados posibles: Pendiente (reloj), En progreso (spinner), Completado (check verde), Falló (X roja)
- Cada cambio de estado es visible en la UI en menos de 2 segundos
- Al completar todas las tareas aparece un resumen: "X de Y tareas completadas"
- El tiempo de ejecución de cada tarea se muestra junto a su estado final

---

**UC-04: Recibir alerta y continuar manualmente si falla una tarea**

Como contador, quiero que si una tarea falla, la app me avise claramente y me dé la opción de completar ese paso manualmente.

Criterios de aceptación:
- Modal de alerta con nombre de la plataforma y descripción del error en lenguaje simple
- Botón "Completar manualmente" que abre Chrome en la URL de la plataforma
- El fallo de una tarea NO interrumpe las siguientes
- El error se reporta automáticamente al servidor con screenshot del escritorio

---

**UC-05: Scheduler automático — POSPUESTO A v1.1**

> Las sesiones de banca argentina expiran en 15-30 min. Un bot desatendido fallaría. En v1.1 se integra con health check y notificación al contador para refresh previo.

---

**UC-05b: Seleccionar el período de fecha antes de ejecutar**

Como contador, quiero poder seleccionar el período de fecha antes de presionar "Ejecutar todo".

Criterios de aceptación:
- Botones de selección rápida: "Ayer", "Esta semana", "Semana pasada", "Este mes", "Mes anterior", "Personalizado"
- Si selecciona "Personalizado": aparecen dos campos de fecha
- El modo seleccionado aplica a todas las tareas que lo soporten
- Las tareas que no soporten el modo usan su date_mode por defecto y muestran un aviso

---

**UC-14: Health Check de sesiones antes de ejecutar**

Como contador, quiero ver antes de ejecutar qué plataformas tienen sesión activa y cuáles necesitan que me loguee manualmente.

Contexto actualizado v1.3: El Health Checker usa **ChromeLauncher + PyAutoExecutor** en lugar de Playwright. Abre Chrome en la session_check_url, toma un screenshot y busca la imagen template `session_indicator_image` en la captura usando `pillow`. Si encuentra la imagen, la sesión está activa.

Criterios de aceptación:
- Al abrir la app (o al presionar "Verificar sesiones"), el sistema corre el health check en background
- El panel muestra: ✅ Sesión activa / ⚠️ Sesión expirada / ❓ No verificable
- Si hay sesiones expiradas, el botón "Ejecutar todo" muestra un warning pero no se bloquea
- Botón "Abrir [plataforma]" junto a cada sesión expirada
- Los resultados se reportan al servidor para tracking histórico

---

### ÉPICA 2: Motor de Ejecución

**UC-06: Ejecutar bot sobre sesión real de Chrome**

Como sistema, necesito controlar el Chrome real del usuario con PyAutoGUI para que las sesiones bancarias sean accesibles.

Contexto técnico actualizado v1.3: **ChromeLauncher** abre Chrome con subprocess usando `--profile-directory=Default` apuntando al perfil real. Chrome se abre en la URL de la plataforma. PyAutoExecutor controla el mouse y teclado sobre esa ventana.

Criterios de aceptación:
- chrome_launcher.py abre Chrome con el perfil real del usuario (sin crear perfil nuevo)
- La ventana de Chrome se pone en foco antes de cada acción de PyAutoGUI
- Si Chrome no está instalado, la app muestra un error con instrucciones claras
- El bot abre Chrome en una nueva ventana sin cerrar las pestañas existentes del usuario

---

**UC-07: Manejar los tres tipos de inyección de fecha**

Como sistema, necesito resolver el problema de ingreso de fechas para cada plataforma usando PyAutoGUI.

Contexto técnico actualizado v1.3: Los tres tipos de handler ahora usan PyAutoExecutor, no Playwright Page.

1. `input_date`: el campo de fecha es un `<input type="date">`. El handler hace clic sobre el campo y usa `paste_text()` para pegar la fecha (más fiable que typewrite en Chrome).
2. `datepicker_js`: el handler usa `wait_for_image(template_abierto)` para esperar que el calendario aparezca, luego navega con `find_image()` para localizar flechas de navegación.
3. `no_filter`: sin interacción. Guarda fechas en contexto para filtro pandas posterior.

Criterios de aceptación:
- factory.py retorna la instancia del handler correcto basándose en `date_handler_type`
- InputDateHandler usa `paste_text()` con formato YYYY-MM-DD en el campo detectado
- DatepickerJSHandler usa image templates para navegar el calendario
- NoDateFilterHandler guarda fechas en contexto sin tocar la pantalla

---

**UC-08: Detectar y capturar el archivo descargado**

Como sistema, necesito detectar cuándo el archivo fue descargado y obtener su path.

Igual que v1.2. downloader.py monitorea la carpeta Downloads con polling. Sin cambios de contrato.

---

**UC-09: Subir el archivo Excel al servidor sin transformación**

Como sistema, necesito enviar el archivo descargado tal como está al servidor Laravel.

Igual que v1.2. La única excepción es `no_filter`: filtrar filas por fecha con pandas antes de subir.

---

### ÉPICA 3: Gestión de Tareas por Técnicos

**UC-10: Publicar una tarea en el servidor**

Como técnico, quiero crear el task.py + schema.json para una plataforma nueva y publicarlos.

Igual que v1.2, pero ahora el técnico puede opcionalmente asociar una macro (`macro_id` en schema.json) en lugar de implementar `navigate()` y `trigger_download()` en código.

---

**UC-11: Actualizar una macro y el .exe desde el servidor**

Como técnico, quiero poder actualizar la lógica de un bot desde el servidor.

Ahora incluye la sincronización de macros. MacroSync verifica hash de cada macro y descarga solo lo que cambió.

---

**UC-12: Recibir alerta cuando un bot falla en producción**

Como técnico, quiero recibir una notificación automática cuando un bot falla.

Ahora el reporte incluye screenshot del **escritorio completo** al momento del fallo (no solo la página web).

---

**UC-13: Cargar un archivo manualmente**

Como contador, quiero poder cargar el archivo manualmente cuando el bot falló o cuando la plataforma envía por email.

Igual que v1.2.

---

**UC-15: Grabar una macro para una plataforma nueva (NUEVO)**

Como técnico, quiero grabar las acciones que realizo en Chrome para una plataforma nueva, para publicarlas como bot sin escribir código.

Contexto: El técnico abre el Macro Recorder Panel en la app, ingresa el nombre y la URL de la plataforma, presiona "Iniciar grabación" y realiza las acciones en Chrome normalmente. El recorder captura cada clic y tecla. Cuando llega al campo de fecha, el técnico presiona "Marcar fecha inicio" o "Marcar fecha fin" para que ese paso sea dinámico. Al terminar presiona "Detener y guardar".

Criterios de aceptación:
- El panel de grabación tiene botones: "Iniciar grabación", "Marcar fecha inicio", "Marcar fecha fin", "Detener y guardar"
- Durante la grabación, un indicador rojo visible muestra que está grabando
- El técnico puede insertar pasos `wait_for_image` manualmente durante la grabación
- Al guardar, la macro se persiste en JSON local y se puede publicar al servidor
- La UI muestra la lista de acciones grabadas para revisión antes de guardar
- Los pasos de fecha muestran `[FECHA_INICIO formato: dd/mm/yyyy]` en lugar de la fecha concreta

---

**UC-16: Reproducir macro grabada con fechas dinámicas (NUEVO)**

Como sistema, necesito reproducir una macro grabada sustituyendo los pasos de fecha con las fechas reales calculadas por DateResolver.

Contexto: MacroPlayer recorre la lista de acciones. Cuando encuentra un Action de tipo `date_step`, no reproduce el texto grabado sino que calcula la fecha con `DateResolver.resolve()` y la formatea según `date_format` del step, luego la pega con `paste_text()`.

Criterios de aceptación:
- Los DateStep se reemplazan por la fecha correcta calculada por DateResolver
- El formato de fecha se respeta exactamente (`%Y-%m-%d`, `%d/%m/%Y`, etc.)
- Los pasos `wait_for_image` bloquean la reproducción hasta encontrar la imagen o hacer timeout
- Si un `wait_for_image` excede el timeout: lanzar `PlaybackError` con descripción del paso fallido
- La velocidad de reproducción es configurable por macro (delay entre acciones)
- El `PlaybackError` incluye screenshot del escritorio al momento del fallo

---

## 6. MÉTRICAS DE ÉXITO

| KPI | Baseline | Meta v1.0 | Cómo se mide |
|---|---|---|---|
| Tiempo diario en descarga manual por contador | ~2 horas | < 5 minutos | Logs de ejecución en servidor |
| Tasa de éxito de tareas automáticas | No aplica | > 90% por semana | reporter.py registra éxitos y fallos |
| Tiempo entre fallo del bot y detección | Días o nunca | < 2 horas | Alertas vía /rpa/failure |
| Tiempo de corrección de bot roto | Semanas | < 30 minutos (re-grabar macro) | Registro de actualizaciones en servidor |
| Tiempo de grabación de nuevo bot | Horas (codegen + debug) | < 15 minutos | Medición manual en piloto |
| Volumen de transacciones procesadas | 0 (manual) | Medir desde día 1 | reporter.py envía row_count por tarea |
| Tasa de sesiones expiradas en health check | No medible | < 20% al final del mes | /rpa/session_check |

---

## 7. GUÍA DE DESARROLLO CON CLAUDE CODE

### 7.1 Cómo usar esta sección

Cada feature tiene contexto, archivos que produce y un prompt exacto a ejecutar.

**Orden de dependencias:**
```
Feature 1  (estructura base)
  → Feature 2  (core/chrome_launcher.py + core/pyauto_executor.py)
  → Feature 3  (date_handlers/ con PyAutoExecutor)
  → Feature 4  (core/downloader.py)
  → Feature 4b (core/health_checker.py con image templates)
  → Feature 5  (tasks/ con PyAutoGUI flow)
  → Feature 6  (uploader/)
  → Feature 7  (core/runner.py + core/reporter.py)
  → Feature 8  (sync/ con MacroSync)
  → Feature 9  (app/ui/ con macro panels)
  → Feature 10 (build/ — empaquetado .exe)
  → Feature 11 (macros/ — recorder, player, storage, models)
  → Feature 12 (integración macro en runner + UI panels)
```

---

### FEATURE 1 — Estructura base del proyecto

**User Stories:** Base para todas.

**Qué produce:**
- Árbol de carpetas completo según sección 3.3
- `__init__.py` en cada carpeta
- `requirements.txt` con todas las dependencias
- `README.md` con instrucciones de instalación

**PROMPT A EJECUTAR:**

```
Crea la estructura completa del proyecto Python para el sistema RPA de automatización contable.

Nombre del proyecto: rpa_conciliaciones

Carpetas a crear (todas con __init__.py vacío):
- app/
- app/ui/
- core/
- macros/
- tasks/
- tasks/mercadopago/
- tasks/mercadopago/images/
- tasks/galicia/
- tasks/galicia/images/
- date_handlers/
- uploader/
- sync/
- config/
- build/

Archivos a crear:

1. requirements.txt con estas dependencias exactas:
customtkinter>=5.2
pyautogui>=0.9.54
pillow>=10.0
pynput>=1.7
pyperclip>=1.8
pygetwindow>=0.0.9
pandas>=2.0
openpyxl>=3.1
httpx>=0.27
keyring>=25.0
pyinstaller>=6.0
python-dateutil>=2.9
semver>=3.0
tkcalendar>=1.6

NO incluir: playwright, apscheduler, selenium, xlrd.

2. README.md con secciones:
- Descripción: "App de escritorio Windows para automatización de descarga de reportes financieros y envío al servidor de conciliación"
- Requisitos: Python 3.11+, Google Chrome instalado (obligatorio)
- Decisiones de arquitectura: (1) Chrome es obligatorio. (2) Motor de automatización: PyAutoGUI (visual, no DevTools). (3) El ETL es del servidor, no de la app. (4) No hay scheduler en v1.0. (5) Macros grabadas = bots sin código.
- Instalación: pip install -r requirements.txt
- Cómo correr en desarrollo: python app/main.py
- Estructura del proyecto: lista de carpetas con rol de cada una

3. app/main.py: esqueleto básico con customtkinter, ventana "RPA Conciliaciones" 900x650, mainloop(). Comentario TODO para integrar dashboard.py.

4. config/settings.py con:
SERVER_URL = "https://tudominio.hostinger.com"
APP_VERSION = "1.0.0"
CHROME_PROFILE_PATH = ""           # Detectado automáticamente en chrome_launcher.py
DOWNLOAD_TIMEOUT_SECONDS = 60
HEALTH_CHECK_TIMEOUT_SECONDS = 10
PYAUTOGUI_CONFIDENCE = 0.8         # Confianza mínima para image matching
PYAUTOGUI_PAUSE = 0.1              # pyautogui.PAUSE global entre acciones
USE_MOCK = True                    # False cuando el backend esté listo
HTTP_TIMEOUT_SECONDS = 30
TASK_CACHE_DIR = ""                # Calculado en runtime: AppData/Local/rpa_conciliaciones
LOG_LEVEL = "INFO"

Al terminar, listar el árbol de carpetas para confirmar que todos los archivos existen.
```

---

### FEATURE 2 — core/chrome_launcher.py + core/pyauto_executor.py

**User Stories:** UC-06

**Qué produce:**
- `core/chrome_launcher.py` con `ChromeLauncher`
- `core/pyauto_executor.py` con `PyAutoExecutor`
- `core/exceptions.py` con excepciones custom del módulo

**Contexto adicional:**
ChromeLauncher usa `subprocess.Popen` para abrir Chrome con el perfil real del usuario. A diferencia del antiguo BrowserManager (que usaba Playwright), solo lanza el proceso — no controla la navegación. PyAutoExecutor es el wrapper sobre `pyautogui` que todas las otras clases usan. Centralizar las llamadas a pyautogui en un único executor permite hacer mocking en tests y ajustar delays globalmente.

**PROMPT A EJECUTAR:**

```
Crea los módulos core/chrome_launcher.py y core/pyauto_executor.py.

1. core/chrome_launcher.py — Clase ChromeLauncher

Constructor: __init__(self)

Método: launch(self, url: str) -> None
- Detectar el path del ejecutable de Chrome en Windows:
  Intentar en orden:
  a. os.path.expanduser("~") + "/AppData/Local/Google/Chrome/Application/chrome.exe"
  b. "C:/Program Files/Google/Chrome/Application/chrome.exe"
  c. "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"
- Si ninguno existe: lanzar ChromeNotFoundError con mensaje:
  "No se encontró Google Chrome. Instalá Chrome desde https://www.google.com/chrome/"
- Construir la ruta del perfil del usuario:
  profile_dir = os.path.expanduser("~") + "/AppData/Local/Google/Chrome/User Data"
- Abrir Chrome con subprocess.Popen:
  [chrome_path, url,
   "--profile-directory=Default",
   f"--user-data-dir={profile_dir}",
   "--new-window",
   "--disable-popup-blocking"]
- Guardar el proceso en self._process
- Esperar 2 segundos para que Chrome abra (time.sleep(2))
- Log: "Chrome abierto en {url}"

Método: close(self) -> None
- Si self._process existe y está corriendo: self._process.terminate()
- Log: "Chrome cerrado"

Método: take_screenshot(self) -> Path
- Tomar screenshot con pyautogui.screenshot()
- Guardar en carpeta temp/ del proyecto con nombre screenshot_{timestamp}.png
- Crear la carpeta temp/ si no existe
- Retornar Path del archivo

2. core/pyauto_executor.py — Clase PyAutoExecutor

Importar pyautogui, pyperclip, pillow (PIL.Image), config/settings.py.
Al instanciar: pyautogui.PAUSE = settings.PYAUTOGUI_PAUSE
              pyautogui.FAILSAFE = True   # Mover mouse a esquina superior izquierda aborta el bot

Métodos a implementar:

click(self, x: int, y: int, delay: float = 0.1) -> None
double_click(self, x: int, y: int) -> None
right_click(self, x: int, y: int) -> None
type_text(self, text: str, interval: float = 0.05) -> None
  - Usar pyautogui.typewrite(text, interval=interval)
  - Solo para texto ASCII simple. Para texto con caracteres especiales usar paste_text.
paste_text(self, text: str) -> None
  - pyperclip.copy(text); pyautogui.hotkey('ctrl', 'v')
press_key(self, *keys: str) -> None
  - pyautogui.hotkey(*keys)
move_to(self, x: int, y: int) -> None
scroll(self, clicks: int, x: int | None = None, y: int | None = None) -> None

focus_window(self, title: str = "Chrome") -> bool
  # Usa pygetwindow.getWindowsWithTitle(title) para activar Chrome.
  # time.sleep(0.3) después del activate — el OS necesita tiempo para procesar el cambio.
  # Retorna True si tuvo éxito, False si no hay ventana con ese título.
  # Si retorna False cuando se espera True: lanzar ChromeNotFoundError.
  # import pygetwindow as gw  (se agrega a requirements.txt en este Feature)
  # LLAMAR antes de click() y paste_text() en MacroPlayer y en cada DateHandler.

wait_for_image(self, template: Path, timeout: int = 30,
               confidence: float | None = None) -> tuple[int, int]
- confidence default: settings.PYAUTOGUI_CONFIDENCE
- Polling cada 0.5s buscando la imagen en pantalla
- Si la encuentra: retornar (x, y) del centro del match
- Si supera timeout: lanzar ImageNotFoundError(f"No se encontró {template.name} en {timeout}s")

find_image(self, template: Path,
           confidence: float | None = None) -> tuple[int, int] | None
- Intentar una sola vez. Retornar (x, y) o None.

screenshot(self, region: tuple | None = None) -> Path
- Tomar screenshot con pyautogui.screenshot(region=region)
- Guardar en temp/ con nombre screenshot_{timestamp}.png
- Retornar Path

3. core/exceptions.py con:
- ChromeNotFoundError
- ImageNotFoundError
- DownloadTimeoutError

4. Agregar a requirements.txt: `pygetwindow>=0.0.9`

5. Bloque if __name__ == "__main__" en chrome_launcher.py:
- Abrir Chrome en google.com, esperar 3 segundos, cerrar.

6. Docstrings completos en ambas clases explicando por qué existen y sus limitaciones (DPI, foco de ventana, FAILSAFE).
```

---

### FEATURE 3 — date_handlers/ — Inyección de fechas con PyAutoGUI

**User Stories:** UC-07, UC-05b

**Qué produce:**
- `date_handlers/date_resolver.py` (sin cambios de contrato)
- `date_handlers/base_handler.py` (recibe executor, no Page)
- `date_handlers/input_date.py` (InputDateHandler con PyAutoExecutor)
- `date_handlers/datepicker_js.py` (DatepickerJSHandler con image templates)
- `date_handlers/no_date_filter.py` (sin cambios de lógica)
- `date_handlers/factory.py`
- `date_handlers/exceptions.py`

**Contexto adicional:**
El cambio clave vs v1.2: los handlers reciben `executor: PyAutoExecutor` en lugar de `page: Page`. InputDateHandler ya no usa `page.fill()` sino que hace clic sobre el campo (localizado por image template) y pega la fecha con `executor.paste_text()`. DatepickerJSHandler ya no usa `page.get_by_text()` sino `executor.wait_for_image(arrow_template)` para encontrar las flechas de navegación del calendario.

**PROMPT A EJECUTAR:**

```
Crea el módulo completo de date_handlers/ adaptado a PyAutoExecutor.

1. date_handlers/date_resolver.py — sin cambios de contrato respecto a v1.2

@classmethod
def resolve(cls, mode: str, custom_from: date = None, custom_to: date = None) -> tuple[date, date]
Modos: 'yesterday', 'current_week', 'last_week', 'current_month', 'last_month', 'custom'
Si mode no existe: UnknownDateModeError con lista de modos válidos.
Docstring explicando por qué existe separado de los handlers.

2. date_handlers/base_handler.py — Clase abstracta BaseDateHandler

Atributo de instancia: self.context = {}
Método abstracto:
  set_dates(self, executor: PyAutoExecutor, date_from: date, date_to: date) -> None
  # executor: PyAutoExecutor — NO Page (Playwright fue removido)

3. date_handlers/input_date.py — InputDateHandler(BaseDateHandler)

Constructor: __init__(self, field_template_from: Path, field_template_to: Path)
  # Recibe los path a los PNG templates del campo de fecha inicio y fin

set_dates(self, executor: PyAutoExecutor, date_from: date, date_to: date) -> None
  a. Usar executor.wait_for_image(field_template_from, timeout=10) → (x, y)
  b. executor.triple_click(x, y) para seleccionar todo el texto del campo
  c. executor.paste_text(date_from.strftime('%Y-%m-%d'))
  d. Repetir para field_template_to con date_to
  Si no encuentra el campo: DateSelectorNotFoundError

Agregar método triple_click(self, x, y) a PyAutoExecutor:
  - pyautogui.click(x, y, clicks=3)

4. date_handlers/datepicker_js.py — DatepickerJSHandler(BaseDateHandler)

Constructor: __init__(self, open_template: Path, prev_arrow_template: Path,
                       next_arrow_template: Path, images_dir: Path)
  # open_template: botón que abre el calendario
  # prev_arrow_template / next_arrow_template: flechas de navegación por mes
  # images_dir: carpeta donde están los templates de los días (generados al grabar)

set_dates(self, executor: PyAutoExecutor, date_from: date, date_to: date) -> None
  a. executor.wait_for_image(open_template, timeout=15) → click en el botón
  b. _navigate_to_month(executor, date_from)
  c. _click_day(executor, date_from.day)
  d. _navigate_to_month(executor, date_to)
  e. _click_day(executor, date_to.day)
  Si no puede navegar: DatepickerNavigationError

_navigate_to_month(executor, target_date):
  - Buscar imagen del mes/año actual en pantalla
  - Comparar con target_date
  - Hacer clic en next_arrow o prev_arrow hasta llegar al mes correcto
  - Máximo 24 clicks (dos años de navegación), si supera: DatepickerNavigationError

_click_day(executor, day: int):
  - Los días del mes son texto numérico en el calendario
  - Buscar template del número (día) en la región del calendario
  - Si no se puede localizar: DatepickerNavigationError

5. date_handlers/no_date_filter.py — NoDateFilterHandler(BaseDateHandler)

set_dates(self, executor: PyAutoExecutor, date_from: date, date_to: date) -> None
  - No hace nada en pantalla
  - Guardar en self.context: {'date_from': date_from, 'date_to': date_to}

6. date_handlers/factory.py
get_handler(handler_type: str, **kwargs) -> BaseDateHandler
Map: 'input_date' → InputDateHandler, 'datepicker_js' → DatepickerJSHandler,
     'no_filter' → NoDateFilterHandler, 'macro' → None (manejado por MacroPlayer)
Si no existe: UnknownDateHandlerError

7. date_handlers/exceptions.py:
DateSelectorNotFoundError, DatepickerNavigationError, UnknownDateHandlerError, UnknownDateModeError

Docstrings completos en todos los handlers.
```

---

### FEATURE 4 — core/downloader.py — Captura del archivo descargado

**User Stories:** UC-08

**Qué produce:**
- `core/downloader.py` con `DownloadWatcher`

**Contexto adicional:**
Sin cambios de lógica respecto a v1.2. Chrome sigue descargando a la carpeta Downloads del usuario. El contrato de la clase es idéntico.

**PROMPT A EJECUTAR:**

```
Crea core/downloader.py con la clase DownloadWatcher.

1. Constructor: __init__(self, timeout_seconds: int = None)
   - Si None: usar DOWNLOAD_TIMEOUT_SECONDS de config/settings.py

2. Método wait_for_download(self, extensions: list = None) -> Path
   - extensions default: ['.xlsx', '.csv']  (sin .xls)
   - Detectar Downloads: Path.home() / "Downloads"
   - Snapshot de archivos existentes ANTES de llamar este método
   - Polling cada 500ms buscando archivos nuevos:
     a. No en existing_files
     b. Extensión válida (no .crdownload)
     c. Tamaño > 0 bytes
     d. No modificado en los últimos 500ms
   - Si supera timeout: DownloadTimeoutError con mensaje:
     "El archivo no se descargó en {timeout} segundos. La plataforma puede haber enviado el archivo por email o el botón de descarga no funcionó."

3. Método cleanup(self, filepath: Path, dest_folder: Path = None) -> Path
   - Mover a dest_folder (default: rpa_conciliaciones/temp/)
   - Crear temp/ si no existe
   - Retornar nuevo Path

4. Logging completo (INFO al detectar, ERROR en timeout).
```

---

### FEATURE 4b — core/health_checker.py — Pre-flight Check con image templates

**User Stories:** UC-14

**Qué produce:**
- `core/health_checker.py` con `HealthChecker` y `SessionStatus`

**Contexto adicional:**
El Health Checker v1.3 no usa Playwright. Usa ChromeLauncher para abrir Chrome en la `session_check_url`, espera 2 segundos para que cargue, toma un screenshot con PyAutoExecutor y busca el `session_indicator_image` (un PNG template que el técnico genera al grabar) usando PIL. Si la imagen aparece en el screenshot, la sesión está activa.

**PROMPT A EJECUTAR:**

```
Crea core/health_checker.py con las siguientes clases:

1. Dataclass SessionStatus (sin cambios de interfaz respecto a v1.2):
@dataclass
class SessionStatus:
    task_id: str
    task_name: str
    platform_url: str
    is_logged_in: bool
    checked_at: datetime
    error: str | None = None

2. Clase HealthChecker

Constructor: __init__(self, chrome_launcher: ChromeLauncher,
                           executor: PyAutoExecutor)

check_all(self, task_list: list) -> list[SessionStatus]
- Para cada tarea con session_check_url definido (no None ni ""):
  a. Thread: _check_one(task)
- Lanzar todos los threads simultáneamente
- join(timeout=15) por thread
- Retornar lista de SessionStatus

_check_one(self, task) -> SessionStatus
- chrome_launcher.launch(task.session_check_url)
- time.sleep(2)  # Esperar a que la página cargue
- screenshot_path = executor.screenshot()
- Cargar la imagen template: tasks/{task_id}/images/{session_indicator_image}
  Si el archivo template no existe: SessionStatus con is_logged_in=None, error="Template no encontrado"
- Usar PIL para buscar el template en el screenshot:
  from PIL import Image
  Usar pyautogui.locate() o PIL Image.find() para buscar la imagen template dentro del screenshot
  Si el match supera confidence threshold (settings.PYAUTOGUI_CONFIDENCE):
    is_logged_in = True
  Else:
    is_logged_in = False
- chrome_launcher.close()
- Retornar SessionStatus

Si cualquier excepción: SessionStatus con is_logged_in=False, error=str(e)
Siempre cerrar Chrome en try/finally.

3. Logging:
- "Verificando sesión de {task_name}..."
- "Sesión activa: {task_name}" o "Sesión expirada: {task_name}"

4. Bloque if __name__ == "__main__" con ejemplo de uso comentado.
```

---

### FEATURE 5 — tasks/ — Motor de ejecución con PyAutoGUI

**User Stories:** UC-06, UC-07, UC-08, UC-10

**Qué produce:**
- `tasks/base_task.py` con `BaseTask` (adaptado a PyAutoExecutor, sin Page)
- `tasks/mercadopago/task.py` y `schema.json`
- `tasks/galicia/task.py` y `schema.json`

**Contexto adicional:**
El cambio central: `navigate(self, executor)` y `trigger_download(self, executor)` reciben un `PyAutoExecutor` en lugar de un `Page` de Playwright. El método `run()` en BaseTask usa `ChromeLauncher` para abrir Chrome y `PyAutoExecutor` para controlar la pantalla.

**PROMPT A EJECUTAR:**

```
Crea el sistema de tasks adaptado a PyAutoGUI:

1. tasks/base_task.py — Clase abstracta BaseTask

Atributos que cada tarea concreta DEBE definir:
- task_id: str
- task_name: str
- platform_url: str
- date_handler_type: str  ('input_date' | 'datepicker_js' | 'no_filter' | 'macro')
- date_handler_kwargs: dict = {}
- date_mode: str = 'yesterday'
- session_check_url: str = ""
- session_indicator_image: str = ""  # Nombre del PNG en tasks/{task_id}/images/

Métodos abstractos:
- navigate(self, executor: PyAutoExecutor) -> None
- trigger_download(self, executor: PyAutoExecutor) -> None

Método concreto run(self, date_from: date, date_to: date) -> Path:
- Instanciar ChromeLauncher y PyAutoExecutor
- chrome_launcher.launch(self.platform_url)
- time.sleep(2)  # Esperar carga inicial
- executor = PyAutoExecutor()
- self.navigate(executor)
- handler = factory.get_handler(self.date_handler_type, **self.date_handler_kwargs)
- Si handler no es None: handler.set_dates(executor, date_from, date_to)
- watcher = DownloadWatcher()
- watcher._take_snapshot()  # Snapshot antes de descargar
- self.trigger_download(executor)
- filepath = watcher.wait_for_download()
- Si date_handler_type == 'no_filter': filtrar con pandas usando handler.context
- chrome_launcher.close()
- Retornar watcher.cleanup(filepath)

En excepción:
- Tomar screenshot con executor.screenshot()
- chrome_launcher.close() (try/finally)
- Relanzar con contexto

2. tasks/mercadopago/task.py — MercadoPagoTask(BaseTask)

task_id = "mercadopago_movimientos"
task_name = "Mercado Pago — Movimientos"
platform_url = "https://www.mercadopago.com.ar/activities"
date_handler_type = "datepicker_js"
date_mode = "yesterday"
session_check_url = "https://www.mercadopago.com.ar/home"
session_indicator_image = "mercadopago_session_ok.png"

navigate(): esperar imagen del dashboard cargado, log "Navegando a Mercado Pago..."
trigger_download(): esperar imagen del botón de descarga, hacer clic en él
Agregar TODO en ambos métodos: "Verificar y reemplazar templates de imagen al grabar con Macro Recorder"

3. tasks/mercadopago/schema.json:
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

4. tasks/galicia/task.py — GaliciaTask(BaseTask)

task_id = "galicia_movimientos"
task_name = "Banco Galicia — Extracto"
platform_url = "https://www.bancogalicia.com/personas/home.html"
date_handler_type = "no_filter"
date_mode = "last_month"
session_check_url = "https://www.bancogalicia.com/personas/home.html"
session_indicator_image = "galicia_session_ok.png"

5. tasks/galicia/schema.json:
{
  "task_id": "galicia_movimientos",
  "task_name": "Banco Galicia — Extracto",
  "platform": "galicia",
  "platform_url": "https://www.bancogalicia.com/personas/home.html",
  "date_handler_type": "no_filter",
  "date_mode": "last_month",
  "date_mode_options": ["last_month", "current_month", "custom"],
  "expected_file_extension": ".xlsx",
  "download_timeout_seconds": 90,
  "delivery": "direct",
  "session_check_url": "https://www.bancogalicia.com/personas/home.html",
  "session_indicator_image": "galicia_session_ok.png",
  "macro_id": null
}
```

---

### FEATURE 6 — uploader/ — Envío del archivo Excel al servidor

**User Stories:** UC-09, UC-13

**Qué produce:**
- `uploader/file_uploader.py` con `FileUploader`
- `uploader/manual_uploader.py` con `ManualUploader`

**Contexto adicional:**
Sin cambios de lógica ni contrato respecto a v1.2. La app no transforma los datos. La única excepción es `no_filter` (filtrar con pandas antes de subir).

**PROMPT A EJECUTAR:**

```
Crea el módulo uploader/ con los siguientes archivos:

1. uploader/file_uploader.py — Clase FileUploader

Constructor: __init__(self, api_client: ApiClient)

upload(self, task_id: str, filepath: Path, date_from: date, date_to: date,
       no_filter_context: dict = None, manual: bool = False) -> bool

Lógica:
a. Si no_filter_context no es None:
   - Leer Excel con pandas
   - Buscar columna de fecha (dtype datetime o nombre con 'fecha'/'date')
   - pd.to_datetime(errors='coerce')
   - Filtrar entre date_from y date_to
   - Guardar en archivo temporal con sufijo "_filtered"
   - filepath = path del filtrado
b. Construir metadata: {task_id, date_from ISO, date_to ISO, machine_id hostname, filename, manual_upload}
c. api_client.upload_file(task_id, filepath, metadata) → bool
d. Si exitoso y había filtrado: eliminar temporal
e. Eliminar original de temp/
f. Retornar True/False

2. uploader/manual_uploader.py — Clase ManualUploader

Constructor: __init__(self, file_uploader: FileUploader)

prompt_and_upload(self, task_id: str, task_name: str,
                  date_from: date, date_to: date) -> bool
- tkinter.filedialog.askopenfilename() con filtros [("Excel y CSV", "*.xlsx *.csv")]
- Si cancela: retornar False
- file_uploader.upload(..., manual=True)

Logging en ambas clases.
```

---

### FEATURE 7 — core/runner.py + core/reporter.py — Orquestador y Telemetría

**User Stories:** UC-02, UC-03, UC-04, UC-12, UC-14

**Qué produce:**
- `core/runner.py` con `TaskRunner`
- `core/reporter.py` con telemetría de negocio

**Contexto adicional:**
Sin cambios de contrato respecto a v1.2. TaskRunner sigue siendo el orquestador que llama a task.run(), uploader y reporter. El cambio es solo que task.run() ya no usa Playwright internamente — eso es transparente para el runner.

**PROMPT A EJECUTAR:**

```
Crea core/runner.py y core/reporter.py.

1. core/reporter.py — Clase Reporter

Constructor: __init__(self, api_client: ApiClient)

report_success(self, task_id, filepath, date_from, date_to, duration_seconds) -> None
- Contar filas del archivo (pandas para .xlsx, conteo de líneas para .csv)
- Si falla el conteo: usar -1 (no bloquear)
- POST a /rpa/telemetry: task_id, date_from ISO, date_to ISO, row_count,
  file_size_kb (filepath.stat().st_size/1024), duration_seconds, machine_id, timestamp
- Capturar excepciones silenciosamente (logger.warning)

report_failure(self, task_id, error, screenshot_path=None) -> None
- api_client.report_failure(task_id, error, screenshot_path)
- Log local

report_session_check(self, results: list) -> None
- api_client.report_session_check(results)
- Silencioso si falla

2. core/runner.py — Clase TaskRunner

PENDING, RUNNING, DONE, ERROR = 'pending', 'running', 'done', 'error'

Constructor:
__init__(self, task_list, on_status_change: Callable[[str, str, str], None],
         file_uploader, reporter)

run_all(self, date_mode=None, custom_from=None, custom_to=None) -> dict
Para cada tarea:
a. DateResolver.resolve(date_mode o task.date_mode, ...)
b. on_status_change(task.task_id, RUNNING, f"{date_from} → {date_to}")
c. start = time.time()
d. try:
   - filepath = task.run(date_from, date_to)
   - file_uploader.upload(task.task_id, filepath, date_from, date_to,
       no_filter_context=getattr(task, '_handler_context', None))
   - elapsed = time.time() - start
   - reporter.report_success(...)
   - on_status_change(task.task_id, DONE, f"OK — {elapsed:.0f}s")
e. except Exception as e:
   - screenshot = getattr(e, 'screenshot_path', None)
   - on_status_change(task.task_id, ERROR, str(e))
   - reporter.report_failure(task.task_id, str(e), screenshot)

Retornar: {"total", "success", "failed", "failed_tasks", "duration_seconds", "total_rows_processed"}
```

---

### FEATURE 8 — sync/ — Comunicación con el servidor Laravel

**User Stories:** UC-09, UC-10, UC-11, UC-12, UC-13

**Qué produce:**
- `sync/api_client.py` con `ApiClient`
- `sync/task_loader.py` con `TaskLoader`
- `sync/updater.py` con `UpdaterClient`
- `sync/macro_sync.py` con `MacroSync` ← NUEVO
- `sync/mock_data.py` con datos mock centralizados
- `sync/exceptions.py`
- `config/credentials.py`

**Contexto adicional:**
La diferencia con v1.2 es la adición de MacroSync. También se mantiene el sistema de mocks (USE_MOCK=True en settings.py) para permitir desarrollo sin el backend listo.

**PROMPT A EJECUTAR:**

```
Crea el módulo sync/ con los siguientes archivos:

1. sync/exceptions.py:
ApiAuthError, UploadError, ServerUnreachableError, MacroSyncError

2. sync/mock_data.py con datos mock centralizados:
- MOCK_TASK_LIST: lista de dos tareas (mercadopago_movimientos, galicia_movimientos) con su metadata
- MOCK_VERSION: {"version": "1.0.0", "release_notes": "Versión inicial"}
- MOCK_UPLOAD_RESPONSE: {"status": "ok", "message": "Archivo recibido"}
- MOCK_MACRO_LIST: lista vacía (no hay macros en el servidor mock)

3. sync/api_client.py — Clase ApiClient

Constructor: __init__(self)
- Si USE_MOCK: log "Modo mock activo — no se conecta al servidor"
- httpx.Client con base_url de settings.SERVER_URL, timeout=settings.HTTP_TIMEOUT_SECONDS

authenticate, load_token, upload_file, report_failure, report_telemetry, report_session_check
(contratos idénticos a CLAUDE.md sección 7. Modo mock: retornar siempre True/None silenciosamente.)

4. sync/task_loader.py — Clase TaskLoader

Constructor: __init__(self, api_client: ApiClient, macro_sync: MacroSync = None)

fetch_and_update(self) -> list[dict]
- Si USE_MOCK: leer schemas locales de tasks/ y retornar list de metadata
- Si real: GET /rpa/tasks → verificar hash → descargar cambios
- Si macro_sync provisto: llamar macro_sync.fetch_and_update() también
- Si servidor no disponible: leer cache local de TASK_CACHE_DIR

5. sync/macro_sync.py — Clase MacroSync  ← NUEVO

Constructor: __init__(self, api_client: ApiClient, storage: MacroStorage)

fetch_macros(self) -> list[dict]
- Si USE_MOCK: retornar lista vacía (no hay macros mock)
- GET /rpa/macros → lista de {macro_id, version, hash}

download_macro(self, macro_id: str) -> Recording
- GET /rpa/macros/{macro_id} → JSON → Recording

upload_macro(self, recording: Recording) -> bool
- POST /rpa/macros con JSON de la Recording
- Si exitoso: storage.save(recording) con flag "synced"
- Retornar True/False

fetch_and_update(self) -> None
- Comparar lista del servidor con macros locales
- Descargar solo las que cambiaron (verificar hash)
- Logging

6. sync/updater.py — Clase UpdaterClient

check(self) -> dict | None
- Si USE_MOCK: retornar None (sin actualización disponible)
- GET /rpa/version → comparar con APP_VERSION (semver) → dict | None

download(self, version_info, dest_folder) -> Path
- GET /rpa/download/{version} streaming

7. config/credentials.py:
get_api_token() -> str | None
set_api_token(token: str) -> None
Usar keyring ("rpa_conciliaciones", "api_token")
```

---

### FEATURE 9 — app/ui/ — Interfaz gráfica del contador

**User Stories:** UC-01, UC-02, UC-03, UC-04, UC-05b, UC-13

**Qué produce:**
- `app/ui/task_status.py`, `date_selector.py`, `dashboard.py`, `alert_modal.py`, `manual_upload.py`, `session_panel.py`
- Actualización de `app/main.py`

**Contexto adicional:**
Nuevo en v1.3: el overlay de "Bot en ejecución" (UC-02) que bloquea el mouse del contador durante la ejecución. El resto de la UI es idéntico a v1.2. Los paneles de macro (Feature 12) se integran en dashboard.py como tabs.

**PROMPT A EJECUTAR:**

```
Crea la interfaz gráfica con CustomTkinter:

1. app/ui/task_status.py — TaskStatusRow(ctk.CTkFrame)
- Constructor: parent, task_name, task_id, platform_url
- update_status(status: str, message: str):
  'pending': "⏸", gris
  'running': "⟳", azul
  'done': "✅", verde
  'done_manual': "📎✅", verde claro
  'error': "❌", rojo + botón "Cargar archivo"
- Mensajes de error en español, lenguaje simple

2. app/ui/date_selector.py — DateSelector(ctk.CTkFrame)
- Botones: "Ayer", "Esta semana", "Semana pasada", "Este mes", "Mes anterior", "Personalizado"
- "Personalizado" muestra dos DateEntry (tkcalendar)
- get_selection() -> dict: {"mode": str, "custom_from": date|None, "custom_to": date|None}
- Default: "Ayer"

3. app/ui/dashboard.py — Dashboard(ctk.CTk)
- 900×650, no redimensionable
- Layout: Header → DateSelector → Lista de tareas (scrollable) → Botón "▶ Ejecutar todo" → Barra de progreso
- Botón "▶ Ejecutar todo" grande y prominente
- Al ejecutar: mostrar overlay semitransparente "Bot en ejecución — no toques el mouse ni el teclado"
- show_update_banner(version_info): banner amarillo con "Nueva versión disponible"

PATRÓN OBLIGATORIO para thread-safety con queue.Queue:
```python
from queue import Queue, Empty
import threading

class Dashboard(ctk.CTk):
    def __init__(self, ...):
        self._status_queue: Queue[tuple[str, str, str]] = Queue()
        self._start_ui_polling()  # Iniciar ciclo de polling

    def _start_ui_polling(self):
        """Inicia el ciclo de polling del queue en el hilo de UI."""
        self._poll_queue()

    def _poll_queue(self):
        """Consume actualizaciones del queue. Thread-safe. Reprogramar cada 50ms."""
        try:
            while True:
                task_id, status, message = self._status_queue.get_nowait()
                self._update_task_row(task_id, status, message)
        except Empty:
            pass
        self.after(50, self._poll_queue)

    def on_status_change(self, task_id: str, status: str, message: str) -> None:
        """Callback para TaskRunner. PUEDE ser llamado desde cualquier thread."""
        self._status_queue.put((task_id, status, message))

    def on_execute_click(self):
        selection = self._date_selector.get_selection()
        self._show_execution_overlay()
        self._execute_button.configure(state="disabled")
        Thread(daemon=True, target=self._run_tasks_background,
               args=(selection,)).start()

    def _run_tasks_background(self, selection: dict):
        """Corre en hilo background. NO tocar widgets directamente."""
        result = self._runner.run_all(
            date_mode=selection['mode'],
            custom_from=selection.get('custom_from'),
            custom_to=selection.get('custom_to')
        )
        # Comunicar fin de ejecución al hilo principal:
        self.after(0, self._on_execution_complete, result)

    def _on_execution_complete(self, result: dict):
        """Siempre corre en el hilo principal. Seguro para widgets."""
        self._hide_execution_overlay()
        self._execute_button.configure(state="normal")
        self._show_summary(result)
```
# POR QUÉ QUEUE Y NO SOLO self.after(0, lambda: widget.configure(...)):
# - El lambda en after(0, ...) acumula sin control de flujo.
# - Queue.get_nowait() vacía todos los mensajes pendientes en cada poll.
# - Si el runner llama on_status_change 50 veces rápido, todos se procesan en orden.

4. app/ui/alert_modal.py — AlertModal(ctk.CTkToplevel)
- Recibe: parent, task_name, error_message, platform_url, on_manual_upload
- Contenido: ícono advertencia, título simple, mensaje en español, detalle técnico colapsable
- Botones: "Abrir sitio web" (webbrowser.open), "Cargar archivo manualmente", "Cerrar"

5. app/ui/manual_upload.py — ManualUploadModal(ctk.CTkToplevel)
- Instrucciones claras para el contador
- filedialog.askopenfilename con filtros xlsx/csv
- Preview del nombre seleccionado
- Botones: "Subir al servidor", "Cancelar"

6. app/ui/session_panel.py — SessionPanel(ctk.CTkFrame)
- Muestra SessionStatus por tarea
- ✅ / ⚠️ / ❓ con nombre de la plataforma
- Botón "Abrir [plataforma]" si expirada
- update(results: list[SessionStatus])

7. Actualizar app/main.py:
- Instanciar ApiClient, MacroStorage, MacroSync, TaskLoader (con macro_sync), UpdaterClient
- fetch_and_update() en thread background
- updater.check() en thread background
- Instanciar ChromeLauncher, PyAutoExecutor, HealthChecker
- Instanciar Dashboard
- dashboard.run_health_check() en thread background al iniciar
- mainloop()
- sys.excepthook global que loguea errores no capturados

Todos los mensajes visibles al contador en español y lenguaje de negocio.
Thread-safety: toda actualización de UI via self.after(0, callback).
```

---

### FEATURE 10 — Empaquetado final en .exe

**User Stories:** Distribución a contadores

**Qué produce:**
- `build/installer.spec`
- `build/build.bat`

**PROMPT A EJECUTAR:**

```
Crea los archivos finales de empaquetado:

1. build/installer.spec — Configuración de PyInstaller

analysis = Analysis(['app/main.py'], ...)
datas:
  ('tasks/', 'tasks/')
  ('config/', 'config/')
  ('macros/', 'macros/')
hiddenimports:
  ['pyautogui', 'pynput', 'pynput.mouse', 'pynput.keyboard',
   'pyperclip', 'PIL', 'PIL.Image',
   'pygetwindow',
   'customtkinter', 'tkcalendar',
   'pandas', 'openpyxl',
   'httpx', 'keyring', 'keyring.backends',
   'semver', 'dateutil', 'dateutil.relativedelta']
name: 'RPA_Conciliaciones'
icon: None  # TODO: reemplazar con ruta a .ico
onefile: True
console: False
upx: False
Excluir explícitamente: playwright, apscheduler, selenium

2. build/build.bat

@echo off
echo ==========================================
echo  Compilando RPA Conciliaciones v1.0
echo ==========================================
echo.
echo Instalando dependencias...
pip install -r requirements.txt
echo.
echo Compilando ejecutable...
pyinstaller build/installer.spec --clean --noconfirm
echo.
echo ==========================================
echo  Listo. Ejecutable en dist/RPA_Conciliaciones.exe
echo ==========================================
pause
```

---

### FEATURE 11 — macros/ — Sistema de grabación y reproducción

**User Stories:** UC-15, UC-16

**Qué produce:**
- `macros/models.py` con `Action`, `Recording`
- `macros/recorder.py` con `MacroRecorder`
- `macros/player.py` con `MacroPlayer`
- `macros/storage.py` con `MacroStorage`
- `macros/date_step.py` (constantes de tipos de DateStep)

**Contexto adicional:**
Este es el feature central de v1.3. El Recorder escucha eventos de mouse y teclado con `pynput` y los guarda como una lista de `Action`. La `DateStep` es un tipo especial de Action que el técnico inserta manualmente marcando "este campo es la fecha de inicio en formato dd/mm/yyyy". Al reproducir, MacroPlayer reemplaza esas acciones con la fecha real calculada por DateResolver.

**PROMPT A EJECUTAR:**

```
Crea el módulo macros/ completo:

1. macros/models.py

from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class Action:
    type: str               # 'click' | 'double_click' | 'right_click' | 'key' | 'type'
                            # | 'paste' | 'scroll' | 'wait_image' | 'date_step' | 'delay'
    x: int | None = None
    y: int | None = None
    text: str | None = None
    keys: list[str] = field(default_factory=list)
    image_template: str | None = None  # nombre del PNG en macros/images/ para wait_image
    delay: float = 0.1
    date_field: str | None = None      # 'date_from' | 'date_to' (solo date_step)
    date_format: str | None = None     # '%d/%m/%Y' | '%Y-%m-%d' (solo date_step)
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

2. macros/date_step.py

DATE_FROM = 'date_from'
DATE_TO = 'date_to'
FORMATS_COMUNES = {
    'ISO': '%Y-%m-%d',
    'Argentino': '%d/%m/%Y',
    'DDMMYYYY': '%d%m%Y',
    'YYYYMMDD': '%Y%m%d',
}

3. macros/recorder.py — Clase MacroRecorder

Constructor: __init__(self)
Atributos: _actions: list[Action] = [], _recording: bool = False,
           _mouse_listener: pynput.mouse.Listener, _keyboard_listener: pynput.keyboard.Listener,
           _current_recording_meta: dict = {}

start(self, macro_id, macro_name, platform_url, task_id) -> None
- Si ya está grabando: MacroRecorderError
- Inicializar _actions = []
- Guardar meta en _current_recording_meta
- Iniciar pynput mouse listener (captura clic izquierdo + posición)
- Iniciar pynput keyboard listener (captura teclas)
- self._recording = True
- Log: "Grabación iniciada: {macro_name}"

stop(self) -> Recording
- Detener ambos listeners
- self._recording = False
- Construir Recording con _actions y _current_recording_meta
- Log: "Grabación detenida. {len(actions)} acciones grabadas."
- Retornar Recording

mark_date_step(self, date_field: str, date_format: str) -> None
- Si no está grabando: MacroRecorderError
- Insertar Action(type='date_step', date_field=date_field, date_format=date_format)
- El próximo evento de teclado que se grabe REEMPLAZA su texto por el date_step
- Log: "Marcador de fecha insertado: {date_field} formato {date_format}"

@property
is_recording(self) -> bool

Callbacks de pynput — FILTROS OBLIGATORIOS para reducir ruido:

_on_move(x, y): NO capturar. Los movimientos de mouse generan miles de acciones inútiles.
  Pynput: en mouse.Listener, on_move=None o simplemente no definirlo.

_on_click(x, y, button, pressed):
  - Solo capturar si pressed=True (click-down) y button == Button.left
  - COLAPSAR multi-clic: si la distancia al último click es < 5px Y el tiempo < 300ms:
      Si último action es 'click': reemplazar por 'double_click'
      Si último action es 'double_click': reemplazar por 'triple_click'
  - Si no: _actions.append(Action(type='click', x=x, y=y))
  - Guardar _last_click_time = time.time() y _last_click_pos = (x, y)
  - Implementación:
    import math
    dist = math.sqrt((x - self._last_click_pos[0])**2 + (y - self._last_click_pos[1])**2)
    if dist < 5 and (time.time() - self._last_click_time) < 0.3:
        if self._actions and self._actions[-1].type == 'click':
            self._actions[-1] = Action(type='double_click', x=x, y=y)
        elif self._actions and self._actions[-1].type == 'double_click':
            self._actions[-1] = Action(type='triple_click', x=x, y=y)
    else:
        self._actions.append(Action(type='click', x=x, y=y))

_on_key_release(key):
  - NO capturar teclas de modificador sueltas (Key.shift, Key.ctrl, Key.alt solos)
  - Para texto normal: agregar Action(type='type', text=char)
  - Para combinaciones especiales (ctrl+c, ctrl+v, etc.): agregar Action(type='key', keys=[...])
  - Ignorar durante date_step pendiente (el técnico está escribiendo la fecha que se reemplazará)

LÍMITES de grabación (advertencias en UI):
- Si len(_actions) > 400: logger.warning + panel muestra "⚠ Grabación muy larga. Considera dividirla."
- Si len(_actions) > 600: logger.error + botón "Detener" parpadea en rojo

4. macros/player.py — Clase MacroPlayer

Constructor: __init__(self, executor: PyAutoExecutor)

play(self, recording: Recording, date_from: date, date_to: date) -> None
- Para cada action en recording.actions:
  - time.sleep(action.delay)
  - Ejecutar según action.type:
    'click': executor.click(action.x, action.y)
    'double_click': executor.double_click(action.x, action.y)
    'type': executor.type_text(action.text)
    'paste': executor.paste_text(action.text)
    'key': executor.press_key(*action.keys)
    'scroll': executor.scroll(action.clicks, action.x, action.y)
    'wait_image': executor.wait_for_image(Path(images_dir) / action.image_template,
                                          timeout=30, confidence=action.confidence)
    'date_step': _play_date_step(action, date_from, date_to)
    'delay': time.sleep(action.delay)

_play_date_step(self, action: Action, date_from: date, date_to: date) -> None
- Determinar la fecha: date_from si action.date_field == DATE_FROM, date_to si DATE_TO
- Formatear: fecha.strftime(action.date_format)
- executor.paste_text(fecha_formateada)

Si wait_for_image lanza ImageNotFoundError:
  screenshot_path = executor.screenshot()
  raise PlaybackError(f"No se encontró {action.image_template} en el paso {index}",
                      screenshot_path=screenshot_path)

5. macros/storage.py — Clase MacroStorage

Constructor: __init__(self, storage_dir: Path | None = None)
- storage_dir default: AppData/Local/rpa_conciliaciones/macros/
- Crear dir si no existe

save(self, recording: Recording) -> Path
- JSON: dataclasses.asdict(recording) con datetime → isoformat
- Guardar en storage_dir/{macro_id}.json
- Retornar Path

load(self, macro_id: str) -> Recording | None
- Cargar JSON, reconstruir Recording + lista de Action
- Retornar None si no existe

list_all(self) -> list[Recording]
delete(self, macro_id: str) -> None

6. Agregar PlaybackError a macros/exceptions.py:
PlaybackError(Exception) con atributo screenshot_path: Path | None

7. Docstrings completos en recorder y player explicando el modelo mental de grabación/reproducción.
```

---

### FEATURE 12 — Integración de macros en runner y UI

**User Stories:** UC-15, UC-16

**Qué produce:**
- `app/ui/macro_recorder_panel.py` con `MacroRecorderPanel`
- `app/ui/macro_list_panel.py` con `MacroListPanel`
- Integración de ambos panels en `dashboard.py` como tab secundaria
- Actualización de `core/runner.py` para ejecutar macros si `macro_id` está presente

**Contexto adicional:**
El runner, al ejecutar una tarea, verifica si tiene `macro_id`. Si lo tiene y la macro existe en MacroStorage, usa MacroPlayer en lugar del flujo de task.run(). Si no, usa el flujo habitual de task.run() (PyAutoGUI code-based).

**PROMPT A EJECUTAR:**

```
Implementa la integración de macros:

1. Actualizar core/runner.py — soporte de macro_id

En run_all(), antes de task.run():
- Si task tiene atributo macro_id (no None):
  a. macro = macro_storage.load(task.macro_id)
  b. Si macro exists:
     - chrome_launcher = ChromeLauncher()
     - chrome_launcher.launch(task.platform_url)
     - time.sleep(2)
     - executor = PyAutoExecutor()
     - player = MacroPlayer(executor)
     - player.play(macro, date_from, date_to)
     - filepath = watcher.wait_for_download()
     - chrome_launcher.close()
     - filepath → cleanup → upload
  c. Si macro no existe en storage: usar task.run() como fallback (log warning)

Constructor del TaskRunner actualizado:
__init__(self, task_list, on_status_change, file_uploader, reporter,
         macro_storage: MacroStorage | None = None)

2. app/ui/macro_recorder_panel.py — MacroRecorderPanel(ctk.CTkFrame)

ESTADO INICIAL (antes de grabar):
- Campo "Nombre de la macro" (label: "Nombre *")
- Campo "URL de la plataforma" (label: "URL * (debe empezar con https://)")
- Botón verde grande: "⏺ Iniciar grabación"

VALIDACIONES antes de iniciar (en on_start_click()):
a. Nombre no vacío → si vacío: resaltar campo en rojo, mostrar "El nombre es obligatorio"
b. URL válida → si no empieza con http:// o https://: mostrar "La URL debe empezar con https://"
c. Chrome abierto → gw.getWindowsWithTitle('Chrome') no vacío
   Si no hay Chrome: mostrar modal "Abrí Chrome en la plataforma antes de iniciar la grabación"
d. Si todo OK: iniciar countdown

COUNTDOWN (5 segundos, en el hilo de UI vía after()):
- Label grande: "Iniciando grabación en: 5"
- Actualizar cada segundo con after(1000, ...)
- Botón "Cancelar" visible durante el countdown
- Al llegar a 0: ocultar countdown, mostrar panel "Grabando"

ESTADO GRABANDO:
- Indicador rojo pulsante: "● Grabando..." (alternating opacity con after(500, ...))
- Contador en tiempo real: "47 acciones grabadas" (actualizado desde on_status_change)
- Timer: "Tiempo: 1:23" (actualizado cada segundo)
- Si acciones > 400: cambiar contador a naranja + "⚠ Macro muy larga"
- Botones disponibles:
  "↩ Deshacer última acción" → recorder._actions.pop() si no vacío
  "📅 Marcar fecha inicio" → dropdown con formatos: ISO, Argentino, DDMMYYYY, YYYYMMDD
  "📅 Marcar fecha fin"    → igual
  "⏹ Detener y guardar"

ESTADO POST-GRABACIÓN:
- Lista scrollable de acciones grabadas (tipo + datos resumidos)
- Campo de descripción opcional: "Descripción de la macro (opcional)"
- Botones: "💾 Guardar localmente", "💾📤 Guardar y publicar", "🗑 Descartar"
- Confirmación antes de descartar si hay acciones grabadas

Callbacks thread-safe con self.after(0, ...).
Mensajes al técnico en español técnico (no de negocio — este panel es solo para técnicos).

3. app/ui/macro_list_panel.py — MacroListPanel(ctk.CTkFrame)

- Lista todas las macros de MacroStorage
- Por cada macro: nombre, task_id, fecha de creación, versión
- Botones por macro: "▶ Probar", "🗑 Eliminar", "📤 Publicar"
- "▶ Probar" ejecuta la macro con DateResolver.resolve('yesterday') como prueba
- refresh() recarga la lista desde storage

4. Integrar en dashboard.py:
- Agregar CTkTabview con dos tabs: "Tareas" (tab principal actual) y "Macros" (tab para técnicos)
- "Tareas": el contenido actual del dashboard
- "Macros": MacroRecorderPanel arriba, MacroListPanel abajo
- El tab de "Macros" está oculto por default; visible si settings.SHOW_MACRO_TAB = True
  (para que los contadores no lo vean, solo los técnicos)

5. Agregar a config/settings.py:
SHOW_MACRO_TAB = False   # True solo para técnicos
```

---

## 8. ALCANCE Y FUERA DE ALCANCE

### En Alcance — Versión 1.0

- Aplicación de escritorio para Windows (empaquetada como .exe)
- Motor de automatización visual con PyAutoGUI sobre Chrome real del usuario
- **Macro Recorder integrado**: grabación de bots sin código para técnicos (UC-15)
- **Macro Player**: reproducción de macros con inyección de fechas dinámicas (UC-16)
- Health Check de sesiones (pre-flight check) con image templates
- Tres tipos de date handler: input nativo, datepicker visual (image templates), sin filtro
- Sistema de variables de fecha dinámica: modos día/semana/mes con resolución automática
- Sistema de bots por plataforma: task.py + schema.json + macros JSON
- Soporte de archivos: solo **.xlsx y .csv**
- Upload del archivo Excel crudo al servidor. ETL completamente en el servidor.
- Fallback de carga manual para plataformas con email delivery o cuando el bot falla
- Telemetría de negocio: volumen de transacciones por tarea y período
- MacroSync: sincronización de macros grabadas con el servidor Laravel
- Auto-update del .exe con notificación al contador (no forzado)
- **Plataformas piloto v1.0:** Mercado Pago y Banco Galicia

### Fuera de Alcance — Versión 1.0

- Soporte para Mac OS o Linux. Solo Windows.
- Soporte para Edge, Firefox u otros navegadores. Solo Chrome.
- Modo headless o ejecución sin pantalla (PyAutoGUI requiere pantalla real).
- Transformación o normalización de columnas del Excel en la app.
- Soporte para archivos .xls (Excel 97-2003).
- **Scheduler automático (ejecución desatendida)** → pospuesto a v1.1
- Plataformas que requieren 2FA en cada login sin posibilidad de sesión persistente.
- Múltiples perfiles de Chrome en el mismo equipo.
- Ejecución en paralelo de tareas.
- Automatización de aplicaciones de escritorio nativas (no Chrome). PyAutoGUI lo permite técnicamente, pero está fuera del alcance del piloto.

### Roadmap v1.1 (post-MVP)

- Scheduler automático con pre-flight check de sesiones integrado
- Soporte para sesiones desatendidas (notificación al contador 5 min antes para refresh)
- Dashboard de telemetría en el servidor para ejecutivos
- Macro editor: edición visual de acciones grabadas sin re-grabar todo

---

## 9. DECISIONES RESUELTAS

### Decisiones de v1.1 y v1.2 (heredadas)

| # | Pregunta original | Decisión |
|---|---|---|
| 1 | ¿La API Laravel tiene endpoint para recibir datos? | No existe. Se crea en este proyecto. Contrato: POST multipart con Excel crudo + metadata. |
| 2 | ¿Toteat descarga directo o por email? | Descarga directa. Email activa flujo manual (UC-13). |
| 3 | ¿Qué navegador usan los contadores? | Chrome obligatorio por política interna. |
| 4 | ¿Cómo se distribuye el .exe? | Servidor de actualizaciones en Laravel/Hostinger. Endpoints /rpa/. |
| 5 | ¿El formato de la API está definido? | Archivo Excel crudo. El servidor ETL hace el mapping. |
| 6 | ¿Cuál es el período de fecha por defecto? | Configurable por tarea en schema.json (date_mode). |

### Decisiones de v1.3 (migración PyAutoGUI)

| Cambio | Decisión | Razón |
|---|---|---|
| **REEMPLAZADO:** Playwright → PyAutoGUI | BrowserManager eliminado. ChromeLauncher + PyAutoExecutor como nuevo motor. | PyAutoGUI controla cualquier UI visualmente sin depender del DevTools Protocol. Más universal, más simple de grabar bots, no requiere selectores CSS que se rompen con updates de portales. |
| **REEMPLAZADO:** playwright codegen → Macro Recorder | El técnico graba bots con el Macro Recorder integrado, sin escribir código. | El modelo de "grabar y reproducir" es más intuitivo, más rápido (15 min vs horas de codegen+debug) y no requiere conocer HTML/CSS. |
| **NUEVO:** macros/ módulo | Recording, MacroRecorder, MacroPlayer, MacroStorage, MacroSync | Permite grabar, reproducir y distribuir bots sin código. Los DateStep resuelven el problema de fechas dinámicas en macros. |
| **ACTUALIZADO:** HealthChecker | Usa ChromeLauncher + PIL image matching en lugar de Playwright. | Consistencia con el nuevo stack: todo usa ChromeLauncher, no hay dependencia de Playwright. |
| **ACTUALIZADO:** date_handlers | Reciben PyAutoExecutor en lugar de Page. Usan image templates. | Eliminación de Playwright como dependencia. Las image templates son más robustas a cambios de CSS. |
| **NUEVO RIESGO:** DPI/resolución | config/settings.py almacena DPI al grabar. UI avisa si hay mismatch. | PyAutoGUI es sensible a la resolución. Requiere estandarización de DPI entre equipos de técnicos y contadores. |
| **NUEVO RIESGO:** Foco de ventana | ChromeLauncher mantiene Chrome en foco. UI muestra overlay durante ejecución. | PyAutoGUI necesita que la ventana objetivo esté en foco para que los clicks lleguen correctamente. |

### Acción pendiente crítica antes de iniciar Feature 5

**Mapeo de 2FA y DPI — Responsable: Equipo técnico — Bloquea: Feature 5**

Antes de grabar los bots piloto:
1. **2FA:** Verificar si Galicia y Mercado Pago requieren 2FA en cada login
2. **DPI:** Confirmar que todos los equipos de contadores usan DPI 100% (sin escalado de pantalla)
3. **Resolución:** Confirmar resolución mínima (≥ 1280×720) en todos los equipos de contadores

---

*Documento vivo. Versión 1.4 — Febrero 2026.*
*Próxima actualización: resultado del mapeo de 2FA + DPI, y definición de plataformas post-piloto (Toteat, Clover, Payway, Dragonfish).*
