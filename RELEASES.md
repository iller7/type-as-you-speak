# Cutting a release

The tag **is** the release: push a `vX.Y.Z` tag and GitHub Actions
(`.github/workflows/release.yml`) does the rest of the core channel —
`check` (tag ↔ `pyproject.toml` ↔ `__init__.py`) → `build` (sdist + wheel +
`.deb`) → `release` (GitHub release with the CHANGELOG slice as notes and the
three artifacts attached).

## Checklist

1. **Bump the version in the repo** (all must say the same number):
   - `pyproject.toml` → `version = "X.Y.Z"`
   - `src/type_as_you_speak/__init__.py` → `__version__ = "X.Y.Z"`
   - `CHANGELOG.md` → new `## [X.Y.Z] - YYYY-MM-DD` entry (this becomes the
     release notes)
   - `data/type-as-you-speak.metainfo.xml` → new `<release>` entry
   - `packaging/flatpak/*.json` → `"tag": "vX.Y.Z"`
   - `packaging/fedora/type-as-you-speak.spec` → `Version: X.Y.Z`
2. **Commit and tag:**
   ```sh
   git commit -am "chore: release X.Y.Z"   # or your feature commit(s) first
   git tag -a vX.Y.Z -m "X.Y.Z — short summary"
   git push origin master vX.Y.Z
   ```
3. **Watch the workflow** (3 green jobs: `check`, `build`, `release`):
   ```sh
   gh run list --workflow release --limit 1
   gh run watch <run-id>          # or: https://github.com/iller7/type-as-you-speak/actions
   ```
4. **Verify the release:**
   - `gh release view vX.Y.Z` — notes match the CHANGELOG slice
   - artifacts present: `*.whl`, `*.tar.gz`, `*.deb`
   - spot-check the `.deb` if you like:
     ```sh
     gh release download vX.Y.Z -p '*.deb' -D /tmp/tays-deb
     dpkg-deb -x /tmp/tays-deb/type-as-you-speak_*.deb /tmp/tays-deb/x
     dpkg-deb -c /tmp/tays-deb/type-as-you-speak_*.deb | head
     ```
5. **AUR hash** (hash of the tag tarball — recompute *after* the tag is
   pushed):
   ```sh
   VER=X.Y.Z
   HASH=$(curl -sL https://github.com/iller7/type-as-you-speak/archive/refs/tags/v$VER.tar.gz | sha256sum | cut -d' ' -f1)
   ```
   then update `pkgver` + `sha256sums` in `packaging/aur/PKGBUILD`, commit,
   and push.

## Manual channels (your accounts)

- **Flathub:** open a PR against Flathub with the bumped manifest
  (`packaging/flatpak/*.json`) + icons + metainfo.
- **Copr / Fedora:** build `packaging/fedora/type-as-you-speak.spec` against
  the tag on Copr.
- **PyPI:** not automated on purpose. If you ever want it, publish from the
  released sdist+wheel:
  `python -m twine upload dist/*`.

## What's deliberately NOT automated

- No auto-bump of the version (the number is decided here, in the repo).
- No PyPI upload, no Flathub PR, no Copr build — all need your accounts and
  a deliberate "go".
