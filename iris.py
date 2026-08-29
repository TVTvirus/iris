#!/usr/bin/env python3
"""Iris: verse, sacarse fotos y grabar video con la webcam.

Existe porque las tres alternativas fallaban en algo distinto:
  - Kamoso ya no se mantiene.
  - Webcamoid agarra el peor modo de la lista (crudo a 1080p = 5 fps) y su
    pipeline mete retraso visible.
  - Snapshot elige bien el formato pero pide 1080p interpolado, aplica rango
    de color 16-235 sobre un stream de rango completo (imagen lavada) y
    espeja la vista sin dejar apagarlo. No tiene un solo ajuste para nada
    de eso.

Aca el formato es MJPG siempre, la resolucion la elegis vos, el espejo y el
giro son interruptores, y la foto sale del mismo cuadro que estas viendo.

Una camara USB admite UN solo programa a la vez: es del aparato, no del
codigo. Por eso esta app es de instancia unica (abrirla dos veces levanta la
ventana que ya hay) y reintenta sola cuando el que la tenia la suelta.
"""

import datetime
import os
import queue
import subprocess
import sys
import threading

from PyQt6.QtCore import (
    QElapsedTimer,
    QPointF,
    QRectF,
    QSettings,
    QSize,
    QStandardPaths,
    Qt,
    QThread,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QAction,
    QActionGroup,
    QColor,
    QImage,
    QKeySequence,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QShortcut,
    QTransform,
)
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtWidgets import (
    QApplication,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

import audio
import iconos
import v4l2cam
from avanzado import Avanzado
from idiomas import T
import idiomas

DISPOSITIVO = "/dev/video0"
NOMBRE_SOCKET = "w4ve-iris"
FPS_POR_DEFECTO = 15

NEGRO = QColor(0, 0, 0)
BARRA = QColor(18, 18, 18)
BLANCO = QColor(255, 255, 255)
APAGADO = QColor(255, 255, 255, 90)
ROJO = QColor(232, 46, 46)


class Capturador(QThread):
    """Lee cuadros en su propio hilo y los va soltando."""

    cuadro = pyqtSignal(bytes)
    fallo = pyqtSignal(str, bool)

    def __init__(self, ancho, alto):
        super().__init__()
        self.ancho, self.alto = ancho, alto
        self.camara = None  # la usa el panel avanzado para tocar controles
        self._seguir = True

    def run(self):
        try:
            cam = v4l2cam.Camara(DISPOSITIVO, self.ancho, self.alto).abrir()
        except v4l2cam.CamaraOcupada as e:
            _, nuestro = v4l2cam.quien_la_tiene()
            self.fallo.emit(T("ocupada", quien=e), nuestro)
            return
        except v4l2cam.CamaraNoSirve as e:
            self.fallo.emit(T("no_abre", error=e), False)
            return
        self.camara = cam
        try:
            while self._seguir:
                datos = cam.cuadro(espera=0.5)
                if datos:
                    self.cuadro.emit(bytes(datos))
        finally:
            self.camara = None
            cam.cerrar()

    def parar(self):
        self._seguir = False
        self.wait(2000)


class Grabador:
    """Le pasa los JPEG a ffmpeg por una tuberia, en un hilo aparte.

    Escribir al pipe desde el hilo de la interfaz la congelaria cada vez que
    ffmpeg se demora, asi que va por una cola. Si la cola se llena se tiran
    cuadros: mejor perder uno que trabar la ventana.
    """

    def __init__(self, ruta, fps, espejo, giro, micro, crf=20):
        self.ruta = ruta
        self.perdidos = 0
        self._cola = queue.Queue(maxsize=60)
        orden = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "mjpeg", "-framerate", str(fps), "-i", "pipe:0",
        ]
        if micro:
            orden += ["-f", "pulse", "-i", micro]
        filtros = filtros_de_video(espejo, giro)
        if filtros:
            orden += ["-vf", filtros]
        orden += [
            "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf),
            "-pix_fmt", "yuv420p",
        ]
        if micro:
            orden += ["-c:a", "aac", "-b:a", "128k", "-shortest"]
        orden.append(ruta)
        self._proceso = subprocess.Popen(orden, stdin=subprocess.PIPE)
        self._hilo = threading.Thread(target=self._escribir, daemon=True)
        self._hilo.start()

    def _escribir(self):
        while True:
            dato = self._cola.get()
            if dato is None:
                break
            try:
                self._proceso.stdin.write(dato)
            except (BrokenPipeError, ValueError):
                break
        try:
            self._proceso.stdin.close()
        except (BrokenPipeError, ValueError):
            pass

    def poner(self, jpeg):
        try:
            self._cola.put_nowait(jpeg)
        except queue.Full:
            self.perdidos += 1

    def detener(self):
        self._cola.put(None)
        self._hilo.join(timeout=3)
        return self._proceso.wait(timeout=15)


