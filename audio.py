"""Los microfonos del sistema, con nombres que se entiendan.

`pactl -f json` devuelve la descripcion en null en esta maquina, y el nombre
crudo de PulseAudio es de la forma
`alsa_input.usb-Generic_Blue_Microphones_201701110001-00.analog-stereo`,
que no se le puede enseñar a nadie. La descripcion legible ("Blue
Microphones") si aparece en la salida de texto, en `device.description`.
"""

import os
import subprocess

from idiomas import T

PREDETERMINADO = "default"

# pactl traduce sus encabezados: en un sistema en español dice "Fuente #" y
# "Nombre:", no "Source #" y "Name:". Se le pide en ingles para poder leerlo.
_ENTORNO = {**os.environ, "LC_ALL": "C", "LANG": "C"}


def microfonos():
    """[(id, nombre)] de las entradas de audio. El primero es el del sistema.

    Se saltan los monitores, que no son microfonos sino la salida de audio
    reflejada, y grabarlos por error es un clasico.
    """
    lista = [(PREDETERMINADO, T("micro_sistema"))]
    try:
        salida = subprocess.run(
            ["pactl", "list", "sources"],
            capture_output=True,
            text=True,
            timeout=5,
            env=_ENTORNO,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return lista

    nombre = descripcion = None
    for linea in salida.splitlines():
        linea = linea.strip()
        if linea.startswith("Source #"):
            nombre = descripcion = None
        elif linea.startswith("Name:"):
            nombre = linea.split(":", 1)[1].strip()
        elif linea.startswith("device.description"):
            descripcion = linea.split("=", 1)[1].strip().strip('"').strip()
        if nombre and descripcion:
            if not nombre.endswith(".monitor"):
                lista.append((nombre, descripcion))
            nombre = descripcion = None
    return lista


def nombre_de(id_micro):
    """El nombre legible de un microfono, o uno de respaldo si ya no esta."""
    for ident, nombre in microfonos():
        if ident == id_micro:
            return nombre
    return T("micro_sistema")


if __name__ == "__main__":
    for ident, nombre in microfonos():
        print(f"{nombre}\n    {ident}")
