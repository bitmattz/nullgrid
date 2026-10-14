#!/bin/bash
# Shell smoke test (make test-shell): run the NULLGRID Quickshell config in a headless Sway inside
# the builder container. Fails on any QML error or warning from our files, checks the IPC
# interface and the sound daemon (a fake pw-play logs what would be heard), checks that GTK and
# Qt apps take the theme and follow a theme switch live, and saves screenshots to
# out/screens/shell-*.png (desktop, start menu, notifications, apps, lock screen) for a human.
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
export PYTHONPATH=$src/tools/nullgrid:$src/tools/nullgrid-sfx PYTHONDONTWRITEBYTECODE=1 XDG_CONFIG_HOME=$HOME/.config
bin=$(mktemp -d); export PATH=$bin:$PATH
printf '#!/bin/sh\nexec python -m nullgrid "$@"\n' > $bin/nullgrid; chmod +x $bin/nullgrid
printf '#!/bin/sh\nexec python -m nullgrid_sfx "$@"\n' > $bin/nullgrid-sfx; chmod +x $bin/nullgrid-sfx
# no sound card here: this pw-play only notes which sound it was given
printf '#!/bin/sh\nfor a; do f=$a; done; basename "$f" .wav >> $HOME/played.log\n' > $bin/pw-play; chmod +x $bin/pw-play
python $src/assets/sounds/generate.py --out $HOME/.local/share/nullgrid/sounds >/dev/null
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
export QT_QPA_PLATFORMTHEME=qt6ct  # as nullgrid-session sets it
sleep 1
nullgrid wallpaper apply -q && ok "wallpaper" || bad "wallpaper apply"
nullgrid toolkit apply -q
[[ $(gsettings get org.gnome.desktop.interface gtk-theme) == "'NULLGRID'" &&
   $(gsettings get org.gnome.desktop.interface cursor-theme) == "'NULLGRID'" ]] \
    && ok "GTK settings: theme, icons, cursor" || bad "GTK settings not written: $(gsettings list-recursively org.gnome.desktop.interface | grep -E 'theme|font')"
[ -f $HOME/.local/share/icons/NULLGRID/cursors/default ] && ok "icon theme and cursors generated" || bad "no icons/cursors"
nullgrid-sfx daemon --no-startup-sound 2>$HOME/sfx.log &
played() { grep -qx "$1" $HOME/played.log 2>/dev/null; }
for i in $(seq 50); do nullgrid-sfx status >/dev/null 2>&1 && break; sleep 0.1; done
sfx=$(nullgrid-sfx status 2>&1)
[[ $sfx == *'"pack": "neural-link"'*'"sway"'* ]] && ok "sound daemon: $sfx" || bad "sound daemon: $sfx"
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
played notification && played notification_critical && ok "notification sounds" || bad "no notification sounds: $(tr '\n' ' ' < $HOME/played.log)"
quickshell -c nullgrid ipc call shell openMenu
sleep 1.5
[[ $(quickshell -c nullgrid ipc call shell status) == *menu=true* ]] && ok "start menu opens" || bad "start menu did not open"
grim $out/shell-menu.png
quickshell -c nullgrid ipc call shell closeMenu
sleep 0.5
played launcher_open && played launcher_close && ok "menu sounds" || bad "no menu sounds: $(tr '\n' ' ' < $HOME/played.log)"
swaymsg -q workspace 2; sleep 0.5; swaymsg -q workspace 1; sleep 0.5
played workspace_switch && ok "workspace sound (sway events)" || bad "no workspace sound"
nullgrid sound mute on >/dev/null; sleep 0.5
[[ $(nullgrid-sfx status) == *'"enabled": false'* ]] && ok "mute reached the daemon" || bad "mute not picked up: $(nullgrid-sfx status)"
n=$(wc -l < $HOME/played.log); nullgrid-sfx play login; sleep 0.5
[[ $(wc -l < $HOME/played.log) == "$n" ]] && ok "muted: silent" || bad "played while muted"
nullgrid sound mute off >/dev/null

# GTK 3 (Thunar), GTK 4 (zathura) and Qt apps, on a workspace of their own
swaymsg -q workspace 3
rsvg-convert -f pdf -o $HOME/doc.pdf /src/assets/logo/nullgrid.svg
mkdir -p $HOME/Documents $HOME/Downloads $HOME/Music
thunar $HOME >$HOME/thunar.log 2>&1 &
zathura $HOME/doc.pdf >$HOME/zathura.log 2>&1 &
QT_QUICK_CONTROLS_STYLE=Fusion /usr/lib/qt6/bin/qml /src/tests/qt_palette.qml >$HOME/qt.log 2>&1 &
for i in $(seq 100); do
    tree=$(swaymsg -t get_tree)
    [[ $tree == *'"app_id": "thunar"'* && $tree == *'"app_id": "org.pwmt.zathura"'* && $tree == *qt-palette-test* ]] && break
    sleep 0.2
done
sleep 2
grim $out/shell-apps.png
qt_id=$(swaymsg -t get_tree | python -c 'import json,sys
def walk(n):
    if n.get("name") == "qt-palette-test": print(n.get("app_id")); sys.exit()
    for c in n.get("nodes", []) + n.get("floating_nodes", []): walk(c)
walk(json.load(sys.stdin))')
palette() { nullgrid theme palette | awk -v k=$1 '$1 == k { print $2 }'; }
bg=$(palette bg) bg_alt=$(palette bg_alt)
got=$(/src/tests/window_color.py thunar $bg $bg_alt) && ok "GTK 3 window in theme colors ($got)" || bad "Thunar is $got, not $bg"
got=$(/src/tests/window_color.py "$qt_id" $bg) && ok "Qt window in theme colors ($got)" || bad "Qt window is $got, not $bg"
problems=$(grep -h -i -E "theme pars|gtk.css" $HOME/thunar.log $HOME/zathura.log)
[ -z "$problems" ] && ok "GTK themes parse cleanly" || { bad "GTK theme errors:"; echo "$problems" | head; }

nullgrid theme set ice-protocol >/dev/null || bad "nullgrid theme set failed"
sleep 3
[[ $(quickshell -c nullgrid ipc call shell status) == theme=ice-protocol* ]] && ok "restyled live to ice-protocol" || bad "theme change not picked up"
bg=$(palette bg) bg_alt=$(palette bg_alt)
got=$(/src/tests/window_color.py thunar $bg $bg_alt) && ok "GTK app restyled live ($got)" || bad "Thunar still $got after the switch (want $bg)"
got=$(/src/tests/window_color.py "$qt_id" $bg) && ok "Qt app restyled live ($got)" || bad "Qt window still $got after the switch (want $bg)"
[[ $(cat $HOME/.local/share/icons/NULLGRID/scalable/places/folder.svg) == *"$(palette primary)"* ]] \
    && ok "icons recolored" || bad "icons kept the old colors"
grim $out/shell-apps-ice-protocol.png
pkill thunar; pkill zathura; pkill -f qt_palette.qml
swaymsg -q workspace 1
sleep 1
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
nullgrid-sfx quit >/dev/null
pkill quickshell; pkill sway-nocap
exit $fail
SESSION
fail=$((fail | $?))
chown -R "${HOST_UID:-0}:${HOST_GID:-0}" $out
for f in $out/shell-*.png; do echo "[info] screenshot ${f#$src/}"; done
[ $fail -eq 0 ] && echo PASS || echo FAIL
exit $fail
