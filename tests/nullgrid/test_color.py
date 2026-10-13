import pytest

from nullgrid.color import Color


def test_parse_and_formats():
    c = Color("#5EF2F2")
    assert str(c) == c.hex == "#5ef2f2"
    assert Color("5ef2f2") == c
    assert c.bare == "5ef2f2"
    assert c.rgb == "94, 242, 242"
    assert c.hexa(0.85) == "#5ef2f2d9"
    assert c.argb(0.5) == "#805ef2f2"
    assert c.hypr() == "rgba(5ef2f2ff)"
    assert c.rgba(0.5) == "rgba(94, 242, 242, 0.5)"


@pytest.mark.parametrize("bad", ["#fff", "cyan", "#12345g", "#1234567"])
def test_rejects_bad_colors(bad):
    with pytest.raises(ValueError):
        Color(bad)


def test_math():
    black, white = Color("#000000"), Color("#ffffff")
    assert black.mix(white, 0.5) == Color("#808080")
    assert black.mix("#ffffff", 0) == black
    assert white.darken(1) == black
    assert black.lighten(1) == white
    assert black.contrast(white) == pytest.approx(21)
    assert white.contrast(white) == pytest.approx(1)


def test_perceptual_distance():
    gray, green, light_gray = Color("#7a8a8f"), Color("#3ddc97"), Color("#b8c7cb")
    assert gray.distance(gray) == pytest.approx(0)
    assert gray.distance(light_gray) < gray.distance(green)  # RGB distance gets this wrong
    assert Color("#000000").distance("#ffffff") == pytest.approx(100, abs=0.5)
