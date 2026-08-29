"""Captura de webcam por V4L2, sin dependencias externas.

Le habla al kernel directamente por ioctl y entrega los cuadros como JPEG
crudo, tal cual sale de la camara. Qt sabe decodificar eso solo, asi que no
hace falta OpenCV ni GStreamer, y la foto se puede guardar sin recomprimir.

Por que MJPG y no crudo: una webcam USB 2.0 no tiene ancho de banda para
video sin comprimir. Una camara tipica da 5 fps en YUYV a 1080p y 30
declarados (15 reales) en MJPG a cualquier resolucion.

Los numeros de ioctl NO estan escritos a mano: se calculan con la misma
formula que usa el kernel, a partir del tamaño real de cada estructura. Por
eso las estructuras llevan uniones de verdad en vez de relleno a ojo: asi
ctypes calcula la alineacion sola y los numeros salen bien tanto en 64 bits
como en 32 o en ARM, donde un puntero mide distinto y las estructuras
cambian de tamaño.
"""

import ctypes
import fcntl
import glob
import mmap
import os
import select

# ------------------------------------------------------- numeros de ioctl
# _IOC(direccion, tipo, numero, tamaño), tal cual asm-generic/ioctl.h
_NINGUNA, _ESCRIBIR, _LEER = 0, 1, 2


def _IOC(direccion, tipo, numero, tamano):
    return (direccion << 30) | (tamano << 16) | (ord(tipo) << 8) | numero


def _IOR(tipo, numero, estructura):
    return _IOC(_LEER, tipo, numero, ctypes.sizeof(estructura))


def _IOW(tipo, numero, estructura):
    return _IOC(_ESCRIBIR, tipo, numero, ctypes.sizeof(estructura))


def _IOWR(tipo, numero, estructura):
    return _IOC(_LEER | _ESCRIBIR, tipo, numero, ctypes.sizeof(estructura))


BUF_TYPE_VIDEO_CAPTURE = 1
MEMORY_MMAP = 1
FRMIVAL_TYPE_DISCRETE = 1
FRMSIZE_TYPE_DISCRETE = 1
CAP_VIDEO_CAPTURE = 0x00000001
CAP_DEVICE_CAPS = 0x80000000

CONTROLES = {
    "brillo": 0x00980900,
    "contraste": 0x00980901,
    "saturacion": 0x00980902,
    "ganancia": 0x00980913,
    "exposicion": 0x009A0902,
    "exposicion_auto": 0x009A0901,
    "prioridad_exposicion": 0x009A0903,
}


def fourcc(texto):
    return sum(ord(c) << (8 * i) for i, c in enumerate(texto))


MJPG = fourcc("MJPG")

u8, u32, i32 = ctypes.c_uint8, ctypes.c_uint32, ctypes.c_int32


# --------------------------------------------------------------- structs
class Capacidad(ctypes.Structure):
    _fields_ = [
        ("driver", u8 * 16),
        ("card", u8 * 32),
        ("bus_info", u8 * 32),
        ("version", u32),
        ("capabilities", u32),
        ("device_caps", u32),
        ("_reservado", u32 * 3),
    ]


class Fract(ctypes.Structure):
    _fields_ = [("num", u32), ("den", u32)]


class PixFormat(ctypes.Structure):
    _fields_ = [
        ("width", u32),
        ("height", u32),
        ("pixelformat", u32),
        ("field", u32),
        ("bytesperline", u32),
        ("sizeimage", u32),
        ("colorspace", u32),
        ("priv", u32),
        ("flags", u32),
        ("enc", u32),
        ("quantization", u32),
        ("xfer_func", u32),
    ]


class _Ventana(ctypes.Structure):
    """v4l2_window. No la usamos: esta para que la union se alinee bien.

    Es la unica rama del union que contiene punteros, y por eso el union
    entero se alinea a 8 en 64 bits. Sin ella, el tamaño de v4l2_format
    saldria 204 en vez de 208 y el numero del ioctl seria otro.
    """

    _fields_ = [
        ("rect", u32 * 4),
        ("field", u32),
        ("chromakey", u32),
        ("clips", ctypes.c_void_p),
        ("clipcount", u32),
        ("bitmap", ctypes.c_void_p),
        ("global_alpha", u8),
    ]


class _UnionFormato(ctypes.Union):
    _fields_ = [("pix", PixFormat), ("win", _Ventana), ("crudo", u8 * 200)]


class Formato(ctypes.Structure):
    _fields_ = [("type", u32), ("fmt", _UnionFormato)]


class PedidoBuffers(ctypes.Structure):
    _fields_ = [
        ("count", u32),
        ("type", u32),
        ("memory", u32),
        ("capabilities", u32),
        ("flags", u8),
        ("_reservado", u8 * 3),
    ]