def filtros_de_video(espejo, giro):
    """La cadena -vf de ffmpeg, en el mismo orden que aplica la vista.

    Primero el espejo y despues el giro, o el video no coincidiria con lo
    que se vio en pantalla al grabarlo.
    """
    partes = []
    if espejo:
        partes.append("hflip")
    if giro == 90:
        partes.append("transpose=1")
    elif giro == 180:
        partes.append("transpose=1,transpose=1")
    elif giro == 270:
        partes.append("transpose=2")
    return ",".join(partes)


def transformar(imagen, espejo, giro):
    """Aplica espejo y giro a un QImage o QPixmap, en ese orden."""
    if espejo:
        imagen = imagen.transformed(QTransform().scale(-1, 1))
    if giro:
        imagen = imagen.transformed(QTransform().rotate(giro))
    return imagen


# ------------------------------------------------------------- controles
class BotonIcono(QPushButton):
    """Boton redondo con un icono dibujado, sin texto ni marco."""

    def __init__(self, dibujo, ayuda, lado=40, alternable=False):
        super().__init__()
        self.dibujo = dibujo
        self.setToolTip(ayuda)
        self.setFixedSize(lado, lado)
        self.setCheckable(alternable)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFlat(True)
        self.setStyleSheet("border: none; background: transparent;")

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.isEnabled():
            color = QColor(255, 255, 255, 45)
        elif self.isChecked():
            color = BLANCO
        elif self.underMouse():
            color = BLANCO
        else:
            color = APAGADO
        if self.isChecked():
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 255, 255, 32))
            p.drawEllipse(self.rect().adjusted(1, 1, -1, -1))
        lado = min(self.width(), self.height())
        p.translate((self.width() - lado) / 2, (self.height() - lado) / 2)
        p.scale(lado / 100.0, lado / 100.0)
        p.translate(18, 18)
        p.scale(0.64, 0.64)
        iconos.DIBUJOS[self.dibujo](p, color)

    def enterEvent(self, e):
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.update()
        super().leaveEvent(e)


