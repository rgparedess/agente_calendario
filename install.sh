#!/bin/bash
# Script de instalación manual para calendario_ics y agente_calendario
# Copia los archivos .py a ~/.local/bin y crea wrappers ejecutables.

set -e

# Directorio de instalación (para usuario, sin sudo)
INSTALL_DIR="$HOME/.local/bin"

# Crear el directorio si no existe
mkdir -p "$INSTALL_DIR"

# Función para instalar un script
install_script() {
    local src="$1"
    local name="$2"
    local dest="$INSTALL_DIR/$name"
    
    echo "Instalando $name en $dest..."
    # Copiar el archivo .py
    cp "$src" "$dest"
    # Hacerlo ejecutable
    chmod +x "$dest"
}

# Instalar agente_calendario (si existe)
if [ -f "agente_calendario.py" ]; then
    install_script "agente_calendario.py" "calendario-agent"
else
    echo "Advertencia: agente_calendario.py no encontrado en el directorio actual."
fi

# Verificar que ~/.local/bin está en el PATH
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo "⚠️  ~/.local/bin no está en tu PATH."
    echo "   Agrégalo con: export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo "   O añade la línea a tu ~/.bashrc"
fi

echo "✅ Instalación manual completada."
echo "Ahora puedes ejecutar 'calendario-agent'."