class Temporizador(ctypes.Structure):
    _fields_ = [("tv_sec", ctypes.c_long), ("tv_usec", ctypes.c_long)]


class _UnionBuffer(ctypes.Union):
    _fields_ = [
        ("offset", u32),
        ("userptr", ctypes.c_ulong),
        ("planes", ctypes.c_void_p),
        ("fd", i32),
    ]


class Buffer(ctypes.Structure):
    _fields_ = [
        ("index", u32),
        ("type", u32),
        ("bytesused", u32),
        ("flags", u32),
        ("field", u32),
        ("timestamp", Temporizador),
        ("timecode", u8 * 16),
        ("sequence", u32),
        ("memory", u32),
        ("m", _UnionBuffer),
        ("length", u32),
        ("reserved2", u32),
        ("request_fd", i32),
    ]


class TamanoCuadro(ctypes.Structure):
    _fields_ = [
        ("index", u32),
        ("pixel_format", u32),
        ("type", u32),
        ("width", u32),
        ("height", u32),
        ("_resto", u32 * 6),
    ]


class IntervaloCuadro(ctypes.Structure):
    _fields_ = [
        ("index", u32),
        ("pixel_format", u32),
        ("width", u32),
        ("height", u32),
        ("type", u32),
        ("discrete", Fract),
        ("_resto", u32 * 6),
    ]


class Control(ctypes.Structure):
    _fields_ = [("id", u32), ("value", i32)]


VIDIOC_QUERYCAP = _IOR("V", 0, Capacidad)
VIDIOC_S_FMT = _IOWR("V", 5, Formato)
VIDIOC_REQBUFS = _IOWR("V", 8, PedidoBuffers)
VIDIOC_QUERYBUF = _IOWR("V", 9, Buffer)
VIDIOC_QBUF = _IOWR("V", 15, Buffer)
VIDIOC_DQBUF = _IOWR("V", 17, Buffer)
VIDIOC_STREAMON = _IOW("V", 18, i32)
VIDIOC_STREAMOFF = _IOW("V", 19, i32)
VIDIOC_G_CTRL = _IOWR("V", 27, Control)
VIDIOC_S_CTRL = _IOWR("V", 28, Control)
VIDIOC_ENUM_FRAMESIZES = _IOWR("V", 74, TamanoCuadro)
VIDIOC_ENUM_FRAMEINTERVALS = _IOWR("V", 75, IntervaloCuadro)


# ----------------------------------------------------------------- error
class CamaraOcupada(Exception):
    """Otro programa tiene la camara abierta. Solo cabe uno a la vez."""


class CamaraNoSirve(Exception):
    """La camara no existe, o no da MJPG."""


# ----------------------------------------------------------------- api
def _texto(campo):
    return bytes(campo).split(b"\0")[0].decode(errors="replace").strip()


def _nombre_limpio(card):
    """El nombre que da el kernel, sin la coletilla truncada.

    El campo `card` mide 32 bytes y los drivers UVC suelen meter ahi el
    nombre dos veces separado por dos puntos, con el segundo cortado a la
    mitad: "REDRAGON Live Camera:  REDRAGO". Nos quedamos con el primero.
    """
    nombre = _texto(card)
    return nombre.split(":")[0].strip() or nombre


def camaras():
    """[(ruta, nombre)] de las camaras que sirven, ordenadas por ruta.

    Una sola webcam suele exponer varios /dev/videoN: los de mas suelen ser
    nodos de metadatos, no de imagen. Se queda solo con los que dicen saber
    capturar video Y ofrecen algun tamaño en MJPG, que es lo unico que esta
    app sabe pedir.
    """
    encontradas = []
    for ruta in sorted(glob.glob("/dev/video*")):
        try:
            fd = os.open(ruta, os.O_RDWR | os.O_NONBLOCK)
        except OSError:
            continue  # ocupada o sin permiso: no es asunto nuestro ahora
        try:
            cap = Capacidad()
            fcntl.ioctl(fd, VIDIOC_QUERYCAP, cap)
            puede = cap.device_caps if cap.capabilities & CAP_DEVICE_CAPS else cap.capabilities
            if not puede & CAP_VIDEO_CAPTURE:
                continue
            tamano = TamanoCuadro(index=0, pixel_format=MJPG)
            fcntl.ioctl(fd, VIDIOC_ENUM_FRAMESIZES, tamano)
            encontradas.append((ruta, _nombre_limpio(cap.card) or ruta))
        except OSError:
            continue
        finally:
            os.close(fd)
    return encontradas


def primera_camara():
    """La ruta de la primera camara util, o /dev/video0 si no hay ninguna."""
    halladas = camaras()
    return halladas[0][0] if halladas else "/dev/video0"


