#!/usr/bin/env bash
set -euo pipefail

# Keep assets editable until every upload succeeds; publishing seals immutable releases.
tag="${1:?release tag required}"
assets="${2:?asset directory required}"
[[ "$tag" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo 'Expected a stable vX.Y.Z tag' >&2; exit 1; }
shopt -s nullglob
files=("$assets"/*)
[ "${#files[@]}" -gt 0 ] || { echo 'No release assets found' >&2; exit 1; }
for file in "${files[@]}"; do
  [ -f "$file" ] || { echo 'Release assets must be regular files' >&2; exit 1; }
done
if ! gh release create "$tag" "${files[@]}" --verify-tag --title "$tag" --generate-notes --draft; then
  draft="$(gh release view "$tag" --json isDraft --jq '.isDraft')"
  [ "$draft" = true ] || { echo 'Refusing to modify a published or unknown release' >&2; exit 1; }
  gh api "repos/{owner}/{repo}/git/ref/tags/$tag" --silent
  remote_assets="$(gh release view "$tag" --json assets --jq '.assets[].name')"
  while IFS= read -r name; do
    [ -n "$name" ] || continue
    case "$name" in */*|.|..) echo 'Unexpected draft asset name' >&2; exit 1 ;; esac
    [ -f "$assets/$name" ] || { echo 'Draft contains an unexpected asset; review it before retrying' >&2; exit 1; }
  done <<< "$remote_assets"
  gh release upload "$tag" "${files[@]}" --clobber
fi
gh release edit "$tag" --draft=false
