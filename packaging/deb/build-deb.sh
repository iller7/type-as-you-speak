#!/usr/bin/env bash
# Build on the target distribution: bundled native extensions require its Python ABI.
set -euo pipefail
cd "$(dirname "$0")/../.."
PY="${PYTHON:-python3}"
VER="$("$PY" -c 'import tomllib; print(tomllib.load(open("pyproject.toml", "rb"))["project"]["version"])')"
PYVER="$("$PY" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
ARCH="$(dpkg --print-architecture)"
# shellcheck source=/dev/null
. /etc/os-release
DISTRO="${ID}${VERSION_ID}"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
PYDEPS="opt/type-as-you-speak/pydeps"
WHEELHOUSE="${1:-dist/wheelhouse}"
if [ ! -d "$WHEELHOUSE" ]; then
  bash scripts/prepare-wheelhouse.sh "$WHEELHOUSE"
fi
mkdir -p "$STAGE/$PYDEPS" "$STAGE/usr/bin" "$STAGE/usr/share/doc/type-as-you-speak"
"$PY" -m pip install --no-compile --no-index --no-deps --require-hashes \
  --target "$STAGE/$PYDEPS" --find-links "$WHEELHOUSE" -r "$WHEELHOUSE/requirements.txt"
shopt -s nullglob
wheels=("$WHEELHOUSE"/type_as_you_speak-*.whl)
[ "${#wheels[@]}" -eq 1 ] || { echo 'Expected exactly one application wheel' >&2; exit 1; }
"$PY" -m pip install --no-compile --no-index --no-deps --target "$STAGE/$PYDEPS" "${wheels[0]}"
rm -rf "${STAGE:?}/${PYDEPS:?}/bin"
"$PY" scripts/audit.py "$STAGE/$PYDEPS" --output "$STAGE/usr/share/doc/type-as-you-speak/dependency-audit.json"
PYTHONPATH="$STAGE/$PYDEPS" "$PY" -c 'import numpy, onnxruntime, faster_whisper; from PySide6 import QtWidgets; from type_as_you_speak.cli import main; main(["--version"])'
bash packaging/build-ydotool.sh "$STAGE"
cat > "$STAGE/usr/bin/tays" <<EOF
#!/usr/bin/python${PYVER}
import os
import sys
os.environ["PATH"] = "/opt/type-as-you-speak/bin:" + os.environ.get("PATH", "/usr/bin:/bin")
sys.path.insert(0, "/opt/type-as-you-speak/pydeps")
from type_as_you_speak.cli import main
sys.exit(main())
EOF
chmod 755 "$STAGE/usr/bin/tays"
install -Dm644 data/type-as-you-speak.desktop "$STAGE/usr/share/applications/type-as-you-speak.desktop"
install -Dm644 data/type-as-you-speak.metainfo.xml "$STAGE/usr/share/metainfo/type-as-you-speak.metainfo.xml"
for size in 512 256 128 64 32; do
  install -Dm644 "data/icons/type-as-you-speak-$size.png" "$STAGE/usr/share/icons/hicolor/${size}x${size}/apps/type-as-you-speak.png"
done
install -m644 README.md LICENSE NOTICE COMMERCIAL.md "$STAGE/usr/share/doc/type-as-you-speak/"
mkdir -p "$STAGE/DEBIAN" dist
INSTALLED_SIZE="$(du -sk "$STAGE" | cut -f1)"
{
  printf 'Version: %s\nArchitecture: %s\nInstalled-Size: %s\n' "$VER" "$ARCH" "$INSTALLED_SIZE"
  sed "s/@PYTHON@/python${PYVER}/g" packaging/deb/control
} > "$STAGE/DEBIAN/control"
OUT="dist/type-as-you-speak_${VER}_${DISTRO}_${ARCH}.deb"
dpkg-deb --build --root-owner-group "$STAGE" "$OUT"
echo "Built $OUT (requires Python $PYVER on $DISTRO)"
