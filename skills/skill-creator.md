# Skill: Skill Creator (Meta-Skill)

| Campo | Valor |
|---|---|
| **Name** | Skill Creator |
| **Description** | Meta-skill que define el proceso para crear nuevas skills cuando el proyecto crece. Garantiza formato consistente y que el índice en CLAUDE.md se mantenga actualizado. |
| **Trigger** | El prompt contiene: "nueva skill", "documentar patrón", "crear skill" |
| **Scope** | `skills/` y la sección 4 de `CLAUDE.md` |

---

## Proceso para crear una nueva skill

### Paso 1 — Validar que la skill es necesaria

Una skill nueva se justifica cuando:
- El patrón se repite en 2+ módulos o tareas
- Tiene trampas no obvias que costaron tiempo resolver
- No está cubierto por una skill existente
- No es un detalle de implementación de un solo archivo

### Paso 2 — Proponer antes de crear

Antes de crear el archivo, presentar al usuario:

```
Sugiero documentar este patrón como una skill nueva:
Nombre: skills/[nombre-descriptivo].md
Trigger: [cuándo debería leerse esta skill]
Contenido: [resumen en 2-3 líneas del patrón y por qué importa]
¿Procedo?
```

### Paso 3 — Crear el archivo con formato estándar

Toda skill debe tener esta estructura:

```markdown
# Skill: [Nombre]

| Campo | Valor |
|---|---|
| **Name** | [Nombre] |
| **Description** | [1-2 oraciones: qué cubre y por qué existe] |
| **Trigger** | [Palabras clave que activan la lectura de esta skill] |
| **Scope** | [Archivos/carpetas que esta skill afecta] |

---

## Reglas obligatorias

### 1. [Regla principal]
[Explicación + ejemplo de código BIEN/MAL]

### 2. [Regla secundaria]
[...]

---

## Anti-patrones
[Lista de errores comunes que esta skill previene]
```

### Paso 4 — Actualizar el índice en CLAUDE.md

Agregar una fila a la tabla de Skills en la sección 4 del CLAUDE.md:

```markdown
| [Nombre] | `skills/[archivo].md` | "[trigger words]" | [Dominio] |
```

### Paso 5 — Verificar consistencia

- El nombre del archivo es `snake-case` con extensión `.md`
- El trigger no se solapa con triggers de skills existentes
- El scope no contradice el mapa de dependencias del CLAUDE.md sección 6

---

## Anti-patrones

- No crear skills para patrones de un solo uso
- No duplicar contenido que ya está en el PRD o CLAUDE.md
- No crear skills genéricas ("buenas prácticas de Python") — solo patrones específicos del proyecto
- No crear skills vacías "por si acaso" — crearlas cuando el trigger se active por primera vez
