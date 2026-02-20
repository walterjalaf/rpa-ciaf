# RPA Conciliaciones

App de escritorio Windows para automatización de descarga de reportes financieros y envío al servidor de conciliación.

## Requisitos

- **Python 3.11+**
- **Google Chrome instalado** (obligatorio, sin alternativas)
- Windows 10/11

## Decisiones de arquitectura

1. **Chrome es obligatorio.** La app usa el perfil real de Chrome del usuario para reutilizar sesiones bancarias activas.
2. **El ETL de columnas es del servidor, no de la app.** Los archivos se suben tal cual al servidor Laravel que hace la conciliación.
3. **No hay scheduler en v1.0** por riesgo de sesiones expiradas en banca argentina (timeout de 15-30 min por inactividad).

## Instalación

```bash
pip install -r requirements.txt
playwright install chromium
```

## Desarrollo

```bash
python app/main.py
```

## Estructura del proyecto

```
rpa_conciliaciones/
├── app/              # UI de escritorio (CustomTkinter)
│   ├── main.py       # Entry point
│   └── ui/           # Componentes visuales
├── core/             # Motor de ejecución (browser, runner, downloader)
├── tasks/            # Una subcarpeta por plataforma (task.py + schema.json)
│   ├── base_task.py  # Clase abstracta
│   ├── mercadopago/  # Plataforma piloto
│   └── galicia/      # Plataforma piloto
├── date_handlers/    # Resolución de fechas y handlers de selector
├── uploader/         # Envío de archivos al servidor
├── sync/             # Comunicación HTTP (api_client, task_loader, updater)
├── config/           # Constantes y credenciales
└── build/            # Configuración de PyInstaller (.exe)
```
