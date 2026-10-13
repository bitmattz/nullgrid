#!/usr/bin/env bash
# Build every PKGBUILD under pkg/ into the local pacman repo out/repo.
# Runs inside the builder container (see Makefile `repo` target).
set -euo pipefail

src=/src
repo="$src/out/repo"
mkdir -p "$repo"
rm -f "$repo"/*.pkg.tar.* "$repo"/nullgrid.*

for dir in "$src"/pkg/*/; do
    name=$(basename "$dir")
    echo ":: building $name"
    work=$(mktemp -d)
    cp -a "$dir". "$work"
    chown -R builder: "$work"
    (cd "$work" && sudo -u builder PKGDEST="$work/out" makepkg --syncdeps --noconfirm --cleanbuild)
    cp "$work"/out/*.pkg.tar.* "$repo"/
    rm -rf "$work"
done

repo-add --quiet "$repo/nullgrid.db.tar.gz" "$repo"/*.pkg.tar.*
chown -R "${HOST_UID:-0}:${HOST_GID:-0}" "$src/out"
echo ":: repo ready: $(ls "$repo"/*.pkg.tar.* | wc -l) package(s)"
