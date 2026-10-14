#!/usr/bin/env bash
# Build every PKGBUILD under pkg/ into the local pacman repo out/repo.
# Runs inside the builder container (see Makefile `repo` target).
#
# Packages are built in dependency order, and each one is added to the repo (registered with
# pacman as [nullgrid]) right away, so later packages can depend on earlier ones.
set -euo pipefail

src=/src
repo="$src/out/repo"
order=(nullgrid-base nullgrid-fonts nullgrid-core nullgrid-sfx nullgrid-dash nullgrid-terminal nullgrid-desktop nullgrid-boot nullgrid-installer)

mkdir -p "$repo"
rm -f "$repo"/*.pkg.tar.* "$repo"/nullgrid.*
repo-add --quiet "$repo/nullgrid.db.tar.gz"   # empty db so pacman can sync it
cat >> /etc/pacman.conf <<CONF

[nullgrid]
SigLevel = Optional TrustAll
Server = file://$repo
CONF
pacman -Sy --noconfirm >/dev/null

# The repo code (not only pkg/<name>) goes into each build dir as a source tarball.
tarball=$(mktemp --suffix=.tar)
tar -C "$src" -cf "$tarball" --exclude=__pycache__ --exclude=.pytest_cache \
    tools themes config assets shell plymouth tests/nullgrid tests/nullgrid_dash tests/nullgrid_sfx tests/nullgrid_install iso/airootfs VERSION pkg

names=("${order[@]}")
for dir in "$src"/pkg/*/; do
    name=$(basename "$dir")
    [[ " ${order[*]} " == *" $name "* ]] || names+=("$name")
done

for name in "${names[@]}"; do
    echo ":: building $name"
    work=$(mktemp -d)
    cp -a "$src/pkg/$name/." "$work"
    cp "$tarball" "$work/nullgrid-src.tar"
    chown -R builder: "$work"
    (cd "$work" && sudo -u builder PKGDEST="$work/out" makepkg --syncdeps --noconfirm --cleanbuild)
    cp "$work"/out/*.pkg.tar.* "$repo"/
    repo-add --quiet "$repo/nullgrid.db.tar.gz" "$work"/out/*.pkg.tar.*
    pacman -Sy --noconfirm >/dev/null
    rm -rf "$work"
done

rm -f "$tarball"
chown -R "${HOST_UID:-0}:${HOST_GID:-0}" "$src/out"
echo ":: repo ready: $(ls "$repo"/*.pkg.tar.* | wc -l) package(s)"
