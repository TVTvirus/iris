"""Los textos de Iris, en español y en inglés.

Sin ficheros .ts ni `lrelease`: son cincuenta frases y un diccionario las
resuelve sin obligar a nadie a compilar traducciones para cambiar una coma.
Se elige solo según el idioma del sistema, y se puede forzar desde las
opciones avanzadas.

Para añadir un idioma: copiar el bloque "en", traducirlo y sumarlo a TEXTOS.
Si a una clave le falta traducción se cae al inglés, nunca revienta.
"""

from PyQt6.QtCore import QLocale

TEXTOS = {
    "es": {
        "calidad_carpetas": "Calidad y carpetas",
        "girar": "Girar la imagen un cuarto de vuelta",
        "espejo": (
            "Espejo: verte con los lados cambiados.\n"
            "Apagado, ves lo mismo que ve la otra persona."
        ),
        "micro_on": "Grabar también el sonido del micrófono",
        "micro_off": "El vídeo va a salir mudo",
        "micro_cual": "Graba con: {nombre}\nClic para cambiarlo",
        "micro_elegido": "El vídeo se va a grabar con: {nombre}",
        "micro_sistema": "Micrófono del sistema",
        "modo_foto": "Modo foto",
        "modo_video": "Modo vídeo",
        "disparo_foto": "Sacar una foto  (Espacio)",
        "disparo_video": "Empezar a grabar  (Espacio)",
        "disparo_parar": "Detener la grabación  (Espacio)",
        "abriendo": "Abriendo la cámara...",
        "sin_camara": "No encuentro la cámara: {error}",
        "ocupada": "La cámara la está usando {quien}",
        "ocupada_nuestra": " Cerrá esta ventana y usá la otra.",
        "ocupada_otro": " Se abre sola en cuanto la suelte.",
        "no_abre": "No se pudo abrir la cámara: {error}",
        "estado": "MJPG {resolucion} · {fps} fps",
        "estado_girada": " · girada {grados}°",
        "foto_guardada": "Guardada: {archivo}",
        "grabando": "● Grabando  {tiempo}  ·  {archivo}",
        "perdidos": " · {cuantos} cuadros perdidos",
        "cerrando": "Cerrando el archivo...",
        "video_guardado": "Guardado: {archivo} · {segundos}s · {tamano} MB",
        "video_fallo": "La grabación falló (ffmpeg salió con {codigo})",
        "no_graba": "No se pudo grabar: {error}",
        "carpeta_fotos": "Abrir la carpeta de fotos",
        "carpeta_videos": "Abrir la carpeta de vídeos",
        "girada": "Imagen girada {grados}°",
        "derecha": "Imagen derecha otra vez",
        "avanzado": "Avanzado",
        "avanzado_titulo": "Iris · opciones avanzadas",
        "avanzado_aviso": (
            "Estos ajustes hablan directo con la cámara. Si algo se ve raro, "
            "«Volver a lo de fábrica» lo deja como estaba."
        ),
        "ctrl_brillo": "Brillo",
        "ctrl_contraste": "Contraste",
        "ctrl_saturacion": "Saturación",
        "ctrl_ganancia": "Ganancia",
        "ctrl_exposicion": "Exposición",
        "ctrl_no_soportado": "Tu cámara no deja tocar esto",
        "restablecer": "Volver a lo de fábrica",
        "cerrar": "Cerrar",
        "idioma": "Idioma",
        "idioma_auto": "El del sistema",
        "idioma_aviso": "El idioma cambia la próxima vez que abras Iris",
        "calidad_jpeg": "Calidad al recomprimir",
        "calidad_jpeg_ayuda": (
            "Solo se recomprime si la foto sale girada o espejada.\n"
            "Derecha y sin espejo se guarda el JPEG tal cual, sin perder nada."
        ),
        "calidad_video": "Calidad del vídeo",
        "calidad_video_ayuda": "Más a la derecha, mejor imagen y archivo más grande",
        "barra_ayuda": "Rueda o clic izquierdo sube, clic derecho baja",
        "ajustes_camara": "Ajustes de la cámara",
        "ajustes_app": "Ajustes del programa",
    },
    "en": {
        "calidad_carpetas": "Quality and folders",
        "girar": "Rotate the image a quarter turn",
        "espejo": (
            "Mirror: see yourself with the sides swapped.\n"
            "Off, you see what the other person sees."
        ),
        "micro_on": "Also record sound from the microphone",
        "micro_off": "The video will be silent",
        "micro_cual": "Records with: {nombre}\nClick to change it",
        "micro_elegido": "The video will be recorded with: {nombre}",
        "micro_sistema": "System microphone",
        "modo_foto": "Photo mode",
        "modo_video": "Video mode",
        "disparo_foto": "Take a photo  (Space)",
        "disparo_video": "Start recording  (Space)",
        "disparo_parar": "Stop recording  (Space)",
        "abriendo": "Opening the camera...",
        "sin_camara": "Camera not found: {error}",
        "ocupada": "The camera is being used by {quien}",
        "ocupada_nuestra": " Close this window and use the other one.",
        "ocupada_otro": " It will open by itself once released.",
        "no_abre": "Could not open the camera: {error}",
        "estado": "MJPG {resolucion} · {fps} fps",
        "estado_girada": " · rotated {grados}°",
        "foto_guardada": "Saved: {archivo}",
        "grabando": "● Recording  {tiempo}  ·  {archivo}",
        "perdidos": " · {cuantos} frames dropped",
        "cerrando": "Closing the file...",
        "video_guardado": "Saved: {archivo} · {segundos}s · {tamano} MB",
        "video_fallo": "Recording failed (ffmpeg exited with {codigo})",
        "no_graba": "Could not record: {error}",
        "carpeta_fotos": "Open the photos folder",
        "carpeta_videos": "Open the videos folder",
        "girada": "Image rotated {grados}°",
        "derecha": "Image upright again",
        "avanzado": "Advanced",
        "avanzado_titulo": "Iris · advanced options",
        "avanzado_aviso": (
            "These settings talk straight to the camera. If something looks "
            "wrong, «Back to factory» puts it back."
        ),
        "ctrl_brillo": "Brightness",
        "ctrl_contraste": "Contrast",
        "ctrl_saturacion": "Saturation",
        "ctrl_ganancia": "Gain",
        "ctrl_exposicion": "Exposure",
        "ctrl_no_soportado": "Your camera does not allow changing this",
        "restablecer": "Back to factory",
        "cerrar": "Close",
        "idioma": "Language",
        "idioma_auto": "Same as the system",
        "idioma_aviso": "The language changes next time you open Iris",
        "calidad_jpeg": "Recompression quality",
        "calidad_jpeg_ayuda": (
            "Only rotated or mirrored photos get recompressed.\n"
            "Upright and unmirrored, the JPEG is saved as is, losing nothing."
        ),
        "calidad_video": "Video quality",
        "calidad_video_ayuda": "Further right, better image and bigger file",
        "barra_ayuda": "Wheel or left click goes up, right click goes down",
        "ajustes_camara": "Camera settings",
        "ajustes_app": "Program settings",
    },
}

DISPONIBLES = (("auto", "idioma_auto"), ("es", "Español"), ("en", "English"))

_actual = "es"


def elegir(preferido="auto"):
    """Fija el idioma. 'auto' mira el del sistema y cae al inglés."""
    global _actual
    if preferido in TEXTOS:
        _actual = preferido
    else:
        sistema = QLocale.system().name().split("_")[0]
        _actual = sistema if sistema in TEXTOS else "en"
    return _actual


def actual():
    return _actual


def T(clave, **datos):
    """El texto de una clave, con sus huecos rellenos."""
    texto = TEXTOS.get(_actual, {}).get(clave) or TEXTOS["en"].get(clave, clave)
    return texto.format(**datos) if datos else texto
