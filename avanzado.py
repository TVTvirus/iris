"""Las opciones avanzadas: hablarle a los controles de la camara.

Esta escondido a proposito. La mayoria de la gente abre una camara para
sacarse una foto, no para ajustar la ganancia del sensor; el que necesita
esto lo busca y lo encuentra, y al resto no le estorba.

Todo lo que tiene rango es una barra, y las barras se manejan de las cuatro
maneras que la gente prueba: arrastrar, rueda, clic izquierdo (sube) y clic
derecho (baja), con los extremos `-` y `+` a los lados.
"""

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

import v4l2cam
from idiomas import DISPONIBLES, T

# Que controles se ofrecen y en que orden. Los que la camara no soporte se
# quedan en gris en vez de desaparecer: asi se ve que existen y que es la
# camara la que no puede, no el programa el que no quiso.
CONTROLES = (
    ("brillo", "ctrl_brillo", -64, 64),
    ("contraste", "ctrl_contraste", 0, 64),
    ("saturacion", "ctrl_saturacion", 0, 128),
    ("ganancia", "ctrl_ganancia", 0, 100),
    ("exposicion", "ctrl_exposicion", 1, 5000),
)


class Barra(QWidget):
    """Una barra de rango con las cuatro formas de moverla.

    Arrastrar, rueda, clic izquierdo (sube un paso) y clic derecho (baja un
    paso). La gente prueba las cuatro, asi que las cuatro tienen que estar.
    """

    cambio = pyqtSignal(int)

    def __init__(self, minimo, maximo, valor):
        super().__init__()
        self.minimo, self.maximo = minimo, maximo
        self.valor = max(minimo, min(maximo, valor))
        self.paso = max(1, (maximo - minimo) // 40)
        self.setFixedHeight(26)
        self.setMinimumWidth(190)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(T("barra_ayuda"))

    def sizeHint(self):
        return QSize(220, 26)

    def poner(self, valor, avisar=True):
        nuevo = max(self.minimo, min(self.maximo, int(valor)))
        if nuevo != self.valor:
            self.valor = nuevo
            self.update()
            if avisar:
                self.cambio.emit(nuevo)

    @property
    def _fraccion(self):
        rango = self.maximo - self.minimo
        return (self.valor - self.minimo) / rango if rango else 0.0

    def _canal(self):
        return self.rect().adjusted(18, 0, -18, 0)

    def _por_posicion(self, x):
        canal = self._canal()
        if canal.width() <= 0:
            return self.valor
        frac = (x - canal.left()) / canal.width()
        return self.minimo + frac * (self.maximo - self.minimo)

    # ------------------------------------------------------------ eventos
    def mousePressEvent(self, e):
        canal = self._canal()
        pos = e.position()
        if pos.x() < canal.left():  # el "-" de la izquierda
            self.poner(self.valor - self.paso)
        elif pos.x() > canal.right():  # el "+" de la derecha
            self.poner(self.valor + self.paso)
        elif e.button() == Qt.MouseButton.RightButton:
            self.poner(self.valor - self.paso)
        else:
            self.poner(self._por_posicion(pos.x()))

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.MouseButton.LeftButton:
            self.poner(self._por_posicion(e.position().x()))

    def wheelEvent(self, e):
        pasos = e.angleDelta().y() / 120
        self.poner(self.valor + self.paso * pasos)
        e.accept()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        vivo = self.isEnabled()
        tenue = QColor(255, 255, 255, 60 if vivo else 26)
        fuerte = QColor(255, 255, 255, 230 if vivo else 60)
        canal = self._canal()
        medio = canal.center().y()

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(tenue)
        p.drawRoundedRect(canal.left(), medio - 2, canal.width(), 4, 2, 2)
        ancho = int(canal.width() * self._fraccion)
        p.setBrush(fuerte)
        p.drawRoundedRect(canal.left(), medio - 2, ancho, 4, 2, 2)
        p.drawEllipse(canal.left() + ancho - 6, medio - 6, 12, 12)

        # los extremos, que también son botones
        p.setPen(fuerte)
        f = p.font()
        f.setPointSize(11)
        p.setFont(f)
        p.drawText(
            self.rect().adjusted(0, 0, -self.width() + 16, 0),
            Qt.AlignmentFlag.AlignCenter,
            "−",
        )
        p.drawText(
            self.rect().adjusted(self.width() - 16, 0, 0, 0),
            Qt.AlignmentFlag.AlignCenter,
            "+",
        )


class Avanzado(QDialog):
    """El panel escondido. Recibe la cámara viva para tocarla en caliente."""

    def __init__(self, padre, ajustes, camara_viva):
        super().__init__(padre)
        self.ajustes = ajustes
        self.camara = camara_viva
        self.barras = {}
        self._de_fabrica = {}

        self.setWindowTitle(T("avanzado_titulo"))
        self.setMinimumWidth(430)
        self.setStyleSheet(
            "QDialog { background: #141414; }"
            "QLabel { color: #d8d8d8; }"
            "QPushButton { color: #e8e8e8; background: #262626; border: none;"
            " padding: 7px 14px; border-radius: 4px; }"
            "QPushButton:hover { background: #333333; }"
            "QComboBox { color: #e8e8e8; background: #262626; border: none;"
            " padding: 5px 8px; border-radius: 4px; }"
        )

        caja = QVBoxLayout(self)
        caja.setContentsMargins(18, 16, 18, 14)
        caja.setSpacing(10)

        aviso = QLabel(T("avanzado_aviso"))
        aviso.setWordWrap(True)
        aviso.setStyleSheet("color: #8a8a8a;")
        caja.addWidget(aviso)

        caja.addWidget(self._titulo(T("ajustes_camara")))
        for clave, etiqueta, minimo, maximo in CONTROLES:
            caja.addLayout(self._fila_control(clave, etiqueta, minimo, maximo))

        caja.addSpacing(6)
        caja.addWidget(self._titulo(T("ajustes_app")))
        caja.addLayout(
            self._fila_calidad(
                "jpeg", T("calidad_jpeg"), 60, 100, 95, T("calidad_jpeg_ayuda")
            )
        )
        caja.addLayout(
            self._fila_calidad(
                "crf", T("calidad_video"), 14, 32, 20, T("calidad_video_ayuda")
            )
        )
        caja.addLayout(self._fila_idioma())

        pie = QHBoxLayout()
        restablecer = QPushButton(T("restablecer"))
        restablecer.clicked.connect(self._restablecer)
        cerrar = QPushButton(T("cerrar"))
        cerrar.clicked.connect(self.accept)
        pie.addWidget(restablecer)
        pie.addStretch(1)
        pie.addWidget(cerrar)
        caja.addSpacing(4)
        caja.addLayout(pie)

    # ------------------------------------------------------------- piezas
    def _titulo(self, texto):
        etiqueta = QLabel(texto)
        etiqueta.setStyleSheet("color: #ffffff; font-weight: 600;")
        return etiqueta

    def _fila_control(self, clave, etiqueta, minimo, maximo):
        fila = QHBoxLayout()
        nombre = QLabel(T(etiqueta))
        nombre.setFixedWidth(96)
        valor = self.camara.control(clave) if self.camara else None
        barra = Barra(minimo, maximo, valor if valor is not None else minimo)
        numero = QLabel(str(valor) if valor is not None else "—")
        numero.setFixedWidth(44)
        numero.setAlignment(Qt.AlignmentFlag.AlignRight)

        if valor is None:
            # La cámara no soporta este control: gris, y se dice por qué.
            for w in (nombre, barra, numero):
                w.setEnabled(False)
            barra.setToolTip(T("ctrl_no_soportado"))
        else:
            self._de_fabrica[clave] = valor
            barra.cambio.connect(
                lambda v, c=clave, n=numero: self._tocar(c, v, n)
            )
        self.barras[clave] = (barra, numero)
        fila.addWidget(nombre)
        fila.addWidget(barra, 1)
        fila.addWidget(numero)
        return fila

    def _tocar(self, clave, valor, numero):
        if self.camara:
            self.camara.control(clave, valor)
        numero.setText(str(valor))

    def _fila_calidad(self, clave, etiqueta, minimo, maximo, defecto, ayuda=""):
        fila = QHBoxLayout()
        nombre = QLabel(etiqueta)
        nombre.setWordWrap(True)
        nombre.setFixedWidth(96)
        nombre.setToolTip(ayuda)
        valor = self.ajustes.value(f"calidad_{clave}", defecto, type=int)
        barra = Barra(minimo, maximo, valor)
        if ayuda:
            barra.setToolTip(f"{ayuda}\n\n{T('barra_ayuda')}")
        numero = QLabel(str(valor))
        numero.setFixedWidth(44)
        numero.setAlignment(Qt.AlignmentFlag.AlignRight)
        barra.cambio.connect(
            lambda v, c=clave, n=numero: (
                self.ajustes.setValue(f"calidad_{c}", v),
                n.setText(str(v)),
            )
        )
        fila.addWidget(nombre)
        fila.addWidget(barra, 1)
        fila.addWidget(numero)
        return fila

    def _fila_idioma(self):
        fila = QHBoxLayout()
        nombre = QLabel(T("idioma"))
        nombre.setFixedWidth(96)
        caja = QComboBox()
        guardado = self.ajustes.value("idioma", "auto", type=str)
        for codigo, etiqueta in DISPONIBLES:
            caja.addItem(T(etiqueta) if codigo == "auto" else etiqueta, codigo)
        caja.setCurrentIndex(max(0, caja.findData(guardado)))
        caja.currentIndexChanged.connect(
            lambda: (
                self.ajustes.setValue("idioma", caja.currentData()),
                self._decir_reinicio(),
            )
        )
        self.aviso_idioma = QLabel("")
        self.aviso_idioma.setStyleSheet("color: #8a8a8a;")
        fila.addWidget(nombre)
        fila.addWidget(caja)
        fila.addWidget(self.aviso_idioma, 1)
        return fila

    def _decir_reinicio(self):
        self.aviso_idioma.setText(T("idioma_aviso"))

    def _restablecer(self):
        """Devuelve los controles de la cámara a como estaban al abrir esto."""
        for clave, valor in self._de_fabrica.items():
            if self.camara:
                self.camara.control(clave, valor)
            barra, numero = self.barras[clave]
            barra.poner(valor, avisar=False)
            numero.setText(str(valor))
