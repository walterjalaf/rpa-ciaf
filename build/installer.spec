# -*- mode: python ; coding: utf-8 -*-
"""
installer.spec — Configuración de PyInstaller para RPA Conciliaciones.

Por qué existe: Define cómo empaquetar todos los módulos, datos y dependencias
en un único .exe distribuible a contadores sin Python instalado.

Notas de arquitectura:
- Entry point: rpa_conciliaciones/app/main.py
- pathex apunta a rpa_conciliaciones/ porque los imports son planos:
  'from core.runner import ...' asume que rpa_conciliaciones/ está en sys.path.
- datas incluye tasks/ y macros/ porque main.py los carga dinámicamente con
  importlib.util.spec_from_file_location(), que requiere los .py en disco.
  En onefile, sys._MEIPASS actúa como PROJECT_ROOT; main.py usa parent.parent
  de __file__ para resolverlo, lo que funciona en modo frozen.
- upx=False para evitar falsos positivos de antivirus en entornos corporativos.
- console=False — la app es de escritorio; errores críticos van al log.

Ejecutar desde la raíz del proyecto:
    pyinstaller build/installer.spec --clean --noconfirm
    (o usar build/build.bat que hace esto automáticamente)

TODO: Reemplazar icon=None con icon='build/rpa_icon.ico' cuando esté disponible.
"""

import os

from PyInstaller.utils.hooks import collect_data_files

# ── Rutas de referencia ──────────────────────────────────────────────────────
# SPECPATH es la carpeta donde vive este .spec (build/).
# PROJECT_ROOT es la raíz del repositorio (un nivel arriba).
PROJECT_ROOT = os.path.abspath(os.path.join(SPECPATH, '..'))
SRC_ROOT = os.path.join(PROJECT_ROOT, 'rpa_conciliaciones')

# ── Datos de customtkinter (temas JSON y assets de imagen) ──────────────────
# Sin estos archivos, la UI arranca con errores de tema no encontrado.
_ctk_datas = collect_data_files('customtkinter')

# ── Datos del proyecto ───────────────────────────────────────────────────────
# tasks/   → schemas JSON, templates PNG e implementaciones .py por plataforma
# macros/  → grabaciones JSON y templates PNG (incluir solo si el módulo existe)
_project_datas = [
    (os.path.join(SRC_ROOT, 'tasks'), 'tasks'),
]

_macros_src = os.path.join(SRC_ROOT, 'macros')
if os.path.isdir(_macros_src):
    _project_datas.append((_macros_src, 'macros'))

# ── Análisis ─────────────────────────────────────────────────────────────────
a = Analysis(
    [os.path.join(SRC_ROOT, 'app', 'main.py')],
    pathex=[SRC_ROOT],      # Permite 'from core.x import ...' directamente
    binaries=[],
    datas=[
        *_project_datas,
        *_ctk_datas,
    ],
    hiddenimports=[

        # ── Imports dinámicos (lazyloading en main.py) ───────────────────────
        # PyInstaller no detecta imports dentro de funciones o threads.
        'core.runner',
        'core.chrome_launcher',
        'core.health_checker',
        'core.pyauto_executor',
        'core.downloader',
        'date_handlers.date_resolver',
        'date_handlers.factory',
        'date_handlers.base_handler',
        'date_handlers.input_date',
        'date_handlers.datepicker_js',
        'date_handlers.no_date_filter',
        'tasks.base_task',
        'tasks.mercadopago.task',
        'tasks.galicia.task',

        # ── Macros (módulo puede no existir aún — se ignoran si faltan) ──────
        'macros.models',
        'macros.player',
        'macros.storage',
        'macros.recorder',
        'macros.date_step',
        'sync.macro_sync',

        # ── PyAutoGUI y captura de pantalla ──────────────────────────────────
        'pyautogui',
        'pyscreeze',            # Dependencia interna de pyautogui para screenshots
        'mouseinfo',            # Dependencia interna de pyautogui

        # ── PIL / Pillow ──────────────────────────────────────────────────────
        'PIL',
        'PIL.Image',
        'PIL.ImageGrab',
        'PIL.ImageChops',
        'PIL.ImageFilter',

        # ── pynput — captura de input (MacroRecorder) ────────────────────────
        # Los backends de Windows deben declararse explícitamente.
        'pynput',
        'pynput.mouse',
        'pynput.keyboard',
        'pynput.mouse._win32',
        'pynput.keyboard._win32',
        'pynput._util',
        'pynput._util.win32',

        # ── pygetwindow — focus_window() antes de clicks críticos ────────────
        'pygetwindow',
        'pyrect',               # Dependencia de pygetwindow

        # ── Clipboard ────────────────────────────────────────────────────────
        'pyperclip',

        # ── UI (CustomTkinter + selector de fecha) ───────────────────────────
        'customtkinter',
        'tkcalendar',
        'babel.dates',          # Usado por tkcalendar para localización
        'babel.numbers',

        # ── Datos / Excel ─────────────────────────────────────────────────────
        'pandas',
        'pandas._libs.tslibs.base',
        'pandas._libs.tslibs.offsets',
        'pandas._libs.tslibs.np_datetime',
        'pandas._libs.tslibs.timezones',
        'pandas._libs.tslibs.parsing',
        'openpyxl',
        'openpyxl.styles',
        'openpyxl.styles.differential',
        'openpyxl.utils',
        'openpyxl.worksheet._reader',

        # ── HTTP ─────────────────────────────────────────────────────────────
        'httpx',
        'httpcore',
        'httpcore._sync.http11',
        'httpcore._sync.connection',
        'httpcore._sync.connection_pool',

        # ── Credenciales (keyring usa backend de Windows Credential Manager) ──
        'keyring',
        'keyring.backends',
        'keyring.backends.Windows',
        'keyring.backends.fail',

        # ── Fechas ────────────────────────────────────────────────────────────
        'dateutil',
        'dateutil.relativedelta',
        'dateutil.tz',
        'dateutil.tz.win',
        'dateutil.parser',

        # ── Versiones ─────────────────────────────────────────────────────────
        'semver',

        # ── pywin32 (requerido por pygetwindow y keyring en Windows) ─────────
        'win32api',
        'win32con',
        'win32gui',
        'pywintypes',

        # ── Encoding (para .xlsx y logs en sistemas con locale no-UTF) ───────
        'encodings.utf_8',
        'encodings.ascii',
        'encodings.latin_1',
        'encodings.cp1252',
        'encodings.cp850',
    ],
    excludes=[
        # ── Librerías explícitamente excluidas (ver CLAUDE.md) ───────────────
        'playwright',           # Removido en v1.3 — reemplazado por PyAutoGUI
        'apscheduler',          # Fuera de alcance v1.0
        'selenium',             # Reemplazado por PyAutoGUI
        'pytest',
        'IPython',
        'notebook',
        'matplotlib',
        'scipy',
        'sklearn',
        'tkinter.test',
        'unittest',
    ],
    noarchive=False,
    optimize=0,                 # Sin optimización: preserva docstrings y asserts
)

pyz = PYZ(a.pure)

# ── Ejecutable final (onefile) ───────────────────────────────────────────────
# Al pasar binaries y datas directamente a EXE (sin COLLECT), PyInstaller
# genera un único .exe autoextractor (onefile).
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='RPA_Conciliaciones',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                  # Deshabilitado: evita falsos positivos de antivirus
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,              # Sin consola: app de escritorio para contadores
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,                  # TODO: 'build/rpa_icon.ico' cuando esté disponible
)
