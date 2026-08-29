Name:           iris
Version:        1.0.0
Release:        1%{?dist}
Summary:        A camera app that doesn't lie about what your webcam can do
Summary(es):    Una cámara que no te miente sobre lo que puede dar tu webcam

License:        MIT
URL:            https://github.com/TVTvirus/iris
Source0:        %{url}/archive/v%{version}/%{name}-%{version}.tar.gz

BuildArch:      noarch
BuildRequires:  desktop-file-utils
BuildRequires:  libappstream-glib

Requires:       python3
Requires:       python3-pyqt6
# Solo hace falta para grabar vídeo, pero grabar es la mitad del programa.
# Se pide el binario y no un paquete concreto, para que valga tanto ffmpeg
# como ffmpeg-free.
Requires:       /usr/bin/ffmpeg

%description
Iris takes photos and records video from a webcam, talking to V4L2 directly
through ioctl. No OpenCV, no GStreamer: frames arrive as raw JPEG and Qt
decodes them on its own, so photos can be saved without recompressing and the
image never goes through a colour conversion that washes it out.

It always asks the camera for MJPG, because uncompressed video on a USB 2.0
webcam means 5 fps at 1080p. The status bar shows the frames per second you
are actually getting, not the ones the camera claims.

Mirror and rotation are switches. There is an advanced panel with the camera's
own controls (brightness, contrast, saturation, gain, exposure). The interface
is available in English and Spanish.

%description -l es
Iris saca fotos y graba vídeo de una webcam, hablándole a V4L2 directamente
por ioctl. Sin OpenCV ni GStreamer: los cuadros llegan como JPEG crudo y Qt
los decodifica solo, así que las fotos se pueden guardar sin recomprimir y la
imagen no pasa por una conversión de color que la lave.

Siempre le pide MJPG a la cámara, porque el vídeo sin comprimir en una webcam
USB 2.0 son 5 fps a 1080p. La barra de estado muestra los fotogramas por
segundo que estás recibiendo de verdad, no los que la cámara promete.

El espejo y el giro son interruptores. Hay un panel avanzado con los controles
propios de la cámara (brillo, contraste, saturación, ganancia, exposición). La
interfaz está en español y en inglés.

%prep
%autosetup

%build
# No hay nada que compilar: es Python puro y el icono ya viene como SVG.

%install
install -d %{buildroot}%{_datadir}/%{name}
install -pm 0644 *.py %{buildroot}%{_datadir}/%{name}/
install -pm 0644 iris.svg %{buildroot}%{_datadir}/%{name}/

install -d %{buildroot}%{_bindir}
cat > %{buildroot}%{_bindir}/%{name} <<'EOF'
#!/usr/bin/sh
exec %{__python3} %{_datadir}/%{name}/iris.py "$@"
EOF
chmod 0755 %{buildroot}%{_bindir}/%{name}

install -d %{buildroot}%{_datadir}/icons/hicolor/scalable/apps
install -pm 0644 iris.svg \
    %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/%{name}.svg

desktop-file-install \
    --dir=%{buildroot}%{_datadir}/applications \
    iris.desktop

%check
desktop-file-validate %{buildroot}%{_datadir}/applications/%{name}.desktop
# Que los módulos al menos compilen, que es lo mínimo que se puede exigir
# sin una cámara ni un servidor gráfico dentro del constructor.
%{__python3} -m compileall -q %{buildroot}%{_datadir}/%{name}

%files
%license LICENSE
%doc README.md README.es.md
%{_bindir}/%{name}
%{_datadir}/%{name}/
%{_datadir}/applications/%{name}.desktop
%{_datadir}/icons/hicolor/scalable/apps/%{name}.svg

%changelog
* Fri Aug 28 2026 TVTvirus <86693814+TVTvirus@users.noreply.github.com> - 1.0.0-1
- Primera versión empaquetada
