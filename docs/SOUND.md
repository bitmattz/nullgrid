# Sound

NULLGRID plays short UI sounds for desktop and system events: a chirp when the launcher opens,
a soft confirm at login, an alert for critical notifications. Every sound is synthesized by
`assets/sounds/generate.py`; nothing is sampled or downloaded.

```sh
nullgrid sound list                # sound packs (* = active)
nullgrid sound set minimal-ops     # switch pack (the daemon picks it up at once)
nullgrid sound test notification   # play one event's sound; `test all` plays every one
nullgrid sound mute                # toggle; or: mute on / mute off
nullgrid sound volume 0.4          # master volume, 0-1 (no argument: print it)
```

## How it fits together

```
 Hyprland socket2 / swaymsg subscribe ──┐
 udevadm monitor (USB, power supply) ───┤
 /sys/class/power_supply (60 s poll) ───┼──> nullgrid-sfx daemon ──> pw-play (PipeWire)
 the shell (Quickshell Socket) ─────────┤      reads generated/sfx.json,
 nullgrid-sfx play EVENT ───────────────┤      SIGHUP re-reads it
 zsh hooks (zsh/net/socket) ────────────┘
```

- **`nullgrid-sfx daemon`** starts with the session (Hyprland and Sway autostart) and ends with
  it. It sleeps in `select()` until an event arrives, then starts `pw-play` for the sound and
  doesn't wait for it, so nothing that sends an event is ever held up. Idle CPU is zero; it uses
  about 20 MB of RAM.
- It listens on `$XDG_RUNTIME_DIR/nullgrid-sfx.sock`, one command per line: `play EVENT`,
  `playwait EVENT` (answers `done` once the sound is over), `status`, `reload`, `quit`.
- Its settings come from `~/.config/nullgrid/generated/sfx.json`, which `nullgrid` writes from
  `[sound]` like any other generated file. When that file changes, the daemon gets SIGHUP and
  re-reads it, so `nullgrid sound ...` and edits applied with `nullgrid theme reload` take
  effect immediately.
- Limits: the same event at most once per 80 ms (a burst of windows opening makes one sound),
  and at most 4 sounds at once.
- `nullgrid-sfx play EVENT` hands the event to the daemon. If no daemon is running (on a TTY,
  for instance), it applies the same rules and plays the sound itself.
- Log: `~/.local/state/nullgrid/sfx.log`. State: `nullgrid-sfx status`.

## Events

| Event | Comes from | On by default |
|---|---|---|
| `boot` | the first desktop session since the machine started | yes |
| `login` | each desktop session after that | yes |
| `logout`, `shutdown` | `nullgrid-power` (start menu power buttons, `SUPER+SHIFT+E`); it waits for the sound to end before acting | yes |
| `workspace_switch`, `window_open`, `window_close` | compositor events | yes |
| `window_focus` | compositor events | no |
| `launcher_open`, `launcher_close` | the start menu; on Hyprland also fuzzel (`SUPER+D`) | yes |
| `menu_hover` | the pointer moving over start-menu entries | no |
| `button_click` | dock, start menu, bar toggles, notification actions | yes |
| `notification`, `notification_critical` | the shell's notification server (silent when the sender sets the `suppress-sound` hint) | yes |
| `volume_change`, `brightness_change` | the hardware keys (`nullgrid-media`) and scrolling on the bar's controls | yes |
| `usb_connect`, `usb_disconnect` | udev | yes |
| `charger_plug` | udev: the mains adapter goes online | yes |
| `battery_low` | the battery drops to 15 % and again to 5 % while discharging | yes |
| `screenshot`, `error` | `nullgrid-screenshot` (`error` when the capture fails); `error` also when Enter in the start menu matches nothing | yes |
| `lock`, `unlock` | `nullgrid-lock` (`SUPER+CTRL+L`, the start menu's LOCK) | yes |
| `terminal_bell` | kitty's bell (`command_on_bell`) | no |
| `command_done` | zsh: a command that ran 10 s or longer finished | no |
| `command_failed` | zsh: a command failed (not counting Ctrl-C / Ctrl-Z) | no |

Switch any of them in `nullgrid.toml`:

```toml
[sound.events]
window_open = { volume = 0.5 }           # quieter
command_failed = { enabled = true }      # on
notification = { enabled = false }       # off
```

The loudness of an event is `volume` × the event's `volume` × the pack's own level for it, times
`[sound.quiet_hours] volume` during quiet hours (`start`/`end` may cross midnight). The zsh hooks
and kitty's bell are set when a shell or kitty starts, so after switching those three events,
open a new terminal.

## Packs

Two packs ship with the `nullgrid-sfx` package (`/usr/share/nullgrid/sounds/`):

- **neural-link** (default): glitchy digital blips, data chirps and soft synth confirms. Uses FM
  bells, bit-crushed pulses, bursts of short chirps on an A-minor pentatonic scale, a small reverb.
- **minimal-ops**: very subtle clicks and low beeps; quieter overall, no reverb.

All sounds are 48 kHz mono WAV, 50-600 ms long, loudness-matched within a pack: UI ticks sit
8 dB below normal events and alerts 3 dB above.

### Your own pack

Put a directory in `~/.local/share/nullgrid/sounds/<name>/` (a user pack with the same name as
a system pack replaces it):

```toml
# ~/.local/share/nullgrid/sounds/my-pack/pack.toml
[meta]
name = "my-pack"            # must match the directory name
description = "..."

[events]                    # event = file, or { file = ..., volume = 0-1 }
login = "hello.ogg"
notification = { file = "ping.wav", volume = 0.7 }
```

Files can be `.wav`, `.ogg`, `.oga` or `.flac`. An event the pack leaves out is silent. Then
`nullgrid sound set my-pack`; `nullgrid doctor` reports problems with the pack.

### Changing the built-in sounds

Every sound is a short recipe in `assets/sounds/generate.py` (oscillators, envelopes, filters,
bit-crusher, reverb, all in numpy). Edit a recipe, then:

```sh
make sounds                                   # writes out/sounds/<pack>/ (Docker, has numpy)
nullgrid sound test login --pack neural-link  # from a git checkout, plays out/sounds
```

The output is deterministic (each sound has its own seed), so changing one recipe never changes
another. `make test` checks every sound's length, level, and that it starts and ends silent.

## Troubleshooting

- `nullgrid doctor` checks the pack, the player (`pw-play`), PipeWire and the daemon.
- No sound at all: `wpctl status` should list an output device; `systemctl --user status
  pipewire wireplumber`. In QEMU, `make run` passes the guest's sound to the host's PulseAudio or
  PipeWire (`AUDIO=none make run` turns it off). In VirtualBox, enable audio output in the VM
  settings.
- The daemon isn't running (`nullgrid-sfx status` says so): start it with
  `nullgrid-sfx daemon &`; a new one replaces an old one.
