#!/usr/bin/env bash
# Boot the newest NULLGRID ISO in QEMU.
#   run-vm.sh [--bios] [--serial] [--gl] [iso]
#     --bios    legacy BIOS boot (default: UEFI via OVMF)
#     --serial  headless; the serial console is attached to stdio
#     --monitor=SOCK  with --serial: emulate a VGA screen and expose the QEMU monitor on a unix
#               socket (the boot test takes screenshots of tty1 and types into it through it)
#     --gl      virtio-gpu with host OpenGL (virgl), needed for smooth Hyprland
# Env: MEM (default 4G), CPUS (default 2)
set -euo pipefail

uefi=1 serial=0 gl=0 iso="" monitor=""
for arg in "$@"; do
    case "$arg" in
        --bios) uefi=0 ;;
        --serial) serial=1 ;;
        --gl) gl=1 ;;
        --monitor=*) monitor=${arg#--monitor=} ;;
        -*) echo "unknown option: $arg" >&2; exit 2 ;;
        *) iso="$arg" ;;
    esac
done

here=$(cd "$(dirname "$0")/.." && pwd)
if [[ -z "$iso" ]]; then
    iso=$(ls -t "$here"/out/nullgrid-*.iso 2>/dev/null | head -n1 || true)
fi
[[ -f "$iso" ]] || { echo "no ISO found; run 'make iso' first" >&2; exit 1; }

command -v qemu-system-x86_64 >/dev/null || {
    echo "qemu-system-x86_64 not found. Debian/Ubuntu: sudo apt install qemu-system-x86 ovmf" >&2
    echo "Arch: sudo pacman -S qemu-desktop edk2-ovmf  (or use 'make test-boot', which runs in Docker)" >&2
    exit 1
}

args=(-m "${MEM:-4G}" -smp "${CPUS:-2}" -machine q35
      -cdrom "$iso" -boot d
      -device virtio-net-pci,netdev=n0 -netdev user,id=n0
      -audiodev none,id=snd0 -device intel-hda -device hda-output,audiodev=snd0)

if [[ -w /dev/kvm ]]; then
    args+=(-enable-kvm -cpu host)
else
    echo "warning: /dev/kvm not usable, falling back to slow emulation (TCG)" >&2
fi

if (( uefi )); then
    code="" vars=""
    for pair in "/usr/share/edk2/x64/OVMF_CODE.4m.fd:/usr/share/edk2/x64/OVMF_VARS.4m.fd" \
                "/usr/share/OVMF/OVMF_CODE_4M.fd:/usr/share/OVMF/OVMF_VARS_4M.fd" \
                "/usr/share/OVMF/OVMF_CODE.fd:/usr/share/OVMF/OVMF_VARS.fd"; do
        if [[ -f "${pair%%:*}" ]]; then code=${pair%%:*} vars=${pair##*:}; break; fi
    done
    [[ -n "$code" ]] || { echo "OVMF firmware not found (install ovmf / edk2-ovmf), or use --bios" >&2; exit 1; }
    state=$(mktemp --suffix=.fd)
    trap 'rm -f "$state"' EXIT
    cp "$vars" "$state"
    args+=(-drive "if=pflash,format=raw,readonly=on,file=$code"
           -drive "if=pflash,format=raw,file=$state")
fi

if (( serial )) && [[ -n "$monitor" ]]; then
    args+=(-display none -vga std -serial stdio -monitor "unix:$monitor,server,nowait")
elif (( serial )); then
    args+=(-display none -vga none -serial stdio -monitor none)
elif (( gl )); then
    args+=(-device virtio-vga-gl -display gtk,gl=on -serial mon:vc)
else
    args+=(-device virtio-vga -display gtk -serial mon:vc)
fi

exec qemu-system-x86_64 "${args[@]}"
