#!/bin/bash
# Instalador para calendario-agent (ejecutable empaquetado con PyInstaller)

set -e

INSTALL_DIR="$HOME/.local/bin"
DESKTOP_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons"
mkdir -p "$INSTALL_DIR"

if [ -f "./calendario-agent" ]; then
    cp "./calendario-agent" "$INSTALL_DIR/"
    chmod +x "$INSTALL_DIR/calendario-agent"
    echo "[INFO] Ejecutable instalado en $INSTALL_DIR/calendario-agent"
else
    echo "[ERROR] No se encuentra 'calendario-agent'."
    exit 1
fi

# Copiar icono a la carpeta estándar
mkdir -p "$HOME/.local/share/icons"
if [ -f "./logo/logo.png" ]; then
    cp "./logo/logo.png" "$HOME/.local/share/icons/agente_calendario.png"
fi

if [ -f "$ICON_DIR/agente_calendario.png" ]; then
    ICON_NAME="agente_calendario"
else
    ICON_NAME="calendar"
fi

# Crear archivo .desktop (usar la ruta absoluta del ejecutable)
cat > "$DESKTOP_DIR/agente_calendario.desktop" <<EOF
[Desktop Entry]
Name=Agente Calendario
Comment=Agente de IA conversacional para gestionar calendario con LLM
Exec=$INSTALL_DIR/calendario-agent
Icon=$ICON_NAME
Terminal=true
Type=Application
Categories=Utility;Office;
EOF

chmod +x "$DESKTOP_DIR/agente_calendario.desktop"
echo "[INFO] Lanzador .desktop creado en $DESKTOP_DIR/agente_calendario.desktop"

# Agregar al PATH si no está
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo "[!]  $HOME/.local/bin no está en tu PATH."
    echo "[?] ¿Deseas agregarlo permanentemente? (s/N)"
    read -r respuesta
    if [[ "$respuesta" == "s" || "$respuesta" == "S" ]]; then
        if [ -f "$HOME/.bashrc" ]; then
            SHELL_RC="$HOME/.bashrc"
        elif [ -f "$HOME/.zshrc" ]; then
            SHELL_RC="$HOME/.zshrc"
        else
            SHELL_RC="$HOME/.profile"
        fi
        echo "export PATH=\"\$HOME/.local/bin:\$PATH\"" >> "$SHELL_RC"
        echo "[INFO] PATH actualizado en $SHELL_RC. Reinicia la terminal o ejecuta 'source $SHELL_RC'."
    else
        echo "[*]  Agrégalo manualmente con: export PATH=\"\$HOME/.local/bin:\$PATH\""
    fi
else
    echo "[INFO] $HOME/.local/bin ya está en el PATH."
fi

echo ""
echo "[INFO] Instalación completada."
echo "   Ahora puedes ejecutar: calendario-agent --host 127.0.0.1 --port 8082"