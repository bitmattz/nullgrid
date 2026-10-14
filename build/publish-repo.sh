#!/usr/bin/env bash
# Upload out/publish (from build/sign-repo.sh) to the GitHub release "repo", which is the
# [nullgrid] pacman repository: Server = https://github.com/bitmattz/nullgrid/releases/download/repo
# Runs on the host (needs gh, logged in). Every publish replaces the whole repository: assets
# that aren't part of it any more (old package versions) are deleted.
set -euo pipefail

gh=${GH:-gh}
command -v "$gh" >/dev/null || gh=$HOME/.local/bin/gh
out=out/publish
tag=repo
[ -f "$out/nullgrid.db" ] || { echo "nothing to publish: run make publish-repo" >&2; exit 1; }

if ! "$gh" release view "$tag" >/dev/null 2>&1; then
    "$gh" release create "$tag" --prerelease --title "NULLGRID package repository" --notes \
"The [nullgrid] pacman repository: signed NULLGRID packages for installed systems.
Not a download for people: installed systems use it through pacman (sudo pacman -Syu or nullgrid update).
See docs/UPDATING.md."
fi
mapfile -t files < <(cd "$out" && ls)
echo ":: uploading ${#files[@]} file(s) to the '$tag' release"
(cd "$out" && "$gh" release upload "$tag" "${files[@]}" --clobber)
# remove what isn't in this publish any more
while read -r name; do
    if [[ ! " ${files[*]} " == *" $name "* ]]; then
        echo ":: removing old asset $name"
        "$gh" release delete-asset "$tag" "$name" --yes
    fi
done < <("$gh" release view "$tag" --json assets --jq '.assets[].name')
echo ":: published: $(grep -c . <<< "$(printf '%s\n' "${files[@]}" | grep '\.pkg\.tar\.zst$')") package(s)"
