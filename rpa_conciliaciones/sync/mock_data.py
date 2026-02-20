"""
Datos mock centralizados para desarrollo sin servidor Laravel.

Por qué existe: Cuando USE_MOCK = True en config/settings.py, los módulos
sync/ y uploader/ usan estos datos en lugar de hacer peticiones HTTP reales.
Centralizar los mocks acá evita duplicar datos de prueba en cada módulo.

Estos datos simulan las respuestas que daría el servidor Laravel.
"""

from datetime import datetime


# ── Respuesta simulada de GET /rpa/tasks ───────────────────────

MOCK_TASK_LIST: list[dict] = [
    {
        "task_id": "mercadopago_movimientos",
        "task_name": "Mercado Pago — Movimientos",
        "platform": "mercadopago",
        "hash": "mock_hash_mp_001",
        "active": True,
    },
    {
        "task_id": "galicia_movimientos",
        "task_name": "Banco Galicia — Extracto",
        "platform": "galicia",
        "hash": "mock_hash_gal_001",
        "active": True,
    },
]


# ── Respuesta simulada de GET /rpa/version ─────────────────────

MOCK_VERSION_INFO: dict = {
    "latest_version": "1.0.0",
    "download_url": "/rpa/download/1.0.0",
    "release_notes": "Versión inicial",
    "released_at": "2026-02-18T00:00:00Z",
}


# ── Funciones que simulan respuestas de endpoints POST ─────────

def mock_upload_response(task_id: str, filename: str) -> dict:
    """Simula la respuesta exitosa de POST /rpa/upload."""
    return {
        "status": "ok",
        "task_id": task_id,
        "filename": filename,
        "received_at": datetime.now().isoformat(),
        "message": "Archivo recibido correctamente (mock)",
    }


def mock_telemetry_response() -> dict:
    """Simula la respuesta de POST /rpa/telemetry."""
    return {"status": "ok", "message": "Telemetría registrada (mock)"}


def mock_failure_response() -> dict:
    """Simula la respuesta de POST /rpa/failure."""
    return {"status": "ok", "message": "Fallo registrado (mock)"}


def mock_session_check_response() -> dict:
    """Simula la respuesta de POST /rpa/session_check."""
    return {"status": "ok", "message": "Estado de sesiones registrado (mock)"}


# ── Respuesta simulada de GET /rpa/macros ──────────────────────
# Lista vacía: en desarrollo no hay macros publicadas en el servidor mock.
# El técnico graba macros localmente con MacroRecorder (Feature 11).
MOCK_MACRO_LIST: list[dict] = []
