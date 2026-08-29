# Iris

*[Read this in English](README.md)*

**Una cámara para Linux que no te miente sobre lo que puede dar tu webcam.**

Ventana negra, un ojo grande que parpadea cuando saca la foto, y ningún ajuste
escondido. Fotos y video con el micrófono que vos elijas.

![el botón es un ojo: parpadea al disparar y se abre del todo al grabar](docs/ojo.png)

## Por qué existe

Porque las tres alternativas fallaban, cada una en algo distinto:

- **Kamoso** ya no se mantiene.
- **Webcamoid** agarra la última fila de la lista de capacidades de la cámara,
  que suele ser lo peor posible: vídeo **sin comprimir a 1080p**. En una webcam
  USB 2.0 eso son **5 fps**, y encima su pipeline mete retraso visible.
- **Snapshot** elige bien el formato, pero pide 1080p interpolado, aplica rango
  de color limitado (16-235) sobre un flujo que viene en rango completo (la
  imagen sale lavada) y espeja la vista sin dejar apagarlo. No tiene **ni un
  solo ajuste**: son once claves de configuración y ninguna es resolución,
  formato ni espejo.

Iris pide **MJPG siempre**, te deja elegir la resolución, y el espejo y el giro
son interruptores que se acuerdan de cómo los dejaste.

## La verdad sobre los fps

Casi todas las webcams USB baratas declaran 30 fps y no los dan. Iris trae un
medidor para que lo compruebes vos:

```bash
python3 v4l2cam.py            # lista los modos y mide los fps reales
```

En la cámara con la que se escribió esto (una REDRAGON Live Camera), la
diferencia entre elegir bien y elegir mal es de **tres veces**:

| Formato | 1920x1080 | 1280x720 | 640x480 |
|---|---|---|---|
| MJPG (comprimido) | 30 declarados, **15 reales** | 30 declarados, **15 reales** | 30 declarados, **15 reales** |
| YUYV (sin comprimir) | **5** | 10 | 30 |

Vídeo sin comprimir a 1080p son unos 60 MB por segundo, y un puerto USB 2.0 da
como un tercio de eso. La cámara no tiene de otra que bajar a cinco cuadros.
Por eso Iris ni siquiera te ofrece el formato crudo: solo invita a elegir mal.

Y la barra de estado te dice los fps que estás recibiendo **de verdad**, no los
que la cámara promete.

## Qué hace

- **Fotos**: con el espejo y el giro apagados, se guarda el **JPEG exacto que
  manda la cámara, sin recomprimir**. Ni un bit de pérdida. Voltear o girar sí
  obliga a tocar los píxeles, y ahí recomprime (la calidad se ajusta).
- **Vídeo**: H.264 con audio AAC, eligiendo cuál de tus micrófonos usar.
- **Espejo**: verte con los lados cambiados, o como te ve la otra persona.
- **Giro**: de a un cuarto de vuelta, para cámaras montadas de costado.
- **Se recupera sola**: si Discord o el navegador tienen la cámara, te dice
  **quién** la tiene por su nombre y se abre en cuanto la suelten.
- **Panel avanzado** (`Ctrl+Shift+A`): brillo, contraste, saturación, ganancia
  y exposición hablando directo con los controles de la cámara, más calidad e
  idioma. Está escondido a propósito. Los controles que tu cámara no soporte
  salen en gris en vez de desaparecer, para que se vea que el que no puede es
  el aparato.
- **Una sola ventana**: una webcam admite un solo programa a la vez, así que
  abrirla dos veces levanta la que ya está en lugar de dejarte una ventana
  negra inútil.
- **Varias cámaras**: las detecta y las lista por su nombre. Una webcam suele
  exponer varios `/dev/videoN` y la mayoría son de metadatos, no de imagen;
  solo se ofrecen las que de verdad capturan MJPG.

Atajos: `Espacio` dispara, `R` gira, `Ctrl+O` abre la carpeta.

Las fotos van a `~/Imágenes/Iris` y los vídeos a `~/Vídeos/Iris`.

## Idiomas

Español e inglés, según el idioma del sistema y cambiable desde el panel
avanzado. Añadir uno es copiar un bloque de `idiomas.py` y traducirlo: sin
ficheros `.ts` ni `lrelease`.

## Cómo funciona por dentro

Sin OpenCV y sin GStreamer. `v4l2cam.py` le habla al kernel directamente por
`ioctl` y entrega los cuadros como **JPEG crudo**, que es como ya vienen de una
webcam en MJPG. Qt sabe decodificar eso solo, así que:

- no hay una capa de conversión de color que lave la imagen,
- la foto se puede guardar sin recomprimir,
- y el vídeo se arma pasándole esos mismos JPEG a `ffmpeg` por una tubería.

La latencia se controla vaciando la cola de cuadros en cada lectura y usando el
más nuevo. Es la diferencia entre verte en vivo y verte tarde.

Los números de `ioctl` no están escritos a mano: se calculan con la misma
fórmula que usa el kernel, a partir del tamaño real de cada estructura. Por eso
las estructuras llevan uniones de verdad en vez de relleno a ojo: así ctypes
calcula la alineación sola y los números salen bien tanto en 64 bits como en 32
o en ARM, donde un puntero mide distinto y las estructuras cambian de tamaño.

## Requisitos

- Python 3 con **PyQt6**
- **ffmpeg** (solo para grabar vídeo)
- Un kernel con V4L2, o sea cualquier Linux

En Fedora:

```bash
sudo dnf install python3-pyqt6 ffmpeg
```

## Instalación

```bash
git clone https://github.com/TVTvirus/iris.git ~/Documentos/iris
cd ~/Documentos/iris && ./instalar.sh
```

Eso deja el lanzador en el menú del escritorio y el comando `iris` en la
terminal. Para sacarlo, `./instalar.sh --quitar`.

## Estado

Funciona y se usa a diario. Lo que falta:

- Nunca se probó fuera de Linux x86-64 con una webcam UVC.
- El código y los comentarios están en español; solo la interfaz es bilingüe.

## Licencia

MIT.
