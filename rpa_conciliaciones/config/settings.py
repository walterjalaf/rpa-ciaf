"""
Configuración central del proyecto RPA Conciliaciones.

Por qué existe: Centraliza todas las constantes configurables del sistema
para que ningún módulo hardcodee valores. Cuando el equipo técnico necesite
cambiar la URL del servidor o el timeout de descarga, lo hace acá.
"""

# ── Modo de desarrollo ─────────────────────────────────────────
# Cuando USE_MOCK = True, los módulos sync/ y uploader/ trabajan contra
# datos locales en lugar de hacer peticiones HTTP al servidor.
# Cambiar a False cuando la API de Laravel esté lista.
USE_MOCK = True

# Servidor Laravel — VPS Hostinger
SERVER_URL = "https://tudominio.hostinger.com"  # Actualizar con URL real del VPS

# Versión de la app (comparada con el servidor para auto-update)
APP_VERSION = "1.0.0"

# Chrome — el path se detecta automáticamente en core/chrome_launcher.py
CHROME_PROFILE_PATH = ""  # Detectado automáticamente
CHROME_EXECUTABLE_PATH = ""  # Vacío = autodetección por paths comunes de Windows

# PyAutoGUI — configuración de image matching
PYAUTOGUI_CONFIDENCE = 0.8         # Confianza por defecto para wait_for_image
PYAUTOGUI_ACTION_DELAY = 0.1       # Pausa global entre acciones (segundos)

# Feature flags — solo para técnicos
SHOW_MACRO_TAB = True              # True habilita la pestaña Macros en la UI

# Timeouts
DOWNLOAD_TIMEOUT_SECONDS = 60
HEALTH_CHECK_TIMEOUT_SECONDS = 10
HTTP_TIMEOUT_SECONDS = 30

# Logging
LOG_LEVEL = "INFO"

# Cache local para TaskLoader
TASK_CACHE_DIR = ""  # Se resuelve en runtime a ~/.rpa_conciliaciones/
