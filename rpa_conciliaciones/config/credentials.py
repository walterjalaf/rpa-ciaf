"""
Gestión de credenciales en el Credential Vault de Windows.

Por qué existe: Centraliza el acceso a keyring para que los módulos sync/
no tengan que conocer los detalles de almacenamiento. El token del servidor
Laravel se guarda en el Credential Vault del OS (no en texto plano).

Uso:
    from config.credentials import get_api_token, set_api_token

    token = get_api_token()          # Leer token guardado
    set_api_token("mi_token_secret") # Guardar token nuevo
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_SERVICE_NAME = "rpa_conciliaciones"
_USERNAME = "api_token"


def get_api_token() -> str | None:
    """
    Lee el token de autenticación del Credential Vault de Windows.

    Returns:
        Token como string, o None si no hay token guardado o keyring falla.
    """
    try:
        import keyring
        token = keyring.get_password(_SERVICE_NAME, _USERNAME)
        if token:
            logger.debug("Token API cargado desde Credential Vault")
        else:
            logger.debug("No hay token API guardado en Credential Vault")
        return token
    except Exception as e:
        logger.warning("No se pudo leer el token del Credential Vault: %s", e)
        return None


def set_api_token(token: str) -> None:
    """
    Guarda el token de autenticación en el Credential Vault de Windows.

    Args:
        token: Token Bearer para autenticarse con el servidor Laravel.

    Raises:
        Exception: Si keyring no puede guardar las credenciales.
            Esto puede ocurrir en sistemas sin Credential Vault.
    """
    try:
        import keyring
        keyring.set_password(_SERVICE_NAME, _USERNAME, token)
        logger.info("Token API guardado en Credential Vault")
    except Exception as e:
        logger.error(
            "No se pudo guardar el token en el Credential Vault: %s", e
        )
        raise


def delete_api_token() -> None:
    """
    Elimina el token del Credential Vault (útil para logout o reset).

    No lanza excepción si el token no existe.
    """
    try:
        import keyring
        keyring.delete_password(_SERVICE_NAME, _USERNAME)
        logger.info("Token API eliminado del Credential Vault")
    except Exception as e:
        logger.warning(
            "No se pudo eliminar el token del Credential Vault: %s", e
        )


if __name__ == "__main__":
    import logging as _logging
    _logging.basicConfig(level=_logging.DEBUG)

    current = get_api_token()
    print(f"Token guardado actualmente: {'Sí' if current else 'No'}")
    print("(No modificar credenciales reales en prueba manual)")
