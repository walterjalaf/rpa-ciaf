"""
Constantes para el sistema de DateStep en macros grabadas.

Por qué existe: Define los nombres de los campos de fecha y los formatos
de fecha más comunes en plataformas argentinas. MacroRecorder usa estas
constantes cuando el técnico marca un campo como "fecha de inicio" o
"fecha de fin". MacroPlayer las usa para determinar qué fecha inyectar
y en qué formato.

Uso:
    from macros.date_step import DATE_FROM, DATE_TO, FORMATS_COMUNES
    action = Action(type='date_step', date_field=DATE_FROM,
                    date_format=FORMATS_COMUNES['Argentino'])
"""

# Identificadores de los campos de fecha dinámica
DATE_FROM = "date_from"
DATE_TO = "date_to"

# Formatos de fecha más comunes en plataformas bancarias y de pagos argentinas.
# La clave es el nombre legible que aparece en la UI del grabador.
# El valor es el string de formato compatible con strftime().
FORMATS_COMUNES: dict[str, str] = {
    "ISO": "%Y-%m-%d",           # 2024-01-31  (estándar internacional)
    "Argentino": "%d/%m/%Y",     # 31/01/2024  (Mercado Pago, bancos locales)
    "DDMMYYYY": "%d%m%Y",        # 31012024    (algunos sistemas legacy)
    "YYYYMMDD": "%Y%m%d",        # 20240131    (APIs y exports de BI)
}
