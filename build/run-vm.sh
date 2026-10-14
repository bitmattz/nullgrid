#!/usr/bin/env bash
# Boot the newest NULLGRID ISO in QEMU.
#   run-vm.sh [--bios] [--serial] [--gl] [iso]
#     --bios    legacy BIOS boot (default: UEFI via OVMF)
#     --serial  headless; the serial console is attached to stdio
#     --monitor=SOCK  with --serial: add a virtio-gpu screen (1600x900, no 3D, like `make run`)
#               and expose the QEMU monitor on a unix socket. The boot test takes screenshots of
#               tty1 and types into it through it.
#     --gl      virtio-gpu with host OpenGL (virgl), needed for smooth Hyprland
#     --vga=TYPE  another QEMU display adapter instead of virtio-gpu, to test other drivers:
#               vmware (vmwgfx, like VirtualBox's VMSVGA), std (bochs), qxl
#     --audio-wav=FILE  record the VM's sound card output to a WAV file (the boot test does)
#     --disk=FILE  attach FILE as a virtio disk (qcow2; created with DISK_SIZE, default 24G, if
#               missing): the target for nullgrid-install
#     --hd      boot the --disk instead of the ISO (an installed system)
# Env: MEM (default 4G), CPUS (default 2), AUDIO (QEMU audio backend for the VM's sound card:
#      default pa when the host has a PulseAudio/PipeWire socket, else none)
set -euo pipefail

uefi=1 serial=0 gl=0 iso="" monitor="" vga="" wav="" disk="" hd=0
for arg in "$@"; do
    case "$arg" in
        --bios) uefi=0 ;;
        --serial) serial=1 ;;
        --gl) gl=1 ;;
        --vga=*) vga=${arg#--vga=} ;;
        --monitor=*) monitor=${arg#--monitor=} ;;
        --audio-wav=*) wav=${arg#--audio-wav=} ;;
        --disk=*) disk=${arg#--disk=} ;;
        --hd) hd=1 ;;
        -*) echo "unknown option: $arg" >&2; exit 2 ;;
        *) iso="$arg" ;;
    esac
done

here=$(cd "$(dirname "$0")/.." && pwd)
if (( hd )); then
    [[ -n "$disk" ]] || { echo "--hd needs --disk=FILE" >&2; exit 2; }
elif [[ -z "$iso" ]]; then
    iso=$(ls -t "$here"/out/nullgrid-*.iso 2>/dev/null | head -n1 || true)
fi
(( hd )) || [[ -f "$iso" ]] || { echo "no ISO found; run 'make iso' first" >&2; exit 1; }

command -v qemu-system-x86_64 >/dev/null || {
    echo "qemu-system-x86_64 not found. Debian/Ubuntu: sudo apt install qemu-system-x86 ovmf" >&2
    echo "Arch: sudo pacman -S qemu-desktop edk2-ovmf  (or use 'make test-boot', which runs in Docker)" >&2
    exit 1
}

# Sound card: Intel HDA. Its output goes to the host's sound server, a WAV file, or nowhere.
if [[ -n "$wav" ]]; then
    audio="wav,id=snd0,path=$wav"
elif [[ -n "${AUDIO:-}" ]]; then
    audio="$AUDIO,id=snd0"
elif (( ! serial )) && [[ -S "${XDG_RUNTIME_DIR:-/nonexistent}/pulse/native" ]]; then
    audio="pa,id=snd0"
else
    audio="none,id=snd0"
fi

args=(-m "${MEM:-4G}" -smp "${CPUS:-2}" -machine q35
      -device virtio-net-pci,netdev=n0 -netdev user,id=n0
      -audiodev "$audio" -device intel-hda -device hda-output,audiodev=snd0)

if [[ -n "$disk" ]]; then
    [[ -f "$disk" ]] || qemu-img create -q -f qcow2 "$disk" "${DISK_SIZE:-24G}"
    args+=(-drive "file=$disk,if=virtio,format=qcow2")
fi
if (( hd )); then
    args+=(-boot c)
else
    args+=(-cdrom "$iso" -boot d)
fi

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
    if [[ -n "$vga" ]]; then display=(-vga "$vga"); else display=(-vga none -device virtio-vga,xres=1600,yres=900); fi
    args+=(-display none "${display[@]}"
           -serial stdio -monitor "unix:$monitor,server,nowait")
elif (( serial )); then
    args+=(-display none -vga none -serial stdio -monitor none)
elif (( gl )); then
    args+=(-device virtio-vga-gl -display gtk,gl=on -serial mon:vc)
else
    if [[ -n "$vga" ]]; then args+=(-vga "$vga"); else args+=(-device virtio-vga); fi
    args+=(-display gtk -serial mon:vc)
fi

exec qemu-system-x86_64 "${args[@]}"
