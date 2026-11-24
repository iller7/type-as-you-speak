#!/usr/bin/env bash
set -euo pipefail

# Keep assets editable until every upload succeeds; publishing seals immutable releases.
tag="${1:?release tag required}"
assets="${2:?asset directory required}"
gh release create "$tag" "$assets"/* --verify-tag --title "$tag" --generate-notes --draft
gh release edit "$tag" --draft=false
