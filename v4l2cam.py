"""Captura de webcam por V4L2, sin dependencias externas.

Le habla al kernel directamente por ioctl y entrega los cuadros como JPEG
crudo, tal cual sale de la camara. Qt sabe decodificar eso solo, asi que no
hace falta OpenCV ni GStreamer, y la foto se puede guardar sin recomprimir.

Por que MJPG y no crudo: una webcam USB 2.0 no tiene ancho de banda para
video sin comprimir. La REDRAGON de esta maquina da 5 fps en YUYV a 1080p
y 30 declarados (15 reales) en MJPG a cualquier resolucion.
"""

import ctypes
import fcntl
import mmap
import os
import select

# ---------------------------------------------------------------- ioctls
# Los numeros salen de _IOWR('V', nr, struct): direccion<<30 | tam<<16 | 'V'<<8 | nr
VIDIOC_S_FMT = 0xC0D05605
VIDIOC_REQBUFS = 0xC0145608
VIDIOC_QUERYBUF = 0xC0585609
VIDIOC_QBUF = 0xC058560F
VIDIOC_DQBUF = 0xC0585611
VIDIOC_STREAMON = 0x40045612
VIDIOC_STREAMOFF = 0x40045613
VIDIOC_ENUM_FRAMESIZES = 0xC02C564A
VIDIOC_ENUM_FRAMEINTERVALS = 0xC034564B
VIDIOC_G_CTRL = 0xC008561B
VIDIOC_S_CTRL = 0xC008561C

BUF_TYPE_VIDEO_CAPTURE = 1
MEMORY_MMAP = 1
FRMIVAL_TYPE_DISCRETE = 1

CONTROLES = {
    "brillo": 0x00980900,
    "contraste": 0x00980901,
    "saturacion": 0x00980902,
    "ganancia": 0x00980913,
    "exposicion": 0x009A0902,
    "exposicion_auto": 0x009A0901,
    "prioridad_exposicion": 0x009A0903,
}


def fourcc(s):
    return sum(ord(c) << (8 * i) for i, c in enumerate(s))


MJPG = fourcc("MJPG")


# --------------------------------------------------------------- structs
class Fract(ctypes.Structure):
    _fields_ = [("num", ctypes.c_uint32), ("den", ctypes.c_uint32)]


