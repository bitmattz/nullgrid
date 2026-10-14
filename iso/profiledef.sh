#!/usr/bin/env bash
# shellcheck disable=SC2034
# archiso profile for the NULLGRID live ISO. See docs/BUILDING.md.

iso_name="nullgrid"
iso_label="NULLGRID_$(date --date="@${SOURCE_DATE_EPOCH:-$(date +%s)}" +%Y%m)"
iso_publisher="NULLGRID <https://github.com/bitmattz/nullgrid>"
iso_application="NULLGRID Live"
# the release version (VERSION at the repo root); the ISO is out/nullgrid-<version>-x86_64.iso
iso_version="$(cat "$(dirname "${BASH_SOURCE[0]}")/../VERSION")"
install_dir="nullgrid"
bootmodes=('bios.syslinux'
           'uefi.systemd-boot')
pacman_conf="pacman.conf"
airootfs_image_type="squashfs"
# zstd decompresses much faster than xz, which matters on old/slow hardware.
airootfs_image_tool_options=('-comp' 'zstd' '-Xcompression-level' '19' '-b' '1M')
bootstrap_tarball_compression=('zstd' '-c' '-T0' '--auto-threads=logical' '--long' '-19')
file_permissions=(
  ["/etc/shadow"]="0:0:400"
  ["/etc/sudoers.d"]="0:0:750"
  ["/etc/sudoers.d/10-nullgrid-live"]="0:0:440"
  ["/root"]="0:0:750"
  ["/home/nullgrid"]="1000:1000:750"
  ["/home/nullgrid/.zshrc"]="1000:1000:644"
  ["/usr/local/bin/choose-mirror"]="0:0:755"
)
