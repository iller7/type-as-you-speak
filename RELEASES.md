# Cutting a release

1. Update `pyproject.toml`, `src/type_as_you_speak/__init__.py`, the AUR `pkgver`, Fedora `Version`, Flatpak source tag/commit, AppStream release entry, installation-guide examples where needed and CHANGELOG. Use a stable `X.Y.Z` version. Run `uv run --locked python scripts/check-release.py` to catch version drift.
2. Run `make check`, `make build` and the distro package checks. Review dependency/licence changes and complete the real-desktop checklist in CONTRIBUTING.md. Record remaining hardware/platform gaps explicitly.
3. Merge through a reviewed PR with passing checks. Push an annotated `vX.Y.Z` tag pointing to that commit. Publishing is tag-triggered; do not use a production release tag to test CI.
4. The release workflow repeats shared code checks and native package builds, verifies the tag, builds Python distributions with the locked backend, checks source contents, and then publishes wheel/sdist, distro-specific `.deb` files, Fedora RPM/SRPM, `SHA256SUMS` and build attestations. Only the final publish job has release-write credentials. Reruns fail rather than overwrite an existing release or assets; investigate partial drafts before retrying.
5. Verify the release notes, artifact inventory, `sha256sum --check SHA256SUMS` and `gh attestation verify <asset> --repo iller7/type-as-you-speak`. Download and install the matching distro package on a disposable Linux machine.
6. After the tag exists, calculate the GitHub tag archive's SHA256 and update the AUR recipe. Review the diff before submitting to AUR. Flathub, Copr and PyPI publication are separate explicit actions; they are not enabled by this workflow.

Never replace an existing release's artifacts to fix a bad build. Publish a new patch version and document the regression. Users can remove the new package and install the previous matching distro package. Preserve configuration and cached models; do not delete user data as a rollback step. Document any future configuration migration and its backward compatibility before shipping it.

See packaging/README.md for the distribution matrix, ABI constraints and experimental Flatpak status. macOS and Windows CI checks portable code only; no desktop installers are published for them.
