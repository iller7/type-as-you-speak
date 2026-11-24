# Linux distribution

KDE Plasma and GNOME are desktops; Debian/Ubuntu, Arch and Fedora are distributions. The app needs both distro package checks and desktop/session tests. We follow KDE's [build-before-publication approach](https://develop.kde.org/docs/packaging/flatpak/publishing/) and Python's [downstream packaging guidance](https://packaging.python.org/en/latest/discussions/downstream-packaging/): complete source archives, offline build inputs, declared dependencies and tests against installed artifacts.

| Channel                          | Build path                               | Automated scope                                                                                     | Publication                                                      |
| -------------------------------- | ---------------------------------------- | --------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------- |
| Debian 12/13, Ubuntu 24.04/26.04 | `packaging/containers/debian.Dockerfile` | Native interpreter, locked dependencies, vulnerability audit, install, imports, offscreen Qt launch | Tagged GitHub release assets                                     |
| Fedora 44/45                     | `packaging/containers/fedora.Dockerfile` | Offline RPM/SRPM, native ABI, audit, install, imports, offscreen Qt and installed CPU recognition   | Tagged GitHub release assets; Copr is separate                   |
| Arch                             | `packaging/aur/PKGBUILD`                 | Non-root makepkg build from the current checkout                                                    | AUR submission and runtime dependency validation remain separate |
| Flatpak                          | `packaging/flatpak/`                     | Prototype with pinned source commits and an offline dependency generator                            | Experimental; not a release asset or a Flathub-ready submission  |

These are CI targets, not a claim that every desktop/hardware combination has been tested. Native package jobs currently target x86-64. PySide6's current ARM64 Linux wheel needs a newer glibc than some target distributions; do not advertise ARM64 packages until native builds are added and tested.

## Debian and Ubuntu

```sh
make package-deb
# Or build on another target distribution:
docker build --build-arg BASE_IMAGE=debian:13-slim -f packaging/containers/debian.Dockerfile --output type=local,dest=dist/packages/debian13 .
```

CI uses digest-pinned images. Artifacts include the distro and architecture in their filename. A `.deb` built for Ubuntu 24.04 is not a generic Debian/Ubuntu binary: the bundle contains native extensions and the launcher requires the exact Python minor it was built against. Dependencies include the system audio/clipboard tools and Qt libraries. The application and settings window are included; NVIDIA runtime wheels are not bundled. Debian 13 does not provide ydotool, so Debian/Ubuntu packages include a private fallback client/daemon built from a checksum-verified upstream commit. The wrapper uses the pinned private client/daemon, so an older distro ydotool cannot override the tested command-line interface. Existing daemons are reused only through the configured socket. Its AGPL licence, complete source archive and provenance are included under `/usr/share/doc/type-as-you-speak/ydotool/`. No service is enabled and no input-device permissions are granted by installing the package.

`scripts/prepare-wheelhouse.sh` exports hashed GUI/runtime requirements from `uv.lock`, downloads only compatible wheels and adds the locally built application wheel. `build-deb.sh` installs offline and audits the installed third-party versions before packaging. The JSON advisory report is included under `/usr/share/doc/type-as-you-speak/`. Model weights are downloaded separately on first use and are not part of the dependency audit.

## Fedora

```sh
make package-rpm
```

The upstream RPM bundles native Python wheels under `/opt/type-as-you-speak/pydeps`. Its source RPM includes the exact offline wheelhouse; `rpmbuild` performs no dependency downloads. It requires the target distro's `python(abi)` and includes third-party distribution metadata/licences. The release gate audits the installed RPM bundle. RPM does not treat the private wheel libraries or optional Qt plugins as public system capabilities: their dependency scanning is scoped out for this private directory, with OS dependencies declared explicitly and checked by installing into a clean Fedora image.

This is an upstream distribution RPM, not a claim of compliance for inclusion in Fedora's repositories. Fedora acceptance requires separately packaging the inference dependencies, removing the bundled wheels and satisfying its [Python packaging policy](https://docs.fedoraproject.org/en-US/packaging-guidelines/Python/). Copr publication also requires an owner/project and a reviewed source RPM.

## Arch

The PKGBUILD uses `python -m build` and `python -m installer`; Python runtime dependencies are supplied by Arch or AUR. Do not assume every inference dependency is available in the official repositories. Install/review those dependencies before building. The current supported interpreter range is 3.11–3.14; an Arch Python transition outside that range needs compatibility work first.

CI builds this checkout with a temporary local source archive and calculated checksum, so it cannot accidentally validate an old release. The published PKGBUILD retains a real release-tarball checksum; update it only after the new tag exists. The non-root package-build check does not certify microphone, GPU or GUI runtime operation.

## Flatpak

The checked-in manifest is a prototype template. It pins git commits, uses app-private configuration/cache and exposes only the host ydotool socket instead of all input devices. A host ydotool daemon is still required; users must not weaken socket permissions to share it across users.

Generate dependencies on Linux x86-64 with Python 3.13 (the Freedesktop 25.08 runtime's Python):

```sh
uv sync --locked --python 3.13 --extra gui
bash scripts/prepare-wheelhouse.sh dist/flatpak-wheelhouse
uv run --locked python scripts/prepare-flatpak.py dist/flatpak-wheelhouse
flatpak-builder --user --force-clean _build/flatpak dist/flatpak/io.github.iller7.TypeAsYouSpeak.json
```

The generator verifies downloaded dependency hashes against PyPI and produces explicit source URLs/hashes. It packages the current local application wheel; build commands use `--no-index --no-deps` and cannot fetch missing dependencies. The ungenerated template is not a standalone build input.

Before shipping: supply and verify `ffmpeg`/`pactl` runtime tools, validate the generated manifest and AppStream identity with Flathub tooling, test the host socket integration on KDE/GNOME, and assess a RemoteDesktop-portal input backend. Native CLI access to `/dev/uinput` does not establish that a sandbox can use it. Flatpak is deliberately excluded from tagged publishing until these checks pass; removing that gate requires desktop evidence.

## Release evidence

Container checks cannot exercise a real microphone, compositor permissions, focus, global shortcuts or GPU inference. Complete the desktop checklist in CONTRIBUTING.md before describing a release as desktop-tested. The source archive carries packaging scripts, icons, metadata, configuration, tests and the lockfile so downstream packagers can reproduce the build inputs.

## CI artifacts

Pull requests still build, install and audit the native packages, but do not upload large binaries. To obtain test packages, run the CI workflow manually on the desired branch; those package artifacts expire after one day. Tag-triggered release builds also upload packages for the publish job, which attaches them to the GitHub release. This limits temporary storage on GitHub Free. Existing artifacts are not deleted by this policy change.

The AUR recipe currently downloads the published MIT v0.5.1 source and retains MIT metadata for that source. Update its licence, version and checksum together when publishing the first AGPL release. The Arch CI source override smoke-builds the current checkout; it does not publish an AUR package.

### Fedora 45 native ONNX provider

The default container is Fedora 45; the CI matrix also retains Fedora 44 through an explicit base-image override. `make package-rpm` writes to `dist/packages/fedora/`; RPM filenames distinguish their Fedora release. The expected-distro check in CI prevents a future base-image upgrade from being tested under an old lane name.

For Python 3.15, the build creates a system-site-enabled build environment and deliberately omits the ONNX wheel from the private wheelhouse. The spec declares `python3-onnxruntime >= 1.26` as a build/runtime dependency on Fedora 45+, and records the provider's build NEVRA under `/usr/share/doc/type-as-you-speak/native-onnx-build.txt`. Other dependencies stay in the locked offline wheelhouse. Standard bundles still select ONNX Runtime 1.32; the lower declared floor reflects the native API version now tested.

The build validates runtime-visible dependencies with `python -m pip check`; uv's own package check intentionally does not include inherited system packages. Audit the installed bundle plus the native ONNX Python dependency closure with `scripts/audit.py --system-package onnxruntime`; missing providers and native/bundled shadowing fail closed. The Python advisory scan remains separate from Fedora's OS-library update/advisory process.

The verification stage checks clean RPM installation and offscreen Qt, then executes the real-model EOF recognition cases against installed application code. It compares the ONNX version seen in the runtime image with the verification environment. The RPM/SRPM is exported only after those checks and the strict audit pass. This remains an upstream bundled RPM, not a Fedora-repository compliance claim; publication remains explicit.

### Strict offline runtime dependency

The default strict-offline process guard requires `libseccomp2` in DEB builds/runtime and `libseccomp` in Fedora builds/runtime. It fails closed if unavailable. The pinned legacy AUR recipe still describes the old MIT release; add this runtime dependency together with its first AGPL release version/licence/checksum update. Experimental Flatpak must also verify the library and filter availability inside its sandbox before publication; its GUI model-download capability does not establish strict engine protection.
