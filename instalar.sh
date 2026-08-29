#!/usr/bin/env bash
# Deja Iris en el menú del escritorio y el comando `iris` en la terminal.
# Sin sudo: todo va dentro de ~/.local, que es donde el escritorio busca.
#
# Usa los mismos archivos que el paquete RPM (iris.desktop, iris.svg) para
# que no haya dos versiones de lo mismo que se despisten con el tiempo.
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN="$HOME/.local/bin"
APPS="$HOME/.local/share/applications"
ICONOS="$HOME/.local/share/icons/hicolor"

quitar() {
    rm -f "$BIN/iris" "$APPS/iris.desktop" "$ICONOS/scalable/apps/iris.svg"
    update-desktop-database "$APPS" 2>/dev/null || true
    gtk-update-icon-cache -f -t "$ICONOS" 2>/dev/null || true
    echo "Iris desinstalada. Tus fotos y vídeos siguen donde estaban."
    exit 0
}

[[ "${1:-}" == "--quitar" ]] && quitar

command -v python3 >/dev/null || { echo "Falta python3"; exit 1; }
python3 -c "import PyQt6.QtWidgets" 2>/dev/null || {
    echo "Falta PyQt6. En Fedora: sudo dnf install python3-pyqt6"
    exit 1
}
command -v ffmpeg >/dev/null || echo "Aviso: sin ffmpeg no vas a poder grabar vídeo."

mkdir -p "$BIN" "$APPS" "$ICONOS/scalable/apps"

cat > "$BIN/iris" <<EOF
#!/usr/bin/env bash
exec python3 "$RAIZ/iris.py" "\$@"
EOF
chmod +x "$BIN/iris" "$RAIZ/iris.py"

# Al .desktop solo hay que ponerle la ruta real del lanzador.
sed "s|^Exec=iris$|Exec=$BIN/iris|" "$RAIZ/iris.desktop" > "$APPS/iris.desktop"
install -m 0644 "$RAIZ/iris.svg" "$ICONOS/scalable/apps/iris.svg"

update-desktop-database "$APPS" 2>/dev/null || true
gtk-update-icon-cache -f -t "$ICONOS" 2>/dev/null || true

echo "Listo. Buscá 'Iris' o 'webcam' en el menú, o escribí 'iris' en la terminal."
if ! echo "$PATH" | grep -q "$BIN"; then
    echo "Ojo: $BIN no está en tu PATH, así que el comando 'iris' no va a andar."
fi
