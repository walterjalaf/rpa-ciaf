# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec para RPA Conciliaciones.

Uso (desde rpa_conciliaciones/):
    pyinstaller build/installer.spec --clean --noconfirm

Genera: dist/RPA_Conciliaciones.exe  (onefile, sin consola)
"""

import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Raiz del proyecto = directorio padre de build/
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(SPEC), '..'))

# CustomTkinter empaqueta sus temas y assets en JSON/PNG propios.
# Si no se incluyen, la app arranca con errores de tema.
ctk_datas = collect_data_files('customtkinter')

# pynput tiene backends por plataforma descubiertos en runtime.
pynput_hidden = collect_submodules('pynput')

a = Analysis(
    [os.path.join(PROJECT_ROOT, 'app', 'main.py')],
    pathex=[PROJECT_ROOT],
    binaries=[],
    datas=[
        # Logo CIAF y assets de la UI
        (os.path.join(PROJECT_ROOT, 'app', 'assets'), os.path.join('app', 'assets')),
        # Tareas y schemas (cargados dinamicamente en runtime)
        (os.path.join(PROJECT_ROOT, 'tasks'), 'tasks'),
        # Config (incluido por si se lee como archivo en runtime)
        (os.path.join(PROJECT_ROOT, 'config'), 'config'),
        # Assets de CustomTkinter (temas JSON, imagenes de componentes)
        *ctk_datas,
    ],
    hiddenimports=[
        # ── Automatizacion visual ──────────────────────────────
        'pyautogui',
        'pyautogui._pyautogui_win',
        'pynput',
        'pynput.keyboard',
        'pynput.mouse',
        'pynput._util',
        'pynput._util.win32',
        'pynput.keyboard._win32',
        'pynput.mouse._win32',
        *pynput_hidden,
        'pyperclip',
        'pyperclip.windows',
        'pygetwindow',
        'pygetwindow._pygetwindow_win',
        # Win32 (requerido por pygetwindow y pynput en Windows)
        'win32api',
        'win32con',
        'win32gui',
        'win32process',
        'ctypes',
        'ctypes.wintypes',
        # ── Imagenes (PIL/Pillow) ──────────────────────────────
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',
        'PIL.ImageFont',
        'PIL.ImageGrab',
        'PIL.BmpImagePlugin',
        'PIL.PngImagePlugin',
        'PIL.JpegImagePlugin',
        # ── UI ────────────────────────────────────────────────
        'customtkinter',
        'tkcalendar',
        'tkinter',
        'tkinter.ttk',
        'tkinter.filedialog',
        'tkinter.messagebox',
        # ── Data processing ───────────────────────────────────
        'pandas',
        'pandas.core.arrays.integer',
        'openpyxl',
        'openpyxl.cell',
        'openpyxl.styles',
        'openpyxl.styles.fills',
        'openpyxl.reader.excel',
        'openpyxl.writer.excel',
        # ── HTTP y autenticacion ──────────────────────────────
        'httpx',
        'httpx._transports',
        'httpx._transports.default',
        'httpx._client',
        'keyring',
        'keyring.backends',
        'keyring.backends.Windows',
        'keyring.core',
        # ── Utilidades ────────────────────────────────────────
        'semver',
        'dateutil',
        'dateutil.relativedelta',
        'dateutil.parser',
        'dateutil.tz',
        # ── Modulos internos: config ──────────────────────────
        'config',
        'config.settings',
        'config.credentials',
        # ── Modulos internos: core ────────────────────────────
        'core',
        'core.chrome_launcher',
        'core.pyauto_executor',
        'core.downloader',
        'core.runner',
        'core.reporter',
        'core.health_checker',
        'core.exceptions',
        # ── Modulos internos: tasks ───────────────────────────
        'tasks',
        'tasks.base_task',
        'tasks.macro_task',
        # ── Modulos internos: date_handlers ───────────────────
        'date_handlers',
        'date_handlers.date_resolver',
        'date_handlers.base_handler',
        'date_handlers.factory',
        'date_handlers.input_date',
        'date_handlers.datepicker_js',
        'date_handlers.no_date_filter',
        'date_handlers.exceptions',
        # ── Modulos internos: macros ──────────────────────────
        'macros',
        'macros.models',
        'macros.recorder',
        'macros.player',
        'macros.storage',
        'macros.date_step',
        'macros.exceptions',
        'macros.task_plan_store',
        # ── Modulos internos: sync ────────────────────────────
        'sync',
        'sync.api_client',
        'sync.task_loader',
        'sync.updater',
        'sync.macro_sync',
        'sync.mock_data',
        'sync.exceptions',
        # ── Modulos internos: uploader ────────────────────────
        'uploader',
        'uploader.file_uploader',
        'uploader.manual_uploader',
        'uploader.upload_queue',
        # ── Modulos internos: app/ui ──────────────────────────
        'app',
        'app.ui',
        'app.ui.dashboard',
        'app.ui.task_status',
        'app.ui.session_panel',
        'app.ui.date_selector',
        'app.ui.manual_upload',
        'app.ui.alert_modal',
        'app.ui.macro_recorder_panel',
        'app.ui.macro_list_panel',
        'app.ui.task_manager_panel',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Playwright removido en v1.3
        'playwright',
        'playwright.sync_api',
        # Otras dependencias no usadas
        'selenium',
        'apscheduler',
        'xlrd',
        'asyncio',
        'aiohttp',
        'pytest',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

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
    upx=False,          # UPX deshabilitado: puede generar falsos positivos en antivirus
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,      # Sin ventana de consola (app de escritorio para el contador)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon='build/icon.ico',  # Descomentar cuando haya un .ico disponible
)