class Disparador(QPushButton):
    """El boton grande es un ojo, que es de donde sale el nombre del programa.

    Y le sirve de paso: el parpadeo ES el obturador, asi que sacar una foto
    se dibuja solo. El iris cambia de color segun lo que va a pasar al
    pulsarlo, y mientras graba el ojo se abre del todo y la pupila late,
    porque el ojo esta mirando y no piensa cerrarse.
    """

    def __init__(self):
        super().__init__()
        self.setFixedSize(84, 62)
        self.modo = "foto"  # foto | video | grabando
        self.apertura = 1.0  # 0 = parpado cerrado, 1 = ojo normal
        self._latido = 0.0  # 0..1, el pulso de la pupila al grabar
        self._fase_parpadeo = None
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFlat(True)
        self.setStyleSheet("border: none; background: transparent;")

        self._reloj = QTimer(self)
        self._reloj.setInterval(16)
        self._reloj.timeout.connect(self._tic)

    # ------------------------------------------------------------ animacion
    def poner_modo(self, modo):
        self.modo = modo
        self.setToolTip(
            {
                "foto": T("disparo_foto"),
                "video": T("disparo_video"),
                "grabando": T("disparo_parar"),
            }[modo]
        )
        if modo == "grabando":
            self._reloj.start()
        else:
            self._latido = 0.0
            if self._fase_parpadeo is None:
                self._reloj.stop()
        self.update()

    def parpadear(self):
        """Un parpadeo completo, que es lo que se ve al sacar la foto."""
        self._fase_parpadeo = 0.0
        self._reloj.start()

    def _tic(self):
        if self._fase_parpadeo is not None:
            # medio ciclo cerrando, medio abriendo, en unos 260 ms
            self._fase_parpadeo += 0.062
            if self._fase_parpadeo >= 1.0:
                self._fase_parpadeo = None
                self.apertura = 1.0
            else:
                cerrado = 1.0 - abs(self._fase_parpadeo - 0.5) * 2
                self.apertura = 1.0 - cerrado
        if self.modo == "grabando":
            self._latido = (self._latido + 0.022) % 1.0
        elif self._fase_parpadeo is None:
            self._reloj.stop()
        self.update()

    # -------------------------------------------------------------- dibujo
    def _contorno(self, apertura):
        """La almendra del ojo. Con apertura 0 queda una raja.

        Va con curvas cubicas y no cuadraticas: con una sola curva por
        parpado, el ojo bien abierto salia con punta arriba y abajo, mas
        hexagono que ojo.
        """
        ancho = self.width() * 0.94
        alto = self.height() * 0.46 * apertura
        cx, cy = self.width() / 2, self.height() / 2
        izq = QPointF(cx - ancho / 2, cy)
        der = QPointF(cx + ancho / 2, cy)
        # Los tiradores se separan a medida que el ojo se abre: si se quedan
        # cerca del centro, un ojo muy abierto sale con los lados rectos.
        tira = ancho * (0.20 + 0.22 * min(apertura, 1.2))
        camino = QPainterPath(izq)
        camino.cubicTo(
            QPointF(cx - tira, cy - alto * 1.34),
            QPointF(cx + tira, cy - alto * 1.34),
            der,
        )
        camino.cubicTo(
            QPointF(cx + tira, cy + alto * 1.34),
            QPointF(cx - tira, cy + alto * 1.34),
            izq,
        )
        return camino

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        vivo = self.isEnabled()

        apertura = self.apertura
        if vivo and self.modo == "grabando":
            apertura *= 1.08  # grabando, el ojo bien abierto
        elif vivo and self.underMouse():
            apertura *= 1.06

        blanco = BLANCO if vivo else QColor(255, 255, 255, 70)
        ojo = self._contorno(apertura)

        if apertura < 0.06:  # ojo cerrado: solo la linea del parpado
            pluma = QPen(blanco, 3.5)
            pluma.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pluma)
            p.drawLine(
                QPointF(self.width() * 0.03, self.height() / 2),
                QPointF(self.width() * 0.97, self.height() / 2),
            )
            return

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(blanco)
        p.drawPath(ojo)

        # El iris no puede salirse del ojo: se recorta con el propio contorno.
        p.save()
        p.setClipPath(ojo)
        centro = QPointF(self.width() / 2, self.height() / 2)
        radio = self.height() * 0.30
        if self.modo == "foto":
            color_iris = QColor(28, 28, 32) if vivo else QColor(70, 70, 70)
        else:
            color_iris = ROJO if vivo else QColor(120, 70, 70)
        p.setBrush(color_iris)
        p.drawEllipse(centro, radio, radio)

        # La pupila late mientras graba.
        pulso = 1.0 + 0.18 * abs(0.5 - self._latido) * 2 if self._latido else 1.0
        p.setBrush(QColor(8, 8, 10))
        p.drawEllipse(centro, radio * 0.44 * pulso, radio * 0.44 * pulso)

        # Un brillito, que es lo que hace que se lea como un ojo y no como
        # una diana.
        p.setBrush(QColor(255, 255, 255, 210))
        p.drawEllipse(
            QPointF(centro.x() - radio * 0.34, centro.y() - radio * 0.38),
            radio * 0.19,
            radio * 0.19,
        )
        p.restore()

    def enterEvent(self, e):
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.update()
        super().leaveEvent(e)