class Formato(ctypes.Structure):
    # v4l2_format: el union arranca en el byte 8 porque contiene un puntero
    # (v4l2_window), que en 64 bits obliga a alineacion de 8.
    _fields_ = [
        ("type", ctypes.c_uint32),
        ("_relleno", ctypes.c_uint32),
        ("width", ctypes.c_uint32),
        ("height", ctypes.c_uint32),
        ("pixelformat", ctypes.c_uint32),
        ("field", ctypes.c_uint32),
        ("bytesperline", ctypes.c_uint32),
        ("sizeimage", ctypes.c_uint32),
        ("colorspace", ctypes.c_uint32),
        ("priv", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
        ("enc", ctypes.c_uint32),
        ("quantization", ctypes.c_uint32),
        ("xfer_func", ctypes.c_uint32),
        ("_resto", ctypes.c_uint8 * 152),
    ]


class PedidoBuffers(ctypes.Structure):
    _fields_ = [
        ("count", ctypes.c_uint32),
        ("type", ctypes.c_uint32),
        ("memory", ctypes.c_uint32),
        ("capabilities", ctypes.c_uint32),
        ("flags", ctypes.c_uint8),
        ("_reservado", ctypes.c_uint8 * 3),
    ]


class Buffer(ctypes.Structure):
    _fields_ = [
        ("index", ctypes.c_uint32),
        ("type", ctypes.c_uint32),
        ("bytesused", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
        ("field", ctypes.c_uint32),
        ("_pad", ctypes.c_uint32),
        ("tv_sec", ctypes.c_int64),
        ("tv_usec", ctypes.c_int64),
        ("timecode", ctypes.c_uint8 * 16),
        ("sequence", ctypes.c_uint32),
        ("memory", ctypes.c_uint32),
        ("offset", ctypes.c_uint32),
        ("_offset_alto", ctypes.c_uint32),
        ("length", ctypes.c_uint32),
        ("reserved2", ctypes.c_uint32),
        ("request_fd", ctypes.c_int32),
        ("_cola", ctypes.c_uint32),
    ]


class TamanoCuadro(ctypes.Structure):
    _fields_ = [
        ("index", ctypes.c_uint32),
        ("pixel_format", ctypes.c_uint32),
        ("type", ctypes.c_uint32),
        ("width", ctypes.c_uint32),
        ("height", ctypes.c_uint32),
        ("_resto", ctypes.c_uint32 * 6),
    ]


class IntervaloCuadro(ctypes.Structure):
    _fields_ = [
        ("index", ctypes.c_uint32),
        ("pixel_format", ctypes.c_uint32),
        ("width", ctypes.c_uint32),
        ("height", ctypes.c_uint32),
        ("type", ctypes.c_uint32),
        ("discrete", Fract),
        ("_resto", ctypes.c_uint32 * 6),
    ]


class Control(ctypes.Structure):
    _fields_ = [("id", ctypes.c_uint32), ("value", ctypes.c_int32)]


# ----------------------------------------------------------------- error
class CamaraOcupada(Exception):
    """Otro programa tiene la camara abierta. Solo cabe uno a la vez."""


class CamaraNoSirve(Exception):
    """La camara no existe, o no da MJPG."""


# ----------------------------------------------------------------- api
def modos(dispositivo="/dev/video0"):
    """Los modos MJPG del aparato, del mas grande al mas chico.

    Devuelve [(ancho, alto, fps), ...]. Solo MJPG: el crudo no sirve para
    nada util en USB 2.0 y ofrecerlo solo invita a elegir mal.
    """
    try:
        fd = os.open(dispositivo, os.O_RDWR)
    except OSError as e:
        raise CamaraNoSirve(str(e)) from e
    try:
        salida = []
        for i in range(64):
            t = TamanoCuadro(index=i, pixel_format=MJPG)
            try:
                fcntl.ioctl(fd, VIDIOC_ENUM_FRAMESIZES, t)
            except OSError:
                break
            if t.type != 1:  # solo tamanos discretos
                continue
            salida.append((t.width, t.height, _mejor_fps(fd, t.width, t.height)))
        salida.sort(key=lambda m: m[0] * m[1], reverse=True)
        return salida
    finally:
        os.close(fd)


def _mejor_fps(fd, ancho, alto):
    mejor = 0
    for i in range(16):
        iv = IntervaloCuadro(index=i, pixel_format=MJPG, width=ancho, height=alto)
        try:
            fcntl.ioctl(fd, VIDIOC_ENUM_FRAMEINTERVALS, iv)
        except OSError:
            break
        if iv.type != FRMIVAL_TYPE_DISCRETE or not iv.discrete.num:
            break
        mejor = max(mejor, round(iv.discrete.den / iv.discrete.num))
    return mejor


# Un "python3" pelado no le dice nada a nadie. Traducimos los sospechosos
# habituales al nombre con el que la gente los conoce.
_APODOS = (
    ("iris.py", "otra ventana de Iris"),
    ("Discord", "Discord"),
    ("webcamoid", "Webcamoid"),
    ("snapshot", "Snapshot"),
    ("obs", "OBS"),
    ("ffplay", "el Espejo"),
    ("cheese", "Cheese"),
    ("firefox", "Firefox"),
    ("chrome", "Chrome"),
    ("chromium", "Chromium"),
    ("zoom", "Zoom"),
)


def quien_la_tiene():
    """El nombre del programa que tiene la camara abierta, o None.

    Sirve para dar un mensaje util en vez de un 'dispositivo ocupado' pelado.
    Devuelve (nombre, es_nuestro) para poder distinguir el caso de abrir la
    app dos veces, que se arregla solo, de otro programa, que no.
    """
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            fds = os.listdir(f"/proc/{pid}/fd")
        except OSError:
            continue
        for fd in fds:
            try:
                if not os.readlink(f"/proc/{pid}/fd/{fd}").startswith("/dev/video"):
                    continue
                with open(f"/proc/{pid}/cmdline", "rb") as f:
                    linea = f.read().replace(b"\0", b" ").decode(errors="replace")
            except OSError:
                continue
            for pista, apodo in _APODOS:
                if pista.lower() in linea.lower():
                    return apodo, pista == "camara.py"
            with open(f"/proc/{pid}/comm") as f:
                return f.read().strip(), False
    return None, False


class Camara:
    """Una camara abierta y transmitiendo. Entrega JPEG crudo."""

    def __init__(self, dispositivo="/dev/video0", ancho=1280, alto=720, buffers=3):
        self.dispositivo = dispositivo
        self.ancho = ancho
        self.alto = alto
        self._fd = None
        self._mapas = []
        self._transmitiendo = False
        self._buffers = buffers

    def abrir(self):
        try:
            self._fd = os.open(self.dispositivo, os.O_RDWR | os.O_NONBLOCK)
        except OSError as e:
            if e.errno in (16, 11):  # EBUSY, EAGAIN
                raise CamaraOcupada(quien_la_tiene()[0] or "otro programa") from e
            raise CamaraNoSirve(str(e)) from e

        fmt = Formato(
            type=BUF_TYPE_VIDEO_CAPTURE,
            width=self.ancho,
            height=self.alto,
            pixelformat=MJPG,
            field=1,  # NONE
        )
        try:
            fcntl.ioctl(self._fd, VIDIOC_S_FMT, fmt)
        except OSError as e:
            self.cerrar()
            if e.errno == 16:
                raise CamaraOcupada(quien_la_tiene()[0] or "otro programa") from e
            raise CamaraNoSirve(f"no acepta MJPG: {e}") from e

        # El driver puede corregir lo pedido: nos quedamos con lo que dio.
        self.ancho, self.alto = fmt.width, fmt.height
        if fmt.pixelformat != MJPG:
            self.cerrar()
            raise CamaraNoSirve("la camara no da MJPG")

        pedido = PedidoBuffers(
            count=self._buffers, type=BUF_TYPE_VIDEO_CAPTURE, memory=MEMORY_MMAP
        )
        try:
            fcntl.ioctl(self._fd, VIDIOC_REQBUFS, pedido)
        except OSError as e:
            self.cerrar()
            raise CamaraOcupada(quien_la_tiene()[0] or "otro programa") from e

        for i in range(pedido.count):
            buf = Buffer(index=i, type=BUF_TYPE_VIDEO_CAPTURE, memory=MEMORY_MMAP)
            fcntl.ioctl(self._fd, VIDIOC_QUERYBUF, buf)
            self._mapas.append(
                mmap.mmap(
                    self._fd,
                    buf.length,
                    flags=mmap.MAP_SHARED,
                    prot=mmap.PROT_READ,
                    offset=buf.offset,
                )
            )
            fcntl.ioctl(self._fd, VIDIOC_QBUF, buf)

        tipo = ctypes.c_uint32(BUF_TYPE_VIDEO_CAPTURE)
        fcntl.ioctl(self._fd, VIDIOC_STREAMON, tipo)
        self._transmitiendo = True
        return self

    def cuadro(self, espera=1.0):
        """El cuadro mas nuevo como bytes JPEG, o None si no llego ninguno.

        Vacia la cola en cada llamada y devuelve el ultimo. Asi la imagen
        nunca se atrasa: es la diferencia entre verse en vivo y verse tarde.
        """
        if not self._transmitiendo:
            return None
        listos, _, _ = select.select([self._fd], [], [], espera)
        if not listos:
            return None
        ultimo = None
        while True:
            buf = Buffer(type=BUF_TYPE_VIDEO_CAPTURE, memory=MEMORY_MMAP)
            try:
                fcntl.ioctl(self._fd, VIDIOC_DQBUF, buf)
            except OSError:
                break  # no queda nada en la cola
            ultimo = self._mapas[buf.index][: buf.bytesused]
            fcntl.ioctl(self._fd, VIDIOC_QBUF, buf)
            listos, _, _ = select.select([self._fd], [], [], 0)
            if not listos:
                break
        return ultimo

    def control(self, nombre, valor=None):
        """Lee un control de la camara, o lo escribe si le pasan valor."""
        if nombre not in CONTROLES:
            raise KeyError(nombre)
        c = Control(id=CONTROLES[nombre], value=int(valor or 0))
        try:
            if valor is not None:
                fcntl.ioctl(self._fd, VIDIOC_S_CTRL, c)
            fcntl.ioctl(self._fd, VIDIOC_G_CTRL, c)
        except OSError:
            return None
        return c.value

    def cerrar(self):
        if self._transmitiendo:
            try:
                tipo = ctypes.c_uint32(BUF_TYPE_VIDEO_CAPTURE)
                fcntl.ioctl(self._fd, VIDIOC_STREAMOFF, tipo)
            except OSError:
                pass
            self._transmitiendo = False
        for m in self._mapas:
            m.close()
        self._mapas = []
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None

    def __enter__(self):
        return self.abrir()

    def __exit__(self, *_):
        self.cerrar()


if __name__ == "__main__":
    import sys
    import time

    dev = sys.argv[1] if len(sys.argv) > 1 else "/dev/video0"
    print(f"modos MJPG de {dev}:")
    for a, al, f in modos(dev):
        print(f"  {a}x{al} @ {f} fps")

    print("\nmidiendo 3 segundos a 1280x720...")
    with Camara(dev) as cam:
        n, pesos, arranque = 0, 0, time.monotonic()
        while time.monotonic() - arranque < 3:
            c = cam.cuadro()
            if c:
                n += 1
                pesos += len(c)
        seg = time.monotonic() - arranque
        print(f"  {n} cuadros en {seg:.1f}s = {n / seg:.1f} fps")
        print(f"  {pesos / n / 1024:.0f} KB por cuadro" if n else "  sin cuadros")
        print(f"  brillo={cam.control('brillo')} ganancia={cam.control('ganancia')}")
