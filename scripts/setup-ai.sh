#!/bin/bash
# setup-ai.sh — Compatibilidad multi-modelo
#
# Crea enlaces simbólicos de CLAUDE.md a los archivos de configuración
# de otros IDEs/modelos, asegurando que la cultura del proyecto sea
# agnóstica a la herramienta.
#
# Uso: bash scripts/setup-ai.sh
# En Windows: ejecutar desde Git Bash o WSL

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
SOURCE_FILE="$PROJECT_ROOT/CLAUDE.md"

if [ ! -f "$SOURCE_FILE" ]; then
    echo "ERROR: No se encontró CLAUDE.md en $PROJECT_ROOT"
    exit 1
fi

echo "Proyecto: RPA Conciliaciones"
echo "Fuente de verdad: CLAUDE.md"
echo ""

# Cursor IDE (.cursorrules)
TARGET_CURSOR="$PROJECT_ROOT/.cursorrules"
if [ -e "$TARGET_CURSOR" ] && [ ! -L "$TARGET_CURSOR" ]; then
    echo "ADVERTENCIA: .cursorrules ya existe y no es un symlink. Se respalda como .cursorrules.bak"
    mv "$TARGET_CURSOR" "$TARGET_CURSOR.bak"
fi
ln -sf "$SOURCE_FILE" "$TARGET_CURSOR"
echo "OK: .cursorrules -> CLAUDE.md"

# Gemini (gemini.md)
TARGET_GEMINI="$PROJECT_ROOT/gemini.md"
if [ -e "$TARGET_GEMINI" ] && [ ! -L "$TARGET_GEMINI" ]; then
    echo "ADVERTENCIA: gemini.md ya existe y no es un symlink. Se respalda como gemini.md.bak"
    mv "$TARGET_GEMINI" "$TARGET_GEMINI.bak"
fi
ln -sf "$SOURCE_FILE" "$TARGET_GEMINI"
echo "OK: gemini.md -> CLAUDE.md"

# Windsurf (.windsurfrules)
TARGET_WINDSURF="$PROJECT_ROOT/.windsurfrules"
if [ -e "$TARGET_WINDSURF" ] && [ ! -L "$TARGET_WINDSURF" ]; then
    echo "ADVERTENCIA: .windsurfrules ya existe y no es un symlink. Se respalda como .windsurfrules.bak"
    mv "$TARGET_WINDSURF" "$TARGET_WINDSURF.bak"
fi
ln -sf "$SOURCE_FILE" "$TARGET_WINDSURF"
echo "OK: .windsurfrules -> CLAUDE.md"

# Copilot (.github/copilot-instructions.md)
COPILOT_DIR="$PROJECT_ROOT/.github"
TARGET_COPILOT="$COPILOT_DIR/copilot-instructions.md"
mkdir -p "$COPILOT_DIR"
if [ -e "$TARGET_COPILOT" ] && [ ! -L "$TARGET_COPILOT" ]; then
    echo "ADVERTENCIA: copilot-instructions.md ya existe y no es un symlink. Se respalda."
    mv "$TARGET_COPILOT" "$TARGET_COPILOT.bak"
fi
ln -sf "$SOURCE_FILE" "$TARGET_COPILOT"
echo "OK: .github/copilot-instructions.md -> CLAUDE.md"

echo ""
echo "Symlinks creados. La cultura del proyecto ahora es agnóstica al IDE/modelo."
echo "Editá únicamente CLAUDE.md — los cambios se reflejan en todos los targets."
