#!/usr/bin/env bash
# Deja Iris en el menú del escritorio y el comando `iris` en la terminal.
# Sin sudo: todo va dentro de ~/.local, que es donde el escritorio busca.
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN="$HOME/.local/bin"
APPS="$HOME/.local/share/applications"
ICONOS="$HOME/.local/share/icons/hicolor"
LADOS=(16 24 32 48 64 128 256)

quitar() {
    rm -f "$BIN/iris" "$APPS/iris.desktop"
    for lado in "${LADOS[@]}"; do
        rm -f "$ICONOS/${lado}x${lado}/apps/iris.png"
    done
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

mkdir -p "$BIN" "$APPS"

cat > "$BIN/iris" <<EOF
#!/usr/bin/env bash
exec python3 "$RAIZ/iris.py" "\$@"
EOF
chmod +x "$BIN/iris" "$RAIZ/iris.py"

cat > "$APPS/iris.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Iris
GenericName=Cámara
Comment=Verte, sacarte fotos y grabar vídeo con la webcam
Exec=$BIN/iris
Icon=iris
Terminal=false
Categories=AudioVideo;Video;
Keywords=camara;cámara;webcam;foto;fotos;video;selfie;iris;
StartupNotify=true
EOF

# El icono se dibuja en vez de venir como archivo: así no hay PNG binarios
# en el repo y sale nítido en cualquier tamaño que pida el escritorio.
QT_QPA_PLATFORM=offscreen python3 - "$RAIZ" "$ICONOS" "${LADOS[@]}" <<'EOF'
import os, sys
sys.path.insert(0, sys.argv[1])
from PyQt6.QtWidgets import QApplication
import iconos

app = QApplication([])
icono = iconos.icono_app()
base = sys.argv[2]
for lado in (int(v) for v in sys.argv[3:]):
    destino = f"{base}/{lado}x{lado}/apps"
    os.makedirs(destino, exist_ok=True)
    icono.pixmap(lado, lado).save(f"{destino}/iris.png")
EOF

update-desktop-database "$APPS" 2>/dev/null || true
gtk-update-icon-cache -f -t "$ICONOS" 2>/dev/null || true

echo "Listo. Buscá 'Iris' o 'webcam' en el menú, o escribí 'iris' en la terminal."
if ! echo "$PATH" | grep -q "$BIN"; then
    echo "Ojo: $BIN no está en tu PATH, así que el comando 'iris' no va a andar."
fi
