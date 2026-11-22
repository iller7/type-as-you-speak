#!/usr/bin/env bash
# Build a .deb for type-as-you-speak (CPU build).
#
# Produces: dist/type-as-you-speak_<version>_<arch>.deb
#
# Strategy: bundle the pure-Python app plus its Python dependencies under
# /opt/type-as-you-speak/pydeps (so we don't rely on distro Python packages
# that may not exist), and expose a /usr/bin/tays wrapper that puts that dir
# on sys.path. System-level tools (ydotool, wl-clipboard, xclip, ffmpeg) are
# declared as package dependencies.
set -euo pipefail
cd "$(dirname "$0")/../.."

PY="${PYTHON:-python3}"
VER="$("$PY" - <<'EOF'
import tomllib, pathlib
print(tomllib.load(open("pyproject.toml", "rb"))["project"]["version"])
EOF
)"
ARCH="$(dpkg --print-architecture)"
DIST="dist"; STAGE="$(mktemp -d)"
PYDEPS="opt/type-as-you-speak/pydeps"

echo "==> building type-as-you-speak $VER for $ARCH"

mkdir -p "$STAGE/usr/bin" "$STAGE/$PYDEPS" \
         "$STAGE/usr/share/applications" "$STAGE/usr/share/metainfo" \
         "$STAGE/usr/share/doc/type-as-you-speak"

echo "==> collecting Python deps + app into $PYDEPS"
"$PY" -m pip install \
  --no-cache-dir --no-build-isolation --no-warn-script-location \
  --ignore-installed --target "$STAGE/$PYDEPS" .

echo "==> launcher + data files"
cat > "$STAGE/usr/bin/tays" <<'EOF'
#!/usr/bin/env python3
import sys, os
sys.path.insert(0, "/opt/type-as-you-speak/pydeps")
from type_as_you_speak.cli import main
sys.exit(main())
EOF
chmod 755 "$STAGE/usr/bin/tays"

install -m644 data/type-as-you-speak.desktop \
  "$STAGE/usr/share/applications/type-as-you-speak.desktop"
install -m644 data/type-as-you-speak.metainfo.xml \
  "$STAGE/usr/share/metainfo/type-as-you-speak.metainfo.xml"
for size in 512 256 128 64 32; do
  mkdir -p "$STAGE/usr/share/icons/hicolor/${size}x${size}/apps"
  install -m644 "data/icons/type-as-you-speak-$size.png" \
    "$STAGE/usr/share/icons/hicolor/${size}x${size}/apps/type-as-you-speak.png"
done
install -m644 README.md LICENSE "$STAGE/usr/share/doc/type-as-you-speak/"

echo "==> control"
install -d "$STAGE/DEBIAN"
INSTALLED_SIZE=$(( $(du -sk "$STAGE" | cut -f1) + 1 ))
sed -e "/^Package:/a Version: $VER\nArchitecture: $ARCH\nInstalled-Size: $INSTALLED_SIZE" \
    packaging/deb/control > "$STAGE/DEBIAN/control"

echo "==> deb"
mkdir -p "$DIST"
OUT="$DIST/type-as-you-speak_${VER}_${ARCH}.deb"
rm -f "$OUT"
dpkg-deb --build --root-owner-group "$STAGE" "$OUT"
rm -rf "$STAGE"
echo "==> wrote $OUT"
