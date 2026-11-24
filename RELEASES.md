# Cutting a release

1. Update `pyproject.toml`, `src/type_as_you_speak/__init__.py`, the AUR `pkgver`, Fedora `Version`, Flatpak source tag/commit, AppStream release entry, installation-guide examples where needed. Use a stable `X.Y.Z` version. Run `uv run --locked python scripts/check-release.py` to catch version drift.
2. Run `make check`, `make build` and the distro package checks. Review dependency/licence changes and complete the real-desktop checklist in CONTRIBUTING.md. Record remaining hardware/platform gaps explicitly.
3. Merge through a reviewed PR with passing checks. Push an annotated `vX.Y.Z` tag pointing to that commit. Publishing is tag-triggered; do not use a production release tag to test CI.
4. The release workflow repeats shared code checks and native package builds, verifies the tag, builds Python distributions with the locked backend, checks source contents, generates native GitHub release notes from merged PRs, and then publishes wheel/sdist, distro-specific `.deb` files, Fedora RPM/SRPM, `SHA256SUMS` and build attestations. Only the final publish job has release-write credentials. Reruns fail rather than overwrite an existing release or assets; investigate partial drafts before retrying.
5. Verify the release notes, artifact inventory, `sha256sum --check SHA256SUMS` and `gh attestation verify <asset> --repo iller7/type-as-you-speak`. Download and install the matching distro package on a disposable Linux machine.
6. After the tag exists, calculate the GitHub tag archive's SHA256 and update the AUR recipe. Review the diff before submitting to AUR. Flathub, Copr and PyPI publication are separate explicit actions; they are not enabled by this workflow.

Never replace an existing release's artifacts to fix a bad build. Publish a new patch version and document the regression. Users can remove the new package and install the previous matching distro package. Preserve configuration and cached models; do not delete user data as a rollback step. Document any future configuration migration and its backward compatibility before shipping it.

See packaging/README.md for the distribution matrix, ABI constraints and experimental Flatpak status. macOS and Windows CI checks portable code only; no desktop installers are published for them.

## Automatic changelog

GitHub Releases is the canonical changelog. The publish job uses `gh release create --generate-notes`; `.github/release.yml` groups merged PRs by label and includes a catch-all so unlabelled PRs are retained. Use clear Conventional Commit PR titles and link the issue. Historical CHANGELOG.md entries are retained; do not write or copy new entries there. No cloud LLM, extra bot token, release-note service or draft maintenance is required. Version bumps and release promotion remain explicit; this change does not publish on every merge.

Preview notes without creating a tag or release (replace the example tag with the intended next version):

```sh
gh api --method POST repos/iller7/type-as-you-speak/releases/generate-notes -f tag_name=vX.Y.Z -f target_commitish=master --jq .body
```

Inspect the generated PR range and any compatibility warnings before authorising a release. Generated notes list merged PRs; they do not prove completion of real-desktop or GPU testing.

Licence changes apply to new releases. The AUR recipe still pins MIT v0.5.1; change its licence to AGPL-3.0-only together with the new version/source checksum for the first AGPL release. Include LICENSE, NOTICE, the preserved legacy MIT notice and commercial-enquiry information in distributions. Review third-party/model terms and corresponding-source obligations separately; do not replace existing MIT release assets.
