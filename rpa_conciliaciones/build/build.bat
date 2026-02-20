@echo off
echo ==========================================
echo  Compilando RPA Conciliaciones v1.0
echo ==========================================
echo.

echo [1/4] Verificando Python...
python --version
if errorlevel 1 (
    echo ERROR: Python no encontrado. Instalar Python 3.11+
    pause
    exit /b 1
)
echo.

echo [2/4] Instalando dependencias...
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: No se pudieron instalar las dependencias.
    pause
    exit /b 1
)
echo.

echo [3/4] Instalando Chromium para Playwright...
playwright install chromium
if errorlevel 1 (
    echo ERROR: No se pudo instalar Chromium.
    pause
    exit /b 1
)
echo.

echo [4/4] Compilando ejecutable...
pyinstaller build/installer.spec --clean --noconfirm
if errorlevel 1 (
    echo ERROR: La compilacion fallo.
    pause
    exit /b 1
)
echo.

echo ==========================================
echo  Listo. Ejecutable en dist\RPA_Conciliaciones.exe
echo ==========================================
echo.
echo Tamano del ejecutable:
dir dist\RPA_Conciliaciones.exe | findstr "RPA_Conciliaciones"
echo.
pause
