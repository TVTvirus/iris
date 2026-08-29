# Iris

*[Léeme en español](README.es.md)*

**A camera app for Linux that doesn't lie to you about what your webcam can do.**

A black window, a big eye that blinks when it takes the picture, and no hidden
settings. Photos and video, with whichever microphone you pick.

![the button is an eye: it blinks when shooting and opens wide while recording](docs/ojo.png)

## Why it exists

Because the three alternatives each failed at something different:

- **Kamoso** is no longer maintained.
- **Webcamoid** grabs the last row of the camera's capability list, which tends
  to be the worst one available: **uncompressed video at 1080p**. On a USB 2.0
  webcam that is **5 fps**, and its pipeline adds visible lag on top.
- **Snapshot** picks the right format, but asks for interpolated 1080p, applies
  limited colour range (16-235) to a stream that arrives in full range (washed
  out image), and mirrors the preview with no way to turn it off. It has **not
  a single setting** for any of that: eleven config keys and none of them is
  resolution, format or mirror.

Iris always asks for **MJPG**, lets you choose the resolution, and mirror and
rotation are switches that remember how you left them.

## The truth about fps

Almost every cheap USB webcam claims 30 fps and doesn't deliver. Iris ships a
meter so you can check yours:

```bash
python3 v4l2cam.py            # lists the modes and measures the real fps
```

On the camera this was written with (a REDRAGON Live Camera), choosing well
versus choosing badly is a **threefold** difference:

| Format | 1920x1080 | 1280x720 | 640x480 |
|---|---|---|---|
| MJPG (compressed) | 30 claimed, **15 real** | 30 claimed, **15 real** | 30 claimed, **15 real** |
| YUYV (uncompressed) | **5** | 10 | 30 |

Uncompressed 1080p video is about 60 MB per second, and a USB 2.0 port gives
you roughly a third of that. The camera has no choice but to drop to five
frames. That is why Iris doesn't even offer you the raw format: it only invites
a bad choice.

And the status bar tells you the fps you are **actually** getting, not the ones
the camera promises.

## What it does

- **Photos**: with mirror and rotation off, it saves the **exact JPEG the camera
  sends, without recompressing**. Not a single bit lost. Flipping or rotating
  does mean touching pixels, and that path recompresses (quality is
  configurable).
- **Video**: H.264 with AAC audio, choosing which of your microphones to use.
- **Mirror**: see yourself with the sides swapped, or the way others see you.
- **Rotation**: a quarter turn at a time, for cameras mounted sideways.
- **It recovers by itself**: if Discord or your browser holds the camera, it
  tells you **who** has it by name and opens as soon as they let go.
- **A single window**: a webcam only accepts one program at a time, so opening
  it twice raises the existing window instead of leaving you a useless black
  one.
- **Several cameras**: they get detected and listed by name. One webcam usually
  exposes several `/dev/videoN` nodes and most of them are metadata, not image;
  only the ones that can actually capture MJPG are offered.
- **Advanced panel** (`Ctrl+Shift+A`): brightness, contrast, saturation, gain
  and exposure straight from the camera's own controls, plus quality and
  language. Deliberately tucked away. Controls your camera doesn't support show
  up greyed out rather than hidden, so you can tell it's the hardware saying no.

Shortcuts: `Space` shoots, `R` rotates, `Ctrl+O` opens the folder.

Photos go to `~/Pictures/Iris` and videos to `~/Videos/Iris` (or whatever your
system calls those folders).

## Languages

English and Spanish, picked from your system locale and switchable in the
advanced panel. Adding one is copying a block in `idiomas.py` and translating
it: no `.ts` files, no `lrelease`.

## How it works inside

No OpenCV, no GStreamer. `v4l2cam.py` talks to the kernel directly through
`ioctl` and hands over frames as **raw JPEG**, which is how they already arrive
from a webcam in MJPG. Qt decodes that on its own, which means:

- no colour conversion layer washing the image out,
- the photo can be saved without recompressing,
- and video is built by piping those same JPEGs into `ffmpeg`.

Latency is kept down by draining the frame queue on every read and using the
newest one. That is the difference between seeing yourself live and seeing
yourself late.

The `ioctl` numbers are not hardcoded: they are computed with the same formula
the kernel uses, from the actual size of each structure. That is why the
structures carry real unions instead of hand-measured padding, so ctypes works
out the alignment by itself and the numbers come out right on 64-bit as well as
on 32-bit or ARM, where a pointer is a different size and the structures change
accordingly.

## Requirements

- Python 3 with **PyQt6**
- **ffmpeg** (only needed to record video)
- A kernel with V4L2, so any Linux

On Fedora:

```bash
sudo dnf install python3-pyqt6 ffmpeg
```

## Install

```bash
git clone https://github.com/TVTvirus/iris.git ~/Documents/iris
cd ~/Documents/iris && ./instalar.sh
```

That puts the launcher in your desktop menu and the `iris` command in your
terminal. To remove it, `./instalar.sh --quitar`.

## Status

It works and gets daily use. What's missing:

- Never tested on anything other than x86-64 Linux with a UVC webcam.
- The code and comments are in Spanish; only the interface is bilingual.

## Licence

MIT.
