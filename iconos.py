"""Iconos dibujados a mano, para no depender del tema del escritorio.

Los iconos de Breeze son oscuros y sobre el fondo negro de esta app no se
verian. Ademas queriamos el aire de la camara de Windows, que no tiene
equivalente en el tema. Son cuatro trazos cada uno: se dibujan en un lienzo
de 100x100 y el widget los escala.
"""

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen


def _lapiz(p, color, grosor=7.0):
    pluma = QPen(color, grosor)
    pluma.setCapStyle(Qt.PenCapStyle.RoundCap)
    pluma.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pluma)
    p.setBrush(Qt.BrushStyle.NoBrush)


def foto(p: QPainter, color):
    """Una camara de fotos: cuerpo, visor y lente."""
    _lapiz(p, color)
    p.drawLine(QPointF(34, 26), QPointF(42, 16))
    p.drawLine(QPointF(42, 16), QPointF(58, 16))
    p.drawLine(QPointF(58, 16), QPointF(66, 26))
    p.drawRoundedRect(QRectF(14, 26, 72, 58), 10, 10)
    p.drawEllipse(QPointF(50, 55), 17, 17)


def video(p: QPainter, color):
    """Una videocamara: el cuerpo y el pico del objetivo."""
    _lapiz(p, color)
    p.drawRoundedRect(QRectF(12, 30, 56, 42), 9, 9)
    camino = QPainterPath(QPointF(74, 44))
    camino.lineTo(88, 34)
    camino.lineTo(88, 68)
    camino.lineTo(74, 58)
    camino.closeSubpath()
    p.drawPath(camino)


def rotar(p: QPainter, color):
    """Una flecha que da la vuelta: gira la imagen un cuarto."""
    _lapiz(p, color)
    arco = QRectF(24, 24, 52, 52)
    camino = QPainterPath()
    camino.arcMoveTo(arco, 20)
    camino.arcTo(arco, 20, 300)
    p.drawPath(camino)
    # punta de flecha donde arranca el arco, arriba a la derecha
    punta = camino.pointAtPercent(0.0)
    p.drawLine(punta, QPointF(punta.x() - 4, punta.y() - 13))
    p.drawLine(punta, QPointF(punta.x() + 11, punta.y() - 3))


def espejo(p: QPainter, color):
    """Dos flechas que se cruzan de lado a lado: cambiar izquierda y derecha.

    La primera version eran dos triangulos con una linea al medio y parecia
    el icono de un altavoz, asi que se cambio por flechas.
    """
    _lapiz(p, color, 7.0)
    p.drawLine(QPointF(18, 38), QPointF(82, 38))
    p.drawLine(QPointF(82, 38), QPointF(70, 27))
    p.drawLine(QPointF(82, 38), QPointF(70, 49))
    p.drawLine(QPointF(82, 66), QPointF(18, 66))
    p.drawLine(QPointF(18, 66), QPointF(30, 55))
    p.drawLine(QPointF(18, 66), QPointF(30, 77))


def micro(p: QPainter, color):
    """Un microfono de mano."""
    _lapiz(p, color)
    p.drawRoundedRect(QRectF(38, 12, 24, 44), 12, 12)
    camino = QPainterPath()
    camino.arcMoveTo(QRectF(26, 30, 48, 48), 200)
    camino.arcTo(QRectF(26, 30, 48, 48), 200, 140)
    p.drawPath(camino)
    p.drawLine(QPointF(50, 78), QPointF(50, 90))


def micro_mudo(p: QPainter, color):
    micro(p, color)
    _lapiz(p, color, 7.0)
    p.drawLine(QPointF(20, 18), QPointF(80, 84))


def mas(p: QPainter, color):
    """Tres puntos: el cajon de los ajustes."""
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(color)
    for x in (26, 50, 74):
        p.drawEllipse(QPointF(float(x), 50.0), 7, 7)


def ojo(p: QPainter, color, iris=None):
    """Un ojo con su iris: la cara del programa.

    La misma forma que el boton grande, para que el icono de la ventana y el
    disparador se reconozcan como la misma cosa.
    """
    from PyQt6.QtGui import QBrush

    camino = QPainterPath(QPointF(6, 50))
    camino.quadTo(QPointF(50, -6), QPointF(94, 50))
    camino.quadTo(QPointF(50, 106), QPointF(6, 50))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(color)
    p.drawPath(camino)

    p.save()
    p.setClipPath(camino)
    p.setBrush(QBrush(iris or QColor(28, 28, 32)))
    p.drawEllipse(QPointF(50, 50), 25, 25)
    p.setBrush(QColor(8, 8, 10))
    p.drawEllipse(QPointF(50, 50), 11, 11)
    p.setBrush(QColor(255, 255, 255, 210))
    p.drawEllipse(QPointF(41, 41), 5, 5)
    p.restore()


DIBUJOS = {
    "foto": foto,
    "video": video,
    "rotar": rotar,
    "espejo": espejo,
    "micro": micro,
    "micro_mudo": micro_mudo,
    "mas": mas,
    "ojo": ojo,
}


def icono_app(lados=(16, 24, 32, 48, 64, 128, 256)):
    """El icono de la aplicacion, dibujado en vez de sacado del tema.

    Es el mismo ojo del boton grande. Sin esto KDE inventa uno con la
    inicial de la organizacion (una W sobre un circulo mostaza). El tema
    Breeze si trae `camera-web`, pero depender de el significa verse
    distinto en cada escritorio, y ademas `QIcon.fromTheme` devuelve nulo
    cuando el tema todavia no esta cargado.

    Lleva su propio fondo redondeado oscuro para que se lea igual de bien
    sobre una barra de titulo clara que sobre una oscura.
    """
    from PyQt6.QtGui import QIcon, QPixmap

    icono = QIcon()
    for lado in lados:
        pm = QPixmap(lado, lado)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.scale(lado / 100.0, lado / 100.0)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(32, 32, 34))
        p.drawRoundedRect(QRectF(2, 2, 96, 96), 22, 22)
        p.translate(11, 11)
        p.scale(0.78, 0.78)
        ojo(p, QColor(255, 255, 255))
        p.end()
        icono.addPixmap(pm)
    return icono
