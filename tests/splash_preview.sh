#!/bin/bash
# Splash preview (make splash): build the Plymouth theme and run it with Plymouth's X11 renderer
# in a virtual X server, in the builder container. Saves out/screens/splash-*.png: the boot
# animation, the disk password prompt, and the shutdown variant. No VM or ISO needed.
set -eu
src=/src
out=$src/out/screens
mkdir -p $out
ls $src/out/repo/nullgrid-fonts-*.pkg.tar.zst >/dev/null 2>&1 \
    && pacman -U --noconfirm --needed $src/out/repo/nullgrid-fonts-*.pkg.tar.zst >/dev/null 2>&1 \
    || echo "[info] nullgrid-fonts not built (make repo): the text uses fallback fonts"
theme=/usr/share/plymouth/themes/nullgrid
python $src/plymouth/generate.py --out $theme >/dev/null
printf '[Daemon]\nTheme=nullgrid\nShowDelay=0\n' > /etc/plymouth/plymouthd.conf
Xvfb :1 -screen 0 1600x900x24 >/dev/null 2>&1 &
export DISPLAY=:1
sleep 1
grab() { xwd -root -display :1 | magick xwd:- $out/splash-$1.png; echo "[info] screenshot out/screens/splash-$1.png"; }
show() {  # mode, then name:seconds pairs
    local mode=$1; shift
    plymouthd --no-daemon --mode=$mode --debug --debug-file=/tmp/plymouth-$mode.log 2>/dev/null &
    sleep 1
    plymouth show-splash
    for shot; do sleep ${shot#*:}; grab ${shot%:*}; done
}
show boot boot-start:0.3 boot:3
plymouth ask-for-password --prompt="Unlock disk cryptroot" >/dev/null 2>&1 &  # (ends with an error when the splash quits)
sleep 1
plymouth display-message --text="fsck: checking /dev/sda2"
sleep 0.5
grab password
plymouth quit; sleep 1
show shutdown shutdown:2
plymouth quit; sleep 1
errors=$(grep -h -i -E "parser? error" /tmp/plymouth-*.log | sort -u || true)
chown -R "${HOST_UID:-0}:${HOST_GID:-0}" $out
[ -z "$errors" ] && echo PASS || { echo "$errors"; echo FAIL; exit 1; }
