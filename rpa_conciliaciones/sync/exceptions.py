"""
Excepciones del módulo sync/.

Por qué existe: Centraliza los errores de comunicación HTTP para que los
módulos consumidores (uploader/, core/reporter.py) puedan capturar fallos
específicos del servidor sin acoplarse a httpx ni a detalles de red.
"""


class ApiAuthError(Exception):
    """Token de autenticación inválido o expirado (HTTP 401)."""


class UploadError(Exception):
    """El servidor rechazó el archivo subido (HTTP 422 o validación fallida)."""


class ServerUnreachableError(Exception):
    """No se pudo conectar al servidor (timeout, DNS, red caída)."""


class MacroSyncError(Exception):
    """Error al sincronizar macros con el servidor (descarga, upload o hash mismatch)."""
