#!/usr/bin/env bash
# Private fallback for distros without ydotool; never installs a service or device rule.
set -euo pipefail
STAGE="${1:?Pass the package staging directory}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
COMMIT=57ba7d0af525e82da2de0e275d169477f293b197
SHA256=f86785b917a297ea06c2e3732c430cab9e71565d45933de0bcb87cf4c2355b49
curl --fail --location --retry 3 "https://github.com/ReimuNotMoe/ydotool/archive/$COMMIT.tar.gz" -o "$WORK/source.tar.gz"
printf '%s  %s\n' "$SHA256" "$WORK/source.tar.gz" | sha256sum --check
mkdir "$WORK/source"
tar -xzf "$WORK/source.tar.gz" --strip-components=1 -C "$WORK/source"
cmake -S "$WORK/source" -B "$WORK/build" -DCMAKE_BUILD_TYPE=Release -DCMAKE_POLICY_VERSION_MINIMUM=3.5
cmake --build "$WORK/build" --target ydotool ydotoold --parallel 2
install -Dm755 "$WORK/build/ydotool" "$STAGE/opt/type-as-you-speak/bin/ydotool"
install -Dm755 "$WORK/build/ydotoold" "$STAGE/opt/type-as-you-speak/bin/ydotoold"
DOC="$STAGE/usr/share/doc/type-as-you-speak/ydotool"
install -Dm644 "$WORK/source/LICENSE" "$DOC/LICENSE"
install -m644 "$WORK/source.tar.gz" "$DOC/source.tar.gz"
printf 'Source: https://github.com/ReimuNotMoe/ydotool\nCommit: %s\nSHA256: %s\nLicense: AGPL-3.0\n' "$COMMIT" "$SHA256" > "$DOC/provenance.txt"
