# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec para RPA Conciliaciones v1.0.

Por qué existe: Configura cómo PyInstaller empaqueta la app en un único .exe
distribuible a los contadores. Las carpetas tasks/ y config/ se incluyen como
datos porque se actualizan en runtime desde el servidor.

Uso:
    pyinstaller build/installer.spec --clean --noconfirm
"""

import os
import sys

# Ruta al directorio raíz del proyecto
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(SPEC), '..'))

a = Analysis(
    [os.path.join(PROJECT_ROOT, 'app', 'main.py')],
    pathex=[PROJECT_ROOT],
    binaries=[],
    datas=[
        # Incluir como datos (se actualizan en runtime desde el servidor)
        (os.path.join(PROJECT_ROOT, 'tasks'), 'tasks'),
        (os.path.join(PROJECT_ROOT, 'config'), 'config'),
    ],
    hiddenimports=[
        # Playwright y su API síncrona
        'playwright',
        'playwright.sync_api',
        # UI
        'customtkinter',
        'tkcalendar',
        # Data processing
        'pandas',
        'openpyxl',
        'openpyxl.cell',
        'openpyxl.styles',
        # HTTP y autenticación
        'httpx',
        'httpx._transports',
        'keyring',
        'keyring.backends',
        'keyring.backends.Windows',
        # Utilidades
        'semver',
        'dateutil',
        'dateutil.relativedelta',
        'dateutil.parser',
        # Módulos internos del proyecto
        'config',
        'config.settings',
        'core',
        'core.browser',
        'core.downloader',
        'core.runner',
        'core.reporter',
        'core.health_checker',
        'core.exceptions',
        'date_handlers',
        'date_handlers.date_resolver',
        'date_handlers.base_handler',
        'date_handlers.factory',
        'date_handlers.input_date',
        'date_handlers.datepicker_js',
        'date_handlers.no_date_filter',
        'date_handlers.exceptions',
        'sync',
        'sync.api_client',
        'sync.task_loader',
        'sync.updater',
        'sync.exceptions',
        'sync.mock_data',
        'uploader',
        'uploader.file_uploader',
        'uploader.manual_uploader',
        'tasks',
        'tasks.base_task',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Excluir explícitamente lo que no se usa en v1.0
    excludes=[
        'apscheduler',
        'xlrd',
        'selenium',
        'asyncio',
        'aiohttp',
        'pytest',
        'unittest',
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
    upx=False,  # UPX deshabilitado: puede causar falsos positivos en antivirus
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Sin ventana de consola (app de escritorio)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon=None,  # Reemplazar con ruta a .ico cuando esté disponible
)