class Visor(QWidget):
    """Pinta el cuadro centrado, sin deformarlo, con destello al disparar."""

    def __init__(self):
        super().__init__()
        self.pixmap = None
        self.espejo = False
        self.giro = 0
        self._destello = 0.0
        self.setMinimumSize(320, 240)
        self._latido = QTimer(self)
        self._latido.timeout.connect(self._bajar_destello)

    def poner(self, pixmap):
        self.pixmap = pixmap
        self.update()

    def limpiar(self):
        self.pixmap = None
        self.update()

    def destellar(self):
        self._destello = 1.0
        self._latido.start(16)

    def _bajar_destello(self):
        self._destello -= 0.08
        if self._destello <= 0:
            self._destello = 0.0
            self._latido.stop()
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), NEGRO)
        if self.pixmap:
            pm = transformar(self.pixmap, self.espejo, self.giro)
            escalado = pm.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            p.drawPixmap(
                (self.width() - escalado.width()) // 2,
                (self.height() - escalado.height()) // 2,
                escalado,
            )
        if self._destello > 0:
            p.fillRect(self.rect(), QColor(255, 255, 255, int(self._destello * 200)))


class Ventana(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Iris")
        self.ajustes = QSettings("w4ve", "iris")
        self.hilo = None
        self.grabador = None
        self.ultimo_jpeg = None
        self.cuenta = 0
        self.fps_real = FPS_POR_DEFECTO
        self.modos_camara = []
        self.modo_video = self.ajustes.value("modo_video", False, type=bool)

        self.visor = Visor()
        self.visor.espejo = self.ajustes.value("espejo", True, type=bool)
        self.visor.giro = self.ajustes.value("giro", 0, type=int)

        # ------------------------------------------------------ controles
        self.b_mas = BotonIcono("mas", T("calidad_carpetas"))
        self.b_mas.clicked.connect(self._menu_mas)

        self.b_girar = BotonIcono("rotar", T("girar"))
        self.b_girar.clicked.connect(self._girar)

        self.b_espejo = BotonIcono("espejo", T("espejo"), alternable=True)
        self.b_espejo.setChecked(self.visor.espejo)
        self.b_espejo.toggled.connect(self._cambiar_espejo)

        self.b_micro = BotonIcono("micro", T("micro_on"), alternable=True)
        self.b_micro.setChecked(self.ajustes.value("micro", True, type=bool))
        self.b_micro.toggled.connect(self._cambiar_micro)

        # Cual microfono. Solo tiene sentido con el sonido encendido, asi que
        # aparece pegado a su boton y desaparece con el.
        self.b_cual_micro = QPushButton()
        self.b_cual_micro.setCursor(Qt.CursorShape.PointingHandCursor)
        self.b_cual_micro.setFlat(True)
        self.b_cual_micro.setMaximumWidth(150)
        self.b_cual_micro.setStyleSheet(
            "QPushButton { color: rgba(255,255,255,150); border: none;"
            " background: transparent; text-align: left; padding: 0 4px; }"
            "QPushButton:hover { color: #ffffff; }"
            "QPushButton:disabled { color: rgba(255,255,255,60); }"
        )
        self.b_cual_micro.clicked.connect(self._menu_micros)
        self._pintar_micro()
        self._cambiar_micro(self.b_micro.isChecked())

        self.b_foto = BotonIcono("foto", T("modo_foto"), alternable=True)
        self.b_video = BotonIcono("video", T("modo_video"), alternable=True)
        self.b_foto.clicked.connect(lambda: self._cambiar_modo(False))
        self.b_video.clicked.connect(lambda: self._cambiar_modo(True))

        self.disparador = Disparador()
        self.disparador.setEnabled(False)
        self.disparador.clicked.connect(self._disparar)

        # Tres columnas de igual peso: asi el disparador cae en el centro
        # exacto de la ventana, y no se corre segun cuantos botones haya a
        # cada lado.
        izquierda = QHBoxLayout()
        izquierda.setSpacing(4)
        for b in (self.b_mas, self.b_girar, self.b_espejo, self.b_micro):
            izquierda.addWidget(b)
        izquierda.addWidget(self.b_cual_micro)
        izquierda.addStretch(1)

        derecha = QHBoxLayout()
        derecha.setSpacing(4)
        derecha.addStretch(1)
        derecha.addWidget(self.b_foto)
        derecha.addWidget(self.b_video)

        fila = QGridLayout()
        fila.setContentsMargins(14, 0, 14, 0)
        fila.addLayout(izquierda, 0, 0)
        fila.addWidget(self.disparador, 0, 1, Qt.AlignmentFlag.AlignCenter)
        fila.addLayout(derecha, 0, 2)
        fila.setColumnStretch(0, 1)
        fila.setColumnStretch(2, 1)

        barra = QWidget()
        barra.setFixedHeight(86)
        barra.setLayout(fila)
        barra.setStyleSheet(f"background: {BARRA.name()};")

        self.estado = QLabel(T("abriendo"))
        self.estado.setStyleSheet("color: #8a8a8a; padding: 3px 14px;")
        self.estado.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.estado.setFixedHeight(24)

        caja = QVBoxLayout()
        caja.setContentsMargins(0, 0, 0, 0)
        caja.setSpacing(0)
        caja.addWidget(self.visor, 1)
        caja.addWidget(barra)
        caja.addWidget(self.estado)

        central = QWidget()
        central.setLayout(caja)
        central.setStyleSheet(f"background: {NEGRO.name()};")
        self.setCentralWidget(central)

        QShortcut(QKeySequence("Space"), self, self._disparar)
        QShortcut(QKeySequence("Ctrl+O"), self, self.abrir_carpeta)
        QShortcut(QKeySequence("R"), self, self._girar)
        QShortcut(QKeySequence("Ctrl+Shift+A"), self, self.abrir_avanzado)

        self.resize(
            self.ajustes.value("ancho_ventana", 900, type=int),
            self.ajustes.value("alto_ventana", 700, type=int),
        )

        self._reloj_grabacion = QElapsedTimer()
        self._contador = QTimer(self)
        self._contador.timeout.connect(self._latir)
        self._contador.start(1000)

        self._reintento = QTimer(self)
        self._reintento.setInterval(2000)
        self._reintento.timeout.connect(self._arrancar)

        self._cambiar_modo(self.modo_video)
        self._cargar_modos()

    # ------------------------------------------------------------ ayudas
    def decir(self, texto):
        self.estado.setText(texto)

    def carpeta_de(self, video):
        base = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.MoviesLocation
            if video
            else QStandardPaths.StandardLocation.PicturesLocation
        )
        destino = os.path.join(base or os.path.expanduser("~"), "Iris")
        os.makedirs(destino, exist_ok=True)
        return destino

    def _nombre_nuevo(self, extension, video):
        sello = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        return os.path.join(self.carpeta_de(video), f"Iris_{sello}.{extension}")

    @property
    def grabando(self):
        return self.grabador is not None

    @property
    def resolucion(self):
        return self.ajustes.value("resolucion", "1280x720", type=str)

    # ------------------------------------------------------------ camara
    def _cargar_modos(self):
        try:
            self.modos_camara = v4l2cam.modos(DISPOSITIVO)
        except v4l2cam.CamaraNoSirve as e:
            self.decir(T("sin_camara", error=e))
            return
        if self.resolucion not in [f"{a}x{b}" for a, b, _ in self.modos_camara]:
            a, b, _ = self.modos_camara[0]
            self.ajustes.setValue("resolucion", f"{a}x{b}")
        self._arrancar()

    def _menu_mas(self):
        menu = QMenu(self)
        grupo = QActionGroup(menu)
        for ancho, alto, _fps in self.modos_camara:
            texto = f"{ancho}x{alto}"
            accion = QAction(texto, menu, checkable=True)
            accion.setChecked(texto == self.resolucion)
            accion.setEnabled(not self.grabando)
            accion.triggered.connect(
                lambda _, t=texto: self._cambiar_resolucion(t)
            )
            grupo.addAction(accion)
            menu.addAction(accion)
        menu.addSeparator()
        menu.addAction(T("carpeta_fotos"), lambda: self.abrir_carpeta(False))
        menu.addAction(T("carpeta_videos"), lambda: self.abrir_carpeta(True))
        menu.addSeparator()
        # Discreto a propósito: al final, sin icono y en gris. Quien lo
        # necesita lo busca; al resto no le estorba.
        avanzado = menu.addAction(T("avanzado"))
        avanzado.setToolTip("Ctrl+Shift+A")
        avanzado.triggered.connect(self.abrir_avanzado)
        menu.exec(self.b_mas.mapToGlobal(self.b_mas.rect().bottomLeft()))

    def _arrancar(self):
        self._parar()
        ancho, alto = (int(v) for v in self.resolucion.split("x"))
        self.hilo = Capturador(ancho, alto)
        self.hilo.cuadro.connect(self._recibir)
        self.hilo.fallo.connect(self._fallo)
        self.hilo.start()

    def _parar(self):
        if self.hilo:
            self.hilo.parar()
            self.hilo = None

    def _recibir(self, datos):
        if self._reintento.isActive():
            self._reintento.stop()
        imagen = QImage.fromData(datos, "JPG")
        if imagen.isNull():
            return
        self.ultimo_jpeg = datos
        self.visor.poner(QPixmap.fromImage(imagen))
        self.cuenta += 1
        if self.grabador:
            self.grabador.poner(datos)
        if not self.disparador.isEnabled():
            self.disparador.setEnabled(True)

    def _fallo(self, mensaje, es_nuestra):
        self.disparador.setEnabled(False)
        self.visor.limpiar()
        if es_nuestra:
            self.decir(mensaje + T("ocupada_nuestra"))
            return
        self.decir(mensaje + T("ocupada_otro"))
        if not self._reintento.isActive():
            self._reintento.start()

    def _latir(self):
        if self.grabando:
            seg = self._reloj_grabacion.elapsed() // 1000
            perdidos = self.grabador.perdidos
            aviso = T("perdidos", cuantos=perdidos) if perdidos else ""
            self.decir(
                T(
                    "grabando",
                    tiempo=f"{seg // 60:02d}:{seg % 60:02d}",
                    archivo=os.path.basename(self.grabador.ruta),
                )
                + aviso
            )
        elif self.cuenta:
            self.fps_real = self.cuenta
            giro = (
                T("estado_girada", grados=self.visor.giro) if self.visor.giro else ""
            )
            self.decir(
                T("estado", resolucion=self.resolucion, fps=self.cuenta) + giro
            )
        self.cuenta = 0

    # ----------------------------------------------------------- acciones
    def _cambiar_modo(self, video):
        if self.grabando:
            return
        self.modo_video = video
        self.ajustes.setValue("modo_video", video)
        self.b_foto.setChecked(not video)
        self.b_video.setChecked(video)
        self.disparador.poner_modo("video" if video else "foto")
        # El micrófono solo pinta algo cuando se graba video.
        self.b_micro.setVisible(video)
        self.b_cual_micro.setVisible(video and self.b_micro.isChecked())

    def _cambiar_espejo(self, activo):
        self.visor.espejo = activo
        self.ajustes.setValue("espejo", activo)
        self.visor.update()

    def _cambiar_micro(self, activo):
        self.b_micro.dibujo = "micro" if activo else "micro_mudo"
        self.b_micro.setToolTip(T("micro_on") if activo else T("micro_off"))
        self.ajustes.setValue("micro", activo)
        self.b_micro.update()
        # Elegir cuál micrófono no significa nada si el sonido está apagado.
        self.b_cual_micro.setVisible(activo and self.modo_video)

    def _pintar_micro(self):
        """Escribe en el botón el nombre del micrófono elegido, recortado."""
        nombre = audio.nombre_de(self.ajustes.value("micro_id", audio.PREDETERMINADO))
        metrica = self.b_cual_micro.fontMetrics()
        self.b_cual_micro.setText(
            metrica.elidedText(nombre, Qt.TextElideMode.ElideRight, 140)
        )
        self.b_cual_micro.setToolTip(T("micro_cual", nombre=nombre))

    def _menu_micros(self):
        menu = QMenu(self)
        grupo = QActionGroup(menu)
        actual = self.ajustes.value("micro_id", audio.PREDETERMINADO)
        for ident, nombre in audio.microfonos():
            accion = QAction(nombre, menu, checkable=True)
            accion.setChecked(ident == actual)
            accion.setEnabled(not self.grabando)
            accion.triggered.connect(lambda _, i=ident: self._elegir_micro(i))
            grupo.addAction(accion)
            menu.addAction(accion)
        menu.exec(
            self.b_cual_micro.mapToGlobal(self.b_cual_micro.rect().bottomLeft())
        )

    def _elegir_micro(self, ident):
        self.ajustes.setValue("micro_id", ident)
        self._pintar_micro()
        self.decir(T("micro_elegido", nombre=audio.nombre_de(ident)))

    def _girar(self):
        if self.grabando:
            return
        self.visor.giro = (self.visor.giro + 90) % 360
        self.ajustes.setValue("giro", self.visor.giro)
        self.visor.update()
        self.decir(
            T("girada", grados=self.visor.giro)
            if self.visor.giro
            else T("derecha")
        )

    def _cambiar_resolucion(self, texto):
        self.ajustes.setValue("resolucion", texto)
        self.disparador.setEnabled(False)
        self._arrancar()

    def _disparar(self):
        if self.grabando:
            self._parar_grabacion()
        elif self.modo_video:
            self._empezar_grabacion()
        else:
            self.sacar_foto()

    def sacar_foto(self):
        if not self.ultimo_jpeg or not self.disparador.isEnabled():
            return
        ruta = self._nombre_nuevo("jpg", video=False)
        if self.visor.espejo or self.visor.giro:
            # Voltear o girar obliga a tocar los píxeles, así que toca
            # recomprimir. Derecha y sin espejo se guarda el JPEG tal cual
            # sale de la cámara: ni un bit de pérdida.
            imagen = QImage.fromData(self.ultimo_jpeg, "JPG")
            transformar(imagen, self.visor.espejo, self.visor.giro).save(
                ruta, "JPEG", self.ajustes.value("calidad_jpeg", 95, type=int)
            )
        else:
            with open(ruta, "wb") as f:
                f.write(self.ultimo_jpeg)
        self.visor.destellar()
        self.disparador.parpadear()
        self.decir(T("foto_guardada", archivo=os.path.basename(ruta)))

    def _empezar_grabacion(self):
        ruta = self._nombre_nuevo("mp4", video=True)
        try:
            self.grabador = Grabador(
                ruta,
                self.fps_real or FPS_POR_DEFECTO,
                self.visor.espejo,
                self.visor.giro,
                self.ajustes.value("micro_id", audio.PREDETERMINADO)
                if self.b_micro.isChecked()
                else None,
                self.ajustes.value("calidad_crf", 20, type=int),
            )
        except OSError as e:
            self.decir(T("no_graba", error=e))
            return
        self._reloj_grabacion.start()
        self.disparador.poner_modo("grabando")
        # Cambiar cualquiera de estos a media grabación rompería el archivo.
        for w in (
            self.b_espejo, self.b_girar, self.b_micro,
            self.b_cual_micro, self.b_foto, self.b_video,
        ):
            w.setEnabled(False)

    def _parar_grabacion(self):
        grabador, self.grabador = self.grabador, None
        self.disparador.poner_modo("video")
        for w in (
            self.b_espejo, self.b_girar, self.b_micro,
            self.b_cual_micro, self.b_foto, self.b_video,
        ):
            w.setEnabled(True)
        self.decir(T("cerrando"))
        QApplication.processEvents()
        codigo = grabador.detener()
        seg = self._reloj_grabacion.elapsed() / 1000
        if codigo == 0 and os.path.exists(grabador.ruta):
            mb = os.path.getsize(grabador.ruta) / 1024 / 1024
            self.decir(
                T(
                    "video_guardado",
                    archivo=os.path.basename(grabador.ruta),
                    segundos=f"{seg:.0f}",
                    tamano=f"{mb:.1f}",
                )
            )
        else:
            self.decir(T("video_fallo", codigo=codigo))

    def abrir_avanzado(self):
        """El panel escondido. Necesita la cámara viva para tocar controles."""
        Avanzado(self, self.ajustes, self.hilo.camara if self.hilo else None).exec()

    def abrir_carpeta(self, video=None):
        subprocess.Popen(
            ["xdg-open", self.carpeta_de(self.modo_video if video is None else video)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    # -------------------------------------------------------------- cierre
    def levantar(self, token=""):
        """La llama la segunda instancia: traer esta ventana al frente.

        En Wayland un programa no puede subirse solo al frente: KWin lo
        ignora en silencio. La unica forma legitima es el token de
        activacion que el compositor le da a quien lanzo la segunda copia,
        asi que ella nos lo pasa y Qt lo usa al activar. Si no hay token
        (arrancada desde una terminal, por ejemplo) al menos hacemos
        parpadear la entrada en la barra de tareas, que si esta permitido.
        """
        if token:
            os.environ["XDG_ACTIVATION_TOKEN"] = token
        self.showNormal()
        self.raise_()
        self.activateWindow()
        os.environ.pop("XDG_ACTIVATION_TOKEN", None)
        QApplication.alert(self)

    def closeEvent(self, evento):
        if self.grabando:
            self._parar_grabacion()
        self.ajustes.setValue("ancho_ventana", self.width())
        self.ajustes.setValue("alto_ventana", self.height())
        self._reintento.stop()
        self._parar()
        evento.accept()


def main():
    # Instancia unica: la camara solo admite un programa a la vez, asi que
    # abrir la app dos veces no puede terminar bien. La segunda le avisa a la
    # primera y se va.
    aviso = QLocalSocket()
    aviso.connectToServer(NOMBRE_SOCKET)
    if aviso.waitForConnected(300):
        # Le regalamos nuestro token de activacion: es lo unico que le
        # permite a la ventana que ya existe ponerse delante.
        token = os.environ.get("XDG_ACTIVATION_TOKEN", "")
        aviso.write(b"levantate:" + token.encode())
        aviso.flush()
        aviso.waitForBytesWritten(300)
        aviso.disconnectFromServer()
        return 0

    app = QApplication(sys.argv)
    app.setApplicationName("Iris")
    # El idioma se fija antes de construir la ventana: después, los textos
    # ya están puestos y no se vuelven a pedir.
    idiomas.elegir(QSettings("w4ve", "iris").value("idioma", "auto", type=str))
    # Sin esto KDE le pone el icono generico, un cuadro amarillo.
    app.setDesktopFileName("iris")
    app.setWindowIcon(iconos.icono_app())
    ventana = Ventana()

    QLocalServer.removeServer(NOMBRE_SOCKET)  # por si quedo huerfano
    servidor = QLocalServer()
    servidor.listen(NOMBRE_SOCKET)

    def atender():
        conexion = servidor.nextPendingConnection()
        if conexion is None:
            return
        conexion.waitForReadyRead(300)
        mensaje = bytes(conexion.readAll()).decode(errors="replace")
        ventana.levantar(mensaje.split(":", 1)[1] if ":" in mensaje else "")
        conexion.disconnectFromServer()

    servidor.newConnection.connect(atender)

    ventana.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
