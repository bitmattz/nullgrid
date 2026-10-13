#!/bin/bash
# Shell smoke test (make test-shell): run the NULLGRID Quickshell config in a headless Sway inside
# the builder container. Fails on any QML error or warning from our files, checks the IPC
# interface, and saves screenshots to out/screens/shell-*.png (desktop, start menu,
# notifications, lock screen) for a human to look at.
set -u
src=/src
out=$src/out/screens
mkdir -p $out
fail=0
ok()  { echo "[ok] $*"; }
bad() { echo "[FAIL] $*"; fail=1; }

# the UI fonts, if the package has been built (make repo)
ls $src/out/repo/nullgrid-fonts-*.pkg.tar.zst >/dev/null 2>&1 && pacman -U --noconfirm --needed $src/out/repo/nullgrid-fonts-*.pkg.tar.zst >/dev/null 2>&1

export HOME=$(mktemp -d) XDG_RUNTIME_DIR=$(mktemp -d)
chmod 700 $XDG_RUNTIME_DIR
export PYTHONPATH=$src/tools/nullgrid PYTHONDONTWRITEBYTECODE=1 XDG_CONFIG_HOME=$HOME/.config
bin=$(mktemp -d); export PATH=$bin:$PATH
printf '#!/bin/sh\nexec python -m nullgrid "$@"\n' > $bin/nullgrid; chmod +x $bin/nullgrid
mkdir -p $HOME/.config/quickshell && ln -s $src/shell $HOME/.config/quickshell/nullgrid
nullgrid init -q

# Sway refuses to run with file capabilities in a container; a plain copy works.
cp /usr/bin/sway $bin/sway-nocap
cat > $HOME/sway.conf <<CONF
output * mode 1600x900
default_border pixel 2
for_window [app_id="kitty"] floating enable
CONF
export WLR_BACKENDS=headless WLR_RENDERER=pixman WLR_LIBINPUT_NO_DEVICES=1
dbus-run-session -- bash -s <<'SESSION'
set -u
fail=0
ok()  { echo "[ok] $*"; }
bad() { echo "[FAIL] $*"; fail=1; }
out=/src/out/screens
sway-nocap -c $HOME/sway.conf >$HOME/sway.log 2>&1 &
for i in $(seq 100); do ls $XDG_RUNTIME_DIR/wayland-? >/dev/null 2>&1 && break; sleep 0.1; done
export WAYLAND_DISPLAY=$(cd $XDG_RUNTIME_DIR && ls -d wayland-? | head -1) SWAYSOCK=$(ls $XDG_RUNTIME_DIR/sway-ipc.* | head -1)
sleep 1
nullgrid wallpaper apply -q && ok "wallpaper" || bad "wallpaper apply"
quickshell -c nullgrid >$HOME/qs.log 2>&1 &
for i in $(seq 100); do grep -q "Configuration Loaded" $HOME/qs.log && break; sleep 0.1; done
grep -q "Configuration Loaded" $HOME/qs.log && ok "shell loaded" || bad "shell did not load"
sleep 4
# Errors and warnings from our QML: they come from the scene/qml loggers or name a .qml file.
# (Service warnings are expected: the container has no PipeWire, NetworkManager, BlueZ or tray.)
qml_problems() { grep -E "ERROR|WARN" $HOME/qs.log | grep -E " scene| qml|\.qml" ; }
problems=$(qml_problems)
[ -z "$problems" ] && ok "no QML errors or warnings" || { bad "QML problems:"; echo "$problems" | head -20; }

status=$(quickshell -c nullgrid ipc call shell status 2>&1)
[[ $status == theme=crimson-hud\ wm=SWAY* ]] && ok "ipc status: $status" || bad "ipc status: $status"
grim $out/shell-desktop.png

notify-send -a nullgrid -A open=Open "Uplink established" "Node 2.2 is online. 3 packets queued." &
sleep 0.3
notify-send -a battery -u critical "Battery critical" "5% left, plug in the charger." &
sleep 1.5
grim $out/shell-notifications.png
quickshell -c nullgrid ipc call shell openMenu
sleep 1.5
[[ $(quickshell -c nullgrid ipc call shell status) == *menu=true* ]] && ok "start menu opens" || bad "start menu did not open"
grim $out/shell-menu.png
quickshell -c nullgrid ipc call shell closeMenu

nullgrid theme set ice-protocol >/dev/null
sleep 2
[[ $(quickshell -c nullgrid ipc call shell status) == theme=ice-protocol* ]] && ok "restyled live to ice-protocol" || bad "theme change not picked up"
grim $out/shell-ice-protocol.png

if command -v hyprlock >/dev/null; then
    hyprlock --no-fade-in >$HOME/hyprlock.log 2>&1 &
    lock=$!
    sleep 4
    grim $out/shell-lock.png
    kill -9 $lock; wait $lock 2>/dev/null
    ok "lock screen screenshot"
fi
qml_problems | grep -q . && { bad "QML problems after interaction:"; qml_problems | tail -10; }
pkill quickshell; pkill sway-nocap
exit $fail
SESSION
fail=$((fail | $?))
chown -R "${HOST_UID:-0}:${HOST_GID:-0}" $out
for f in $out/shell-*.png; do echo "[info] screenshot ${f#$src/}"; done
[ $fail -eq 0 ] && echo PASS || echo FAIL
exit $fail
