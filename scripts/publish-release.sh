#!/usr/bin/env bash
set -euo pipefail

# release-please creates the Release — as a DRAFT, with the release notes —
# when the release PR merges. This script only supplies the verified assets
# and seals the draft: a release goes public only when every asset is on it.
# If no release exists for the tag at all (e.g. a manually cut tag), one is
# created here as a draft first; a published release is never modified.
tag="${1:?release tag required}"
assets="${2:?asset directory required}"
[[ "$tag" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo 'Expected a stable vX.Y.Z tag' >&2; exit 1; }
shopt -s nullglob
files=("$assets"/*)
[ "${#files[@]}" -gt 0 ] || { echo 'No release assets found' >&2; exit 1; }
for file in "${files[@]}"; do
  [ -f "$file" ] || { echo 'Release assets must be regular files' >&2; exit 1; }
done

state="$(gh release view "$tag" --json isDraft --jq '.isDraft' 2>/dev/null || echo missing)"
case "${state}" in
  missing)
    gh release create "$tag" --verify-tag --title "$tag" --generate-notes --draft
    ;;
  true)
    ;;
  *)
    echo 'Refusing to modify a published or unknown release' >&2
    exit 1
    ;;
esac

# A draft carrying assets we do not recognise is reviewed, never clobbered.
remote_assets="$(gh release view "$tag" --json assets --jq '.assets[].name')"
while IFS= read -r name; do
  [ -n "$name" ] || continue
  case "$name" in */*|.|..) echo 'Unexpected draft asset name' >&2; exit 1 ;; esac
  [ -f "$assets/$name" ] || { echo 'Draft contains an unexpected asset; review it before retrying' >&2; exit 1; }
done <<< "$remote_assets"

gh release upload "$tag" "${files[@]}" --clobber

# Seal: only now that every verified asset is uploaded does the release exist
# for the public.
gh release edit "$tag" --draft=false
