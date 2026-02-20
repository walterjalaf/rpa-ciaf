# Skill: API Logic

| Campo | Valor |
|---|---|
| **Name** | API Logic |
| **Description** | Reglas para la capa de comunicación HTTP con el servidor Laravel. Cubre httpx, manejo de errores, retry, upload multipart y telemetría. |
| **Trigger** | El prompt contiene: "API", "endpoint", "upload", "servidor", "httpx", "sync/" |
| **Scope** | `sync/api_client.py`, `sync/task_loader.py`, `sync/updater.py`, `uploader/file_uploader.py` |

---

## Reglas obligatorias

### 1. Cliente HTTP: httpx síncrono

El proyecto usa `httpx` síncrono. No usar `aiohttp`, `requests` ni `urllib`.

```python
import httpx

class ApiClient:
    def __init__(self, base_url: str, timeout: float = 30.0):
        self._client = httpx.Client(
            base_url=base_url,
            timeout=timeout,
            headers={"Accept": "application/json"}
        )
```

### 2. Autenticación via Bearer token

El token se almacena en Windows Credential Vault via `keyring`:

```python
import keyring

token = keyring.get_password("rpa_conciliaciones", "api_token")
self._client.headers["Authorization"] = f"Bearer {token}"
```

### 3. Upload de archivos: multipart/form-data

```python
def upload_file(self, task_id: str, filepath: Path, metadata: dict) -> bool:
    with open(filepath, "rb") as f:
        response = self._client.post(
            "/rpa/upload",
            files={"file": (filepath.name, f)},
            data={
                "task_id": task_id,
                "date_from": metadata["date_from"].isoformat(),
                "date_to": metadata["date_to"].isoformat(),
                "machine_id": platform.node(),
            }
        )
    return response.status_code in (200, 201)
```

### 4. Política de errores HTTP

| Status | Acción |
|---|---|
| 200, 201 | OK |
| 401 | Lanzar `ApiAuthError` — token inválido o expirado |
| 422 | Loguear campos rechazados, lanzar `UploadError` |
| 500+ | Loguear, no reintentar (el servidor tiene un problema) |
| Timeout | Loguear, marcar tarea como error |

### 5. Telemetría: no bloquea el flujo

Las llamadas a `/rpa/telemetry` y `/rpa/session_check` nunca deben propagar excepciones:

```python
def report_telemetry(self, ...) -> None:
    try:
        self._client.post("/rpa/telemetry", json={...})
    except Exception as e:
        logger.warning(f"Telemetria no enviada: {e}")
```

### 6. Task Loader: cache local

`task_loader.py` guarda la última lista de tareas válida en disco. Si el servidor no responde, usa el cache:

```python
CACHE_PATH = Path.home() / ".rpa_conciliaciones" / "task_cache.json"
```

### 7. Excepciones del módulo

Definidas en `sync/exceptions.py`:
- `ApiAuthError` — token inválido
- `UploadError` — el servidor rechazó el archivo
- `ServerUnreachableError` — timeout o DNS failure

---

## Endpoints de referencia

```
GET  /rpa/tasks                  → lista de tareas con hash
GET  /rpa/tasks/{id}/script      → descarga task.py
GET  /rpa/tasks/{id}/schema      → descarga schema.json
GET  /rpa/version                → versión actual del .exe
GET  /rpa/download/{version}     → descarga el nuevo .exe
POST /rpa/upload                 → archivo Excel + metadata
POST /rpa/failure                → reporte de fallo
POST /rpa/telemetry              → métricas de tarea exitosa
POST /rpa/session_check          → resultados de health check
```
