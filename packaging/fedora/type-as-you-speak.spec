# Upstream bundled RPM, not a Fedora repository submission; see packaging/README.md.
%global debug_package %{nil}
%global native_system_requires dbus-libs fontconfig libstdc++ mesa-libEGL libglvnd-opengl libglvnd-glx libxkbcommon-x11 xcb-util-cursor

Name:           type-as-you-speak
Version:        0.5.1
Release:        1%{?dist}
Summary:        Local dictation for Linux (Wayland and X11)
License:        AGPL-3.0-only
URL:            https://github.com/iller7/type-as-you-speak
Source0:        type_as_you_speak-%{version}.tar.gz
Source1:        wheelhouse.tar.gz
# Wheel-private DSOs and optional Qt plugins are not system RPM capabilities.
# Their OS dependencies are declared below and checked in a clean runtime image.
%global __requires_exclude_from ^/opt/%{name}/pydeps/.*$
%global __provides_exclude_from ^/opt/%{name}/pydeps/.*$
BuildRequires:  python3-devel
BuildRequires:  python3-pip
BuildRequires:  python3-rpm-macros
BuildRequires:  %{native_system_requires}
Requires:       python(abi) = %{python3_version}
Requires:       %{native_system_requires}
Requires:       ydotool
Requires:       wl-clipboard
Requires:       xclip
Requires:       ffmpeg-free
Requires:       pulseaudio-utils
Requires:       libnotify

%description
Local, streaming speech-to-text dictation using faster-whisper. Includes the
settings window and a locked Python dependency bundle. Audio stays on-device.

%prep
%setup -q -n type_as_you_speak-%{version}
mkdir wheelhouse
tar -xzf %{SOURCE1} -C wheelhouse

%build
# Dependencies and the application wheel were prepared before the offline RPM build.

%install
python3 -m pip install --no-compile --no-index --no-deps --require-hashes \
  --find-links=wheelhouse --target %{buildroot}/opt/%{name}/pydeps -r wheelhouse/requirements.txt
python3 -m pip install --no-compile --no-index --no-deps \
  --target %{buildroot}/opt/%{name}/pydeps wheelhouse/type_as_you_speak-*.whl
rm -rf %{buildroot}/opt/%{name}/pydeps/bin
install -Dm755 /dev/null %{buildroot}/usr/bin/tays
cat > %{buildroot}/usr/bin/tays <<'PY'
#!/usr/bin/python3
import sys
sys.path.insert(0, "/opt/type-as-you-speak/pydeps")
from type_as_you_speak.cli import main
sys.exit(main())
PY
install -Dm644 data/type-as-you-speak.desktop %{buildroot}/usr/share/applications/type-as-you-speak.desktop
install -Dm644 data/type-as-you-speak.metainfo.xml %{buildroot}/usr/share/metainfo/type-as-you-speak.metainfo.xml
for size in 512 256 128 64 32; do
  install -Dm644 data/icons/type-as-you-speak-$size.png %{buildroot}/usr/share/icons/hicolor/${size}x${size}/apps/type-as-you-speak.png
done
install -Dm644 README.md %{buildroot}/usr/share/doc/%{name}/README.md
install -Dm644 LICENSE %{buildroot}/usr/share/licenses/%{name}/LICENSE

%py3_shebang_fix %{buildroot}/opt/%{name}/pydeps

%check
PYTHONPATH=%{buildroot}/opt/%{name}/pydeps python3 -c 'import numpy, onnxruntime, faster_whisper; from PySide6 import QtWidgets; from type_as_you_speak.cli import main; main(["--version"])'

%files
/opt/%{name}
/usr/bin/tays
/usr/share/applications/type-as-you-speak.desktop
/usr/share/metainfo/type-as-you-speak.metainfo.xml
/usr/share/icons/hicolor/*/apps/type-as-you-speak.png
%doc /usr/share/doc/%{name}
%license /usr/share/licenses/%{name}

%changelog
* Tue Nov 24 2026 Faizal Sahebdin <iller7@gmail.com> - 0.5.1-1
- Build from a locked offline wheelhouse and check native imports.
