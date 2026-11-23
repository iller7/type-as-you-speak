# type-as-you-speak — Fedora / Copr spec
#
# NOTE (first submission): faster-whisper / ctranslate2 are not (yet) packaged
# for Fedora, so this bundles the Python deps under /opt/<name>/pydeps and
# ships a /usr/bin/tays wrapper. If they get packaged, switch to
#   Requires: python3-faster-whisper python3-onnxruntime
# and drop the /opt bundle + wrapper (use a normal %pyproject_install).

Name:           type-as-you-speak
Version:        0.5.1
Release:        1%{?dist}
Summary:        Mac-like, type-as-you-speak dictation for Linux (Wayland & X11) - 100% local

License:        AGPL-3.0-only
URL:            https://github.com/iller7/type-as-you-speak
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz

BuildRequires:  python3-pip
BuildRequires:  python3-setuptools
BuildRequires:  python3-wheel
Requires:       python3
Requires:       ydotool
Requires:       wl-clipboard
Requires:       xclip
Requires:       ffmpeg

%description
Type As You Speak is dictation, not transcription: it is an input method,
like a keyboard. Press the Dictation key, talk, and the words appear in the
focused window as you speak. Everything runs on the machine
(faster-whisper), so audio never leaves it and it works offline after the
first model download. Wayland and X11.

%prep
%setup -q -n %{name}-%{version}

%build
# Pure-Python app; nothing to compile.

%install
# Bundle app + Python deps (Fedora does not package faster-whisper yet).
python3 -m pip install --no-cache-dir --no-build-isolation \
  --target %{buildroot}/opt/%{name}/pydeps .

install -Dm755 /dev/null %{buildroot}/usr/bin/tays
cat > %{buildroot}/usr/bin/tays <<'EOF'
#!/usr/bin/env python3
import sys
sys.path.insert(0, "/opt/type-as-you-speak/pydeps")
from type_as_you_speak.cli import main
sys.exit(main())
EOF

install -Dm644 data/type-as-you-speak.desktop \
  %{buildroot}/usr/share/applications/type-as-you-speak.desktop
install -Dm644 data/type-as-you-speak.metainfo.xml \
  %{buildroot}/usr/share/metainfo/type-as-you-speak.metainfo.xml
for size in 512 256 128 64 32; do
  install -Dm644 data/icons/type-as-you-speak-$size.png \
    %{buildroot}/usr/share/icons/hicolor/${size}x${size}/apps/type-as-you-speak.png
done
install -Dm644 README.md %{buildroot}/usr/share/doc/%{name}/README.md
install -Dm644 LICENSE %{buildroot}/usr/share/doc/%{name}/LICENSE

%files
/opt/%{name}
/usr/bin/tays
/usr/share/applications/type-as-you-speak.desktop
/usr/share/metainfo/type-as-you-speak.metainfo.xml
/usr/share/icons/hicolor/512x512/apps/type-as-you-speak.png
/usr/share/icons/hicolor/256x256/apps/type-as-you-speak.png
/usr/share/icons/hicolor/128x128/apps/type-as-you-speak.png
/usr/share/icons/hicolor/64x64/apps/type-as-you-speak.png
/usr/share/icons/hicolor/32x32/apps/type-as-you-speak.png
/usr/share/doc/%{name}

%changelog
* Sun Nov 22 2026 Faizal Sahebdin <iller7@gmail.com> - 0.5.0-1
- Initial spec: dictation for Linux, 100% local (faster-whisper on CPU).