def nombre_de(ruta):
    for camino, nombre in camaras():
        if camino == ruta:
            return nombre
    return ruta


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
            if t.type != FRMSIZE_TYPE_DISCRETE:
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
    ("ffplay", "ffplay"),
    ("cheese", "Cheese"),
    ("firefox", "Firefox"),
    ("chrome", "Chrome"),
    ("chromium", "Chromium"),
    ("zoom", "Zoom"),
    ("teams", "Teams"),
)


def quien_la_tiene(dispositivo=None):
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
                destino = os.readlink(f"/proc/{pid}/fd/{fd}")
                if not destino.startswith("/dev/video"):
                    continue
                if dispositivo and destino != dispositivo:
                    continue
                with open(f"/proc/{pid}/cmdline", "rb") as f:
                    linea = f.read().replace(b"\0", b" ").decode(errors="replace")
            except OSError:
                continue
            for pista, apodo in _APODOS:
                if pista.lower() in linea.lower():
                    return apodo, pista == "iris.py"
            try:
                with open(f"/proc/{pid}/comm") as f:
                    return f.read().strip(), False
            except OSError:
                continue
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

    def _ocupada(self, error):
        quien, _ = quien_la_tiene(self.dispositivo)
        return CamaraOcupada(quien or "otro programa")

    def abrir(self):
        try:
            self._fd = os.open(self.dispositivo, os.O_RDWR | os.O_NONBLOCK)
        except OSError as e:
            if e.errno in (16, 11):  # EBUSY, EAGAIN
                raise self._ocupada(e) from e
            raise CamaraNoSirve(str(e)) from e

        fmt = Formato(type=BUF_TYPE_VIDEO_CAPTURE)
        fmt.fmt.pix.width = self.ancho
        fmt.fmt.pix.height = self.alto
        fmt.fmt.pix.pixelformat = MJPG
        fmt.fmt.pix.field = 1  # NONE
        try:
            fcntl.ioctl(self._fd, VIDIOC_S_FMT, fmt)
        except OSError as e:
            self.cerrar()
            if e.errno == 16:
                raise self._ocupada(e) from e
            raise CamaraNoSirve(f"no acepta MJPG: {e}") from e

        # El driver puede corregir lo pedido: nos quedamos con lo que dio.
        self.ancho, self.alto = fmt.fmt.pix.width, fmt.fmt.pix.height
        if fmt.fmt.pix.pixelformat != MJPG:
            self.cerrar()
            raise CamaraNoSirve("la camara no da MJPG")

        pedido = PedidoBuffers(
            count=self._buffers, type=BUF_TYPE_VIDEO_CAPTURE, memory=MEMORY_MMAP
        )
        try:
            fcntl.ioctl(self._fd, VIDIOC_REQBUFS, pedido)
        except OSError as e:
            self.cerrar()
            raise self._ocupada(e) from e

        for i in range(pedido.count):
            buf = Buffer(index=i, type=BUF_TYPE_VIDEO_CAPTURE, memory=MEMORY_MMAP)
            fcntl.ioctl(self._fd, VIDIOC_QUERYBUF, buf)
            self._mapas.append(
                mmap.mmap(
                    self._fd,
                    buf.length,
                    flags=mmap.MAP_SHARED,
                    prot=mmap.PROT_READ,
                    offset=buf.m.offset,
                )
            )
            fcntl.ioctl(self._fd, VIDIOC_QBUF, buf)

        tipo = ctypes.c_int32(BUF_TYPE_VIDEO_CAPTURE)
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
                tipo = ctypes.c_int32(BUF_TYPE_VIDEO_CAPTURE)
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

    halladas = camaras()
    print(f"camaras encontradas: {len(halladas)}")
    for ruta, nombre in halladas:
        print(f"  {ruta}  {nombre}")

    dev = sys.argv[1] if len(sys.argv) > 1 else primera_camara()
    print(f"\nmodos MJPG de {dev}:")
    for a, al, f in modos(dev):
        print(f"  {a}x{al} @ {f} fps")

    print("\nmidiendo 5 segundos a 1280x720...")
    with Camara(dev) as cam:
        cam.cuadro()  # el primero se lleva el arranque del sensor
        n, pesos, arranque = 0, 0, time.monotonic()
        while time.monotonic() - arranque < 5:
            c = cam.cuadro()
            if c:
                n += 1
                pesos += len(c)
        seg = time.monotonic() - arranque
        print(f"  {n} cuadros en {seg:.1f}s = {n / seg:.1f} fps reales")
        if n:
            print(f"  {pesos / n / 1024:.0f} KB por cuadro")
        print(f"  brillo={cam.control('brillo')} ganancia={cam.control('ganancia')}")
