@echo off
setlocal enabledelayedexpansion

:: ── Navegar a la raíz del proyecto (un nivel arriba de build\) ──────────────
cd /d "%~dp0.."

echo.
echo ==========================================
echo  Compilando RPA Conciliaciones v1.0
echo ==========================================
echo.

:: ── Configuración de Python ──────────────────────────────────────────────────
:: Si 'python' no está en PATH (instalación sin agregar al PATH del sistema),
:: descomentar la siguiente línea y ajustar la ruta:
::
::   set PYTHON_EXE=C:\Users\Administrador\AppData\Local\Programs\Python\Python312\python.exe
::
:: Por defecto se usa 'python' del PATH del sistema.
if "%PYTHON_EXE%"=="" set PYTHON_EXE=python

:: ── Verificar que Python esté disponible ─────────────────────────────────────
%PYTHON_EXE% --version > NUL 2>&1
if errorlevel 1 (
    echo [ERROR] Python no encontrado en PATH.
    echo         Edita build\build.bat y configura la variable PYTHON_EXE con
    echo         la ruta completa a python.exe. Por ejemplo:
    echo.
    echo           set PYTHON_EXE=C:\Users\Administrador\AppData\Local\Programs\Python\Python312\python.exe
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%v in ('%PYTHON_EXE% --version 2^>^&1') do (
    echo Python encontrado: %%v
)
echo.

:: ── Instalar dependencias ────────────────────────────────────────────────────
echo Instalando dependencias desde rpa_conciliaciones\requirements.txt...
%PYTHON_EXE% -m pip install -r rpa_conciliaciones\requirements.txt

if errorlevel 1 (
    echo.
    echo [ERROR] Fallo al instalar dependencias.
    echo         Verifica tu conexion a internet y que pip este disponible.
    pause
    exit /b 1
)
echo.

:: ── Compilar ejecutable ───────────────────────────────────────────────────────
echo Compilando ejecutable (esto puede tardar varios minutos)...
echo.
%PYTHON_EXE% -m PyInstaller build\installer.spec --clean --noconfirm

if errorlevel 1 (
    echo.
    echo [ERROR] Fallo al compilar el ejecutable.
    echo         Revisa los mensajes de error arriba para mas detalle.
    echo         Log completo disponible en build\build.log si usaste redireccion.
    pause
    exit /b 1
)

echo.
echo ==========================================
echo  Listo. Ejecutable generado en:
echo.
echo    dist\RPA_Conciliaciones.exe
echo.
echo  Distribuir solo ese archivo .exe
echo  (no requiere Python instalado).
echo ==========================================
echo.
pause
