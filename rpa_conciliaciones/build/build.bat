@echo off
chcp 65001 >nul
echo ==========================================
echo  Compilando RPA Conciliaciones
echo ==========================================
echo.

:: Ir al directorio raiz del proyecto (padre de build/)
cd /d "%~dp0.."

:: Ruta al Python instalado (ajustar si cambia la version/ubicacion)
set PYTHON=C:\Users\Administrador\AppData\Local\Programs\Python\Python312\python.exe

echo [1/3] Verificando Python...
"%PYTHON%" --version
if errorlevel 1 (
    echo ERROR: Python no encontrado en %PYTHON%
    echo Ajusta la variable PYTHON en este script.
    pause
    exit /b 1
)
echo.

echo [2/3] Instalando dependencias...
"%PYTHON%" -m pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo ERROR: No se pudieron instalar las dependencias.
    pause
    exit /b 1
)
echo OK.
echo.

echo [3/3] Compilando ejecutable (puede tardar 2-5 minutos)...
"%PYTHON%" -m PyInstaller build\installer.spec --clean --noconfirm
if errorlevel 1 (
    echo.
    echo ERROR: La compilacion fallo. Leer los mensajes de arriba para detalles.
    pause
    exit /b 1
)

echo.
echo ==========================================
echo  Listo!
echo  Ejecutable: dist\RPA_Conciliaciones.exe
echo ==========================================
echo.
if exist dist\RPA_Conciliaciones.exe (
    echo Tamano del archivo:
    dir dist\RPA_Conciliaciones.exe | findstr "RPA_Conciliaciones"
)
echo.
pause
