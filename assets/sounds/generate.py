#!/usr/bin/env python3
"""Generate the NULLGRID sound packs: every sound is synthesized here, nothing is sampled.

  generate.py [--out DIR] [--pack NAME]... [--list]

Writes DIR/<pack>/pack.toml plus one .wav per event (48 kHz, 16-bit mono, 50-600 ms, peak
loudness-matched). Default DIR: out/sounds in the repo. The output is deterministic: each sound has
its own random seed, so changing one recipe never changes the others.

Packs:
  neural-link  glitchy digital blips, data chirps, soft synth confirms
  minimal-ops  very subtle clicks and low beeps

To tweak a sound, edit its recipe below and run the script again; `nullgrid sound test <event>`
plays it. A recipe is a function (rng) -> numpy array of samples; every sound is then matched to
a loudness target (ticks quiet, alerts louder), so the pack stays balanced.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np

SR = 48_000
MIN_MS, MAX_MS = 50, 600
ROOT = Path(__file__).resolve().parents[2]

Signal = np.ndarray
Recipe = Callable[[np.random.Generator], Signal]


# =========================================================================== building blocks
def samples(sec: float) -> int:
    return max(1, int(round(sec * SR)))


def midi(note: float) -> float:
    return 440.0 * 2 ** ((note - 69) / 12)


def _curve(freq, n: int) -> Signal:
    """Hz as a constant, a (start, end) exponential glide, or a per-sample array."""
    if isinstance(freq, tuple):
        a, b = freq
        return a * (b / a) ** np.linspace(0, 1, n)
    if isinstance(freq, np.ndarray):
        return np.resize(freq, n)
    return np.full(n, float(freq))


def tone(freq, sec: float, shape: str = "sine", *, fm: tuple[float, float] | None = None,
         detune: float = 0.0) -> Signal:
    """An oscillator. shape: sine, triangle, square (band-limited), soft (rounded square),
    saw (band-limited), pulse (naive square: aliases on purpose, the "8-bit" grit).
    fm=(ratio, index) adds a sine modulator whose depth decays over the note (bell-like).
    detune (cents) mixes in a second, slightly detuned oscillator for width."""
    n = samples(sec)
    f = _curve(freq, n)
    if detune:
        return 0.5 * (tone(f, sec, shape, fm=fm) + tone(f * 2 ** (detune / 1200), sec, shape, fm=fm))
    phase = 2 * np.pi * np.cumsum(f) / SR
    if fm:
        ratio, index = fm
        phase = phase + index * np.linspace(1, 0.1, n) * np.sin(phase * ratio)
    if shape == "sine":
        return np.sin(phase)
    if shape == "triangle":
        return 2 / np.pi * np.arcsin(np.sin(phase))
    if shape == "soft":
        return np.tanh(3 * np.sin(phase)) / np.tanh(3)
    if shape == "pulse":
        return np.sign(np.sin(phase))
    top = max(1, int(16_000 / f.max()))  # harmonics below 16 kHz: no aliasing
    if shape == "square":
        return 4 / np.pi * sum(np.sin(k * phase) / k for k in range(1, top + 1, 2))
    if shape == "saw":
        return 2 / np.pi * sum((-1) ** (k + 1) * np.sin(k * phase) / k for k in range(1, top + 1))
    raise ValueError(f"unknown shape {shape!r}")


def noise(rng: np.random.Generator, sec: float) -> Signal:
    return rng.standard_normal(samples(sec))


def perc(sec: float, attack: float = 0.002, curve: float = 3.0) -> Signal:
    """Percussive envelope: quick rise, then (1-x)^curve down to exactly zero."""
    n = samples(sec)
    a = min(samples(attack), n - 1)
    rise = np.sin(np.linspace(0, np.pi / 2, a)) ** 2
    fall = (1 - np.linspace(0, 1, n - a)) ** curve
    return np.concatenate([rise, fall])


def adsr(sec: float, attack: float = 0.005, decay: float = 0.05, sustain: float = 0.6,
         release: float = 0.08) -> Signal:
    n = samples(sec)
    a, d, r = samples(attack), samples(decay), samples(release)
    s = max(0, n - a - d - r)
    env = np.concatenate([np.linspace(0, 1, a), np.linspace(1, sustain, d), np.full(s, sustain),
                          np.linspace(sustain, 0, r)])
    return np.resize(env, n) if len(env) >= n else np.pad(env, (0, n - len(env)))


def filt(x: Signal, lo: float | None = None, hi: float | None = None, order: int = 2) -> Signal:
    """Zero-phase high/low/band-pass with Butterworth-shaped magnitude, done in the frequency
    domain (padded, so the tail doesn't wrap around to the start)."""
    pad = 4096
    spec = np.fft.rfft(np.concatenate([x, np.zeros(pad)]))
    f = np.fft.rfftfreq(len(x) + pad, 1 / SR)
    gain = np.ones_like(f)
    if lo:
        r = (np.maximum(f, 1e-9) / lo) ** (2 * order)
        gain *= np.sqrt(r / (1 + r))
    if hi:
        gain *= 1 / np.sqrt(1 + (f / hi) ** (2 * order))
    return np.fft.irfft(spec * gain, len(x) + pad)[: len(x)]


def crush(x: Signal, bits: int = 6, hold: int = 4) -> Signal:
    """Bit crusher: sample-and-hold every `hold` samples, then quantize to `bits` bits."""
    held = np.repeat(x[::hold], hold)[: len(x)]
    steps = 2 ** (bits - 1)
    return np.round(held * steps) / steps


def _comb(x: Signal, d: int, g: float) -> Signal:
    # y[n] = x[n] + g*y[n-d], computed one block of d samples at a time (each block only
    # needs the finished block before it, so numpy can do the block in one go)
    y = x.copy()
    for start in range(d, len(y), d):
        end = min(start + d, len(y))
        y[start:end] += g * y[start - d:end - d]
    return y


def _allpass(x: Signal, d: int, g: float) -> Signal:
    # y[n] = -g*x[n] + x[n-d] + g*y[n-d]
    y = -g * x + np.concatenate([np.zeros(d), x[:-d]])
    for start in range(d, len(y), d):
        end = min(start + d, len(y))
        y[start:end] += g * y[start - d:end - d]
    return y


def reverb(x: Signal, tail: float = 0.15, mix: float = 0.25, size: float = 1.0,
           decay: float = 0.6) -> Signal:
    """Small Schroeder reverb (4 combs, 2 allpasses). Adds `tail` seconds."""
    x = np.concatenate([x, np.zeros(samples(tail))])
    wet = sum(_comb(x, int(ms * size * SR / 1000), decay) for ms in (29.7, 37.1, 41.1, 43.7)) / 4
    for ms in (5.0, 1.7):
        wet = _allpass(wet, int(ms * SR / 1000), 0.7)
    wet = filt(wet, lo=200, hi=7000)  # keep the tail out of the lows and the hiss
    return (1 - mix) * x + mix * wet


def echo(x: Signal, delay: float, feedback: float = 0.4, repeats: int = 3) -> Signal:
    d = samples(delay)
    out = np.concatenate([x, np.zeros(d * repeats)])
    for i in range(1, repeats + 1):
        out[d * i:d * i + len(x)] += x * feedback ** i
    return out


def stutter(x: Signal, at: float, length: float, repeats: int) -> Signal:
    """Glitch: repeat a short slice in place (the rest of the sound moves later)."""
    a, n = samples(at), samples(length)
    piece = x[a:a + n] * np.hanning(n) ** 0.25
    return np.concatenate([x[:a], np.tile(piece, repeats), x[a + n:]])


def seq(*parts: tuple[float, Signal] | tuple[float, Signal, float]) -> Signal:
    """Mix sounds at offsets: seq((0, a), (0.05, b, 0.5)) -> b starts at 50 ms at half gain."""
    end = max(samples(p[0]) + len(p[1]) for p in parts)
    out = np.zeros(end)
    for p in parts:
        at, sig, gain = p[0], p[1], p[2] if len(p) > 2 else 1.0
        out[samples(at):samples(at) + len(sig)] += gain * sig
    return out


def blip(freq, sec: float, shape: str = "sine", curve: float = 3.0, **kw) -> Signal:
    return tone(freq, sec, shape, **kw) * perc(sec, curve=curve)


def click(rng: np.random.Generator, sec: float = 0.006, lo: float = 2000, hi: float = 9000) -> Signal:
    return filt(noise(rng, sec), lo=lo, hi=hi) * perc(sec, attack=0.0005, curve=4)


def chirps(rng: np.random.Generator, count: int, step: float, notes: list[float], length: float = 0.022,
           shape: str = "pulse", rising: bool | None = None) -> Signal:
    """A burst of data chirps: short blips on random notes of a scale (sorted up or down)."""
    picks = list(rng.choice(notes, count))
    if rising is not None:
        picks.sort(reverse=not rising)
    return seq(*((i * step, blip(midi(n), length, shape, curve=1.5)) for i, n in enumerate(picks)))


PEAK_DB = -1.0


def loudness(x: Signal) -> float:
    """dBFS RMS of the loudest 50 ms: how loud a short sound feels, more or less."""
    w = samples(0.05)
    power = np.convolve(x ** 2, np.ones(w) / w, mode="valid") if len(x) > w else [np.mean(x ** 2)]
    return 10 * np.log10(max(np.max(power), 1e-20))


def finish(x: Signal, loudness_db: float) -> Signal:
    """Remove DC/rumble, fade the ends (no clicks), match the loudness target; the peak never
    goes above PEAK_DB."""
    x = filt(x, lo=40, order=1)
    fade_in, fade_out = samples(0.001), samples(0.006)
    x[:fade_in] *= np.linspace(0, 1, fade_in)
    x[-fade_out:] *= np.linspace(1, 0, fade_out)
    if not np.abs(x).max():
        raise ValueError("silent sound")
    x = x * 10 ** ((loudness_db - loudness(x)) / 20)
    return x * min(1.0, 10 ** (PEAK_DB / 20) / np.abs(x).max())


# Scale for the chirps and melodies: A minor pentatonic over three octaves.
PENTA = [n + o for o in (57, 69, 81) for n in (0, 3, 5, 7, 10)]


# =========================================================================== neural-link
# Digital and a little glitchy: FM bells, crushed pulses, chirp bursts, short reverb.
def nl_boot(r):
    rise = tone((90, 1400), 0.24, "saw") * perc(0.24, attack=0.18, curve=1.2)
    rise = filt(crush(rise, bits=5, hold=6), hi=8000) * 0.35
    hiss = filt(noise(r, 0.24), lo=3000) * perc(0.24, attack=0.2, curve=1) * 0.15
    notes = [seq((i * 0.06, blip(midi(n), 0.2, "soft", curve=2.5, fm=(2, 0.6), detune=7), 0.7))
             for i, n in enumerate((69, 76, 81, 88))]
    body = seq((0, rise), (0, hiss), (0.2, sum_parts(notes)))
    return reverb(body, tail=0.0, mix=0.3)[: samples(0.6)]


def sum_parts(parts: list[Signal]) -> Signal:
    return seq(*((0, p) for p in parts))


def nl_login(r):
    a = blip(midi(76), 0.16, "soft", curve=2, fm=(2, 0.8), detune=6)
    b = blip(midi(83), 0.26, "soft", curve=2.5, fm=(2, 0.8), detune=6)
    return reverb(seq((0, chirps(r, 4, 0.018, PENTA[8:], length=0.016), 0.25), (0.07, a), (0.15, b)),
                  tail=0.12, mix=0.28)


def nl_logout(r):
    a = blip(midi(83), 0.16, "soft", curve=2, fm=(2, 0.8), detune=6)
    b = blip(midi(76), 0.28, "soft", curve=2.5, fm=(2, 0.8), detune=6)
    return reverb(seq((0, a), (0.1, b)), tail=0.12, mix=0.28)


def nl_shutdown(r):
    # a power-down: pitch falls like a stopping tape, the bits fall apart at the end
    drop = tone((660, 70), 0.48, "square") * perc(0.48, attack=0.004, curve=1.6)
    drop = filt(crush(drop, bits=6, hold=3), hi=7000) * 0.6
    chord = blip(midi(81), 0.3, "soft", curve=2, fm=(2, 0.6), detune=8) * 0.6
    return reverb(seq((0, chord), (0.05, drop)), tail=0.06, mix=0.22)


def nl_workspace(r):
    whoosh = filt(noise(r, 0.11), lo=1200, hi=6000) * perc(0.11, attack=0.03, curve=2)
    sweep = blip((1800, 900), 0.07, "sine", curve=2) * 0.5
    return seq((0, whoosh, 0.6), (0.02, sweep))


def nl_window_open(r):
    return seq((0, blip((700, 1700), 0.12, "triangle", curve=2.2)), (0.0, click(r), 0.4))


def nl_window_close(r):
    return seq((0, blip((1500, 550), 0.11, "triangle", curve=2.2)), (0.0, click(r), 0.4))


def nl_window_focus(r):
    return blip(2400, 0.05, "sine", curve=4)


def nl_launcher_open(r):
    return reverb(chirps(r, 5, 0.022, PENTA[5:], rising=True), tail=0.06, mix=0.2)


def nl_launcher_close(r):
    return reverb(chirps(r, 3, 0.024, PENTA[5:], rising=False), tail=0.05, mix=0.2)


def nl_menu_hover(r):
    return blip(3200, 0.05, "sine", curve=5)


def nl_button_click(r):
    return seq((0, click(r, 0.005), 0.8), (0.002, blip(1300, 0.05, "soft", curve=4)))


def nl_notification(r):
    a = blip(midi(84), 0.18, "sine", curve=2, fm=(3.5, 1.2))
    b = blip(midi(91), 0.22, "sine", curve=2.2, fm=(3.5, 1.2))
    return reverb(seq((0, chirps(r, 3, 0.016, PENTA[10:], length=0.014), 0.2), (0.05, a), (0.13, b, 0.8)),
                  tail=0.1, mix=0.25)


def nl_notification_critical(r):
    pulse = lambda f: filt(crush(blip(f, 0.09, "soft", curve=1.2), bits=6, hold=2), hi=6000)  # noqa: E731
    alarm = seq((0, pulse(880)), (0.12, pulse(660)), (0.24, pulse(880)), (0.36, pulse(660)))
    return reverb(alarm, tail=0.08, mix=0.18)


def nl_volume(r):
    return blip(1500, 0.055, "sine", curve=4)


def nl_brightness(r):
    return blip(2100, 0.055, "triangle", curve=4)


def nl_usb_connect(r):
    return reverb(seq((0, click(r), 0.5), (0.01, blip(midi(79), 0.08, "soft", curve=3)),
                      (0.09, blip(midi(86), 0.12, "soft", curve=3))), tail=0.08, mix=0.22)


def nl_usb_disconnect(r):
    return reverb(seq((0, blip(midi(86), 0.08, "soft", curve=3)), (0.08, blip(midi(79), 0.12, "soft", curve=3)),
                      (0.19, click(r), 0.4)), tail=0.08, mix=0.22)


def nl_battery_low(r):
    beep = lambda f: blip(f, 0.16, "triangle", curve=1.5)  # noqa: E731
    return reverb(seq((0, beep(midi(69))), (0.2, beep(midi(64)))), tail=0.1, mix=0.2)


def nl_charger(r):
    rise = tone((180, 900), 0.22, "saw") * perc(0.22, attack=0.15, curve=1.5)
    ping = blip(midi(88), 0.12, "sine", curve=2.5, fm=(2, 0.5))
    return reverb(seq((0, filt(rise, hi=4000) * 0.5), (0.2, ping)), tail=0.06, mix=0.2)


def nl_screenshot(r):
    shutter = lambda: filt(noise(r, 0.03), lo=1500, hi=10000) * perc(0.03, attack=0.001, curve=3)  # noqa: E731
    return seq((0, shutter()), (0.07, shutter(), 0.7), (0.07, blip(2600, 0.06, curve=4), 0.3))


def nl_error(r):
    buzz = lambda: filt(crush(blip(150, 0.09, "pulse", curve=0.8), bits=4, hold=4), hi=3500)  # noqa: E731
    return seq((0, buzz()), (0.12, buzz()))


def nl_lock(r):
    fall = blip((1600, 400), 0.14, "triangle", curve=2)
    thunk = blip((140, 60), 0.18, "sine", curve=2.5)
    lock = seq((0, fall, 0.6), (0.12, thunk), (0.12, click(r, 0.01, lo=800, hi=5000), 0.6))
    return stutter(reverb(lock, tail=0.08, mix=0.2), at=0.0, length=0.012, repeats=3)


def nl_unlock(r):
    a = blip(midi(81), 0.12, "soft", curve=2.5, fm=(2, 0.7))
    b = blip(midi(88), 0.2, "soft", curve=2.5, fm=(2, 0.7))
    return reverb(seq((0, click(r), 0.5), (0.02, a), (0.1, b)), tail=0.12, mix=0.25)


def nl_bell(r):
    return blip(midi(81), 0.15, "sine", curve=2.5, fm=(3, 0.8))


def nl_command_done(r):
    return reverb(seq((0, blip(midi(81), 0.1, "soft", curve=3)), (0.08, blip(midi(88), 0.16, "soft", curve=3))),
                  tail=0.08, mix=0.2)


def nl_command_failed(r):
    a = crush(blip(midi(64), 0.1, "square", curve=2), bits=5, hold=3)
    b = crush(blip(midi(57), 0.16, "square", curve=2), bits=5, hold=3)
    return seq((0, a), (0.1, b))


# =========================================================================== minimal-ops
# Quiet and plain: soft sine beeps in the low-mid range, tiny filtered clicks. No reverb.
def mo_beep(note: float, sec: float = 0.09, curve: float = 2.5) -> Signal:
    return tone(midi(note), sec, "sine") * adsr(sec, attack=0.004, decay=0.02, sustain=0.7, release=sec * 0.6) \
        * perc(sec, attack=0.001, curve=curve * 0.3)


def mo_click(r, lo=1500, hi=5000):
    return click(r, 0.004, lo=lo, hi=hi)


def mo_pad(x: Signal, sec: float = 0.05) -> Signal:
    """Pad very short clicks to the minimum length (silence after them)."""
    return np.pad(x, (0, max(0, samples(sec) - len(x))))


MINIMAL: dict[str, Recipe] = {
    "boot": lambda r: seq((0, mo_beep(57, 0.16)), (0.14, mo_beep(64, 0.16)), (0.28, mo_beep(69, 0.3))),
    "login": lambda r: seq((0, mo_beep(64, 0.1)), (0.1, mo_beep(69, 0.18))),
    "logout": lambda r: seq((0, mo_beep(69, 0.1)), (0.1, mo_beep(64, 0.18))),
    "shutdown": lambda r: seq((0, mo_beep(64, 0.12)), (0.12, mo_beep(60, 0.12)), (0.24, mo_beep(57, 0.28))),
    "workspace_switch": lambda r: mo_pad(seq((0, mo_click(r, 800, 3000)), (0.01, mo_beep(72, 0.04)))),
    "window_open": lambda r: mo_beep(72, 0.06),
    "window_close": lambda r: mo_beep(67, 0.06),
    "window_focus": lambda r: mo_pad(mo_click(r, 2000, 6000)),
    "launcher_open": lambda r: seq((0, mo_beep(69, 0.05)), (0.05, mo_beep(76, 0.06))),
    "launcher_close": lambda r: seq((0, mo_beep(76, 0.05)), (0.05, mo_beep(69, 0.06))),
    "menu_hover": lambda r: mo_pad(mo_click(r, 3000, 7000)),
    "button_click": lambda r: mo_pad(mo_click(r)),
    "notification": lambda r: seq((0, mo_beep(76, 0.1)), (0.12, mo_beep(81, 0.14))),
    "notification_critical": lambda r: seq((0, mo_beep(76, 0.1)), (0.14, mo_beep(76, 0.1)), (0.28, mo_beep(76, 0.14))),
    "volume_change": lambda r: mo_pad(seq((0, mo_click(r, 1000, 4000)), (0, mo_beep(81, 0.03)))),
    "brightness_change": lambda r: mo_pad(seq((0, mo_click(r, 1500, 6000)), (0, mo_beep(84, 0.03)))),
    "usb_connect": lambda r: seq((0, mo_beep(67, 0.07)), (0.08, mo_beep(74, 0.1))),
    "usb_disconnect": lambda r: seq((0, mo_beep(74, 0.07)), (0.08, mo_beep(67, 0.1))),
    "battery_low": lambda r: seq((0, mo_beep(57, 0.16)), (0.22, mo_beep(57, 0.16))),
    "charger_plug": lambda r: mo_beep(69, 0.14),
    "screenshot": lambda r: mo_pad(seq((0, mo_click(r, 1500, 8000)), (0.05, mo_click(r, 1500, 8000), 0.6)), 0.08),
    "error": lambda r: seq((0, mo_beep(50, 0.1)), (0.13, mo_beep(50, 0.1))),
    "lock": lambda r: seq((0, mo_beep(64, 0.08)), (0.08, mo_beep(57, 0.12))),
    "unlock": lambda r: seq((0, mo_beep(57, 0.08)), (0.08, mo_beep(64, 0.12))),
    "terminal_bell": lambda r: mo_beep(69, 0.08),
    "command_done": lambda r: seq((0, mo_beep(72, 0.07)), (0.08, mo_beep(76, 0.1))),
    "command_failed": lambda r: seq((0, mo_beep(57, 0.08)), (0.09, mo_beep(53, 0.12))),
}

NEURAL: dict[str, Recipe] = {
    "boot": nl_boot, "login": nl_login, "logout": nl_logout, "shutdown": nl_shutdown,
    "workspace_switch": nl_workspace, "window_open": nl_window_open, "window_close": nl_window_close,
    "window_focus": nl_window_focus, "launcher_open": nl_launcher_open, "launcher_close": nl_launcher_close,
    "menu_hover": nl_menu_hover, "button_click": nl_button_click, "notification": nl_notification,
    "notification_critical": nl_notification_critical, "volume_change": nl_volume,
    "brightness_change": nl_brightness, "usb_connect": nl_usb_connect, "usb_disconnect": nl_usb_disconnect,
    "battery_low": nl_battery_low, "charger_plug": nl_charger, "screenshot": nl_screenshot, "error": nl_error,
    "lock": nl_lock, "unlock": nl_unlock, "terminal_bell": nl_bell, "command_done": nl_command_done,
    "command_failed": nl_command_failed,
}

# Loudness per event: small UI ticks sit well below confirms, alerts above them.
TICKS = {"window_focus", "menu_hover", "button_click", "volume_change", "brightness_change", "terminal_bell"}
LOUD = {"notification_critical", "battery_low", "error"}


@dataclass
class Pack:
    name: str
    description: str
    recipes: dict[str, Recipe]
    level: float  # loudness (dBFS, see loudness()) of a normal event; ticks 8 dB lower, alerts 3 dB higher

    def level_of(self, event: str) -> float:
        return self.level - 8 if event in TICKS else self.level + 3 if event in LOUD else self.level


PACKS = {
    "neural-link": Pack("neural-link", "Glitchy digital blips, data chirps and soft synth confirms", NEURAL, -16),
    "minimal-ops": Pack("minimal-ops", "Very subtle clicks and low beeps", MINIMAL, -21),
}


# =========================================================================== output
def render(pack: Pack, event: str) -> Signal:
    seed = int.from_bytes(hashlib.sha256(f"{pack.name}/{event}".encode()).digest()[:8], "little")
    x = finish(np.asarray(pack.recipes[event](np.random.default_rng(seed)), dtype=float), pack.level_of(event))
    ms = len(x) * 1000 / SR
    if not MIN_MS <= ms <= MAX_MS:
        raise ValueError(f"{pack.name}/{event}: {ms:.0f} ms, must be {MIN_MS}-{MAX_MS} ms")
    return x


def write_wav(path: Path, x: Signal) -> None:
    pcm = np.clip(np.round(x * 32767), -32768, 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def write_pack(pack: Pack, out: Path) -> list[Path]:
    d = out / pack.name
    d.mkdir(parents=True, exist_ok=True)
    for old in d.glob("*.wav"):
        old.unlink()
    files = []
    for event in pack.recipes:
        f = d / f"{event}.wav"
        write_wav(f, render(pack, event))
        files.append(f)
    lines = [
        "# Generated by assets/sounds/generate.py: edit the recipes there, not this file.",
        "[meta]",
        f'name = "{pack.name}"',
        f'description = "{pack.description}"',
        'author = "NULLGRID (synthesized by assets/sounds/generate.py)"',
        'license = "MIT"',
        "",
        "# event = file, or { file = ..., volume = 0-1 }",
        "[events]",
        *(f'{event} = "{event}.wav"' for event in pack.recipes),
    ]
    (d / "pack.toml").write_text("\n".join(lines) + "\n")
    return files


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", type=Path, default=ROOT / "out" / "sounds", help="default: out/sounds")
    p.add_argument("--pack", action="append", choices=sorted(PACKS), help="only this pack (repeatable)")
    p.add_argument("--list", action="store_true", help="list packs and events, write nothing")
    args = p.parse_args(argv)
    if args.list:
        for pack in PACKS.values():
            print(f"{pack.name}: {pack.description}\n  " + " ".join(pack.recipes))
        return 0
    for name in args.pack or sorted(PACKS):
        files = write_pack(PACKS[name], args.out)
        size = sum(f.stat().st_size for f in files)
        print(f"{name}: {len(files)} sounds, {size // 1024} KiB -> {args.out / name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
