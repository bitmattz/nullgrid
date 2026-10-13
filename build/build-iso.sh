#!/usr/bin/env bash
# Build the live ISO from iso/ with mkarchiso. Runs inside the builder container.
set -euo pipefail

work=/work            # docker volume, keeps root-owned build trees off the host
out=/src/out

# mkarchiso skips steps whose markers exist, so always start from a clean tree.
rm -rf "${work:?}"/*
mkdir -p "$out"
rm -f "$out"/nullgrid-*.iso

log=$(mktemp)
mkarchiso -v -r -w "$work" -o "$out" /src/iso 2>&1 | tee "$log"
# mkinitcpio errors don't fail mkarchiso, but they mean a broken initramfs.
if grep -q '^==> ERROR' "$log"; then
    echo "!! build reported errors (see '==> ERROR' lines above); refusing to ship this ISO" >&2
    rm -f "$out"/nullgrid-*.iso
    exit 1
fi
chown -R "${HOST_UID:-0}:${HOST_GID:-0}" "$out"
ls -lh "$out"/nullgrid-*.iso
