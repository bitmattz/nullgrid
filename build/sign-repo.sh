#!/usr/bin/env bash
# Sign the packages in out/repo and build the signed [nullgrid] database in out/publish.
# Runs in the builder container (`make publish-repo`), with the signing key at /signing.
set -euo pipefail

export GNUPGHOME=/signing/gnupg
fpr=$(cat /signing/fingerprint)
src=/src/out/repo
out=/src/out/publish

rm -rf "$out"
mkdir -p "$out"
cp "$src"/*.pkg.tar.zst "$out"/
cd "$out"
for pkg in *.pkg.tar.zst; do
    gpg --batch --yes --detach-sign --no-armor --local-user "$fpr" "$pkg"
done
repo-add --quiet --sign --key "$fpr" nullgrid.db.tar.gz *.pkg.tar.zst
# GitHub release assets can't be symlinks: pacman asks for nullgrid.db(.sig), nullgrid.files(.sig)
for f in nullgrid.db nullgrid.files; do
    rm -f "$f" "$f.sig"
    cp "$f.tar.gz" "$f"
    cp "$f.tar.gz.sig" "$f.sig"
done
rm -f nullgrid.db.tar.gz* nullgrid.files.tar.gz*
# check what we're about to publish
for f in *.pkg.tar.zst nullgrid.db nullgrid.files; do
    gpg --batch --verify "$f.sig" "$f" 2>/dev/null || { echo "!! bad signature: $f" >&2; exit 1; }
done
echo ":: signed $(ls *.pkg.tar.zst | wc -l) package(s) and the database with $fpr"
