"""Colors as templates see them: one value, printed in whatever format an app wants."""
from __future__ import annotations

import re

HEX = re.compile(r"#?([0-9a-fA-F]{6})")


class Color:
    """An sRGB color. str() gives '#rrggbb'; methods give the other formats apps use."""

    __slots__ = ("r", "g", "b")

    def __init__(self, value: str):
        m = HEX.fullmatch(value.strip())
        if not m:
            raise ValueError(f"expected a color like '#5ef2f2', got {value!r}")
        h = m.group(1)
        self.r, self.g, self.b = (int(h[i:i + 2], 16) for i in (0, 2, 4))

    @classmethod
    def from_rgb(cls, r: float, g: float, b: float) -> Color:
        clamp = lambda v: max(0, min(255, round(v)))  # noqa: E731
        return cls("%02x%02x%02x" % (clamp(r), clamp(g), clamp(b)))

    # -- formats ---------------------------------------------------------
    @property
    def hex(self) -> str:
        """'#rrggbb'"""
        return "#%02x%02x%02x" % (self.r, self.g, self.b)

    @property
    def bare(self) -> str:
        """'rrggbb' (fuzzel, Linux console, Hyprland)"""
        return self.hex[1:]

    @property
    def rgb(self) -> str:
        """'r, g, b'"""
        return f"{self.r}, {self.g}, {self.b}"

    def hexa(self, alpha: float = 1.0) -> str:
        """'#rrggbbaa' (mako, CSS)"""
        return self.hex + _byte(alpha)

    def barea(self, alpha: float = 1.0) -> str:
        """'rrggbbaa' (fuzzel)"""
        return self.bare + _byte(alpha)

    def argb(self, alpha: float = 1.0) -> str:
        """'#aarrggbb' (Qt, QML)"""
        return "#" + _byte(alpha) + self.bare

    def rgba(self, alpha: float = 1.0) -> str:
        """'rgba(r, g, b, a)' (CSS)"""
        return f"rgba({self.rgb}, {round(alpha, 3):g})"

    def hypr(self, alpha: float = 1.0) -> str:
        """'rgba(rrggbbaa)' (Hyprland, hyprlock)"""
        return f"rgba({self.barea(alpha)})"

    # -- math ------------------------------------------------------------
    def mix(self, other: Color | str, t: float = 0.5) -> Color:
        """Blend toward other: t=0 is self, t=1 is other."""
        o = other if isinstance(other, Color) else Color(other)
        return Color.from_rgb(*(a + (b - a) * t for a, b in zip(self.tuple, o.tuple)))

    def lighten(self, t: float) -> Color:
        return self.mix("#ffffff", t)

    def darken(self, t: float) -> Color:
        return self.mix("#000000", t)

    @property
    def tuple(self) -> tuple[int, int, int]:
        return (self.r, self.g, self.b)

    @property
    def luminance(self) -> float:
        """WCAG relative luminance."""
        def lin(c: int) -> float:
            c /= 255
            return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
        r, g, b = map(lin, self.tuple)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    def contrast(self, other: Color | str) -> float:
        """WCAG contrast ratio, 1..21."""
        o = other if isinstance(other, Color) else Color(other)
        hi, lo = sorted((self.luminance, o.luminance), reverse=True)
        return (hi + 0.05) / (lo + 0.05)

    def __str__(self) -> str:
        return self.hex

    def __repr__(self) -> str:
        return f"Color({self.hex!r})"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Color) and self.tuple == other.tuple

    def __hash__(self) -> int:
        return hash(self.tuple)


def _byte(alpha: float) -> str:
    return "%02x" % max(0, min(255, round(alpha * 255)))
