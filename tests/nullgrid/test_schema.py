from nullgrid.schema import Bool, Enum, Float, Int, Table, Time


SCHEMA = Table({
    "on": Bool(default=True),
    "level": Int(0, 10, default=5),
    "ratio": Float(0, 1, default=0.5),
    "corners": Enum("sharp", "round", default="sharp"),
    "start": Time(default="22:00"),
    "inner": Table({"name": Enum("a", "b")}),
})


def check(data):
    errors = []
    out = SCHEMA.validate(data, "", errors)
    return out, errors


def test_fills_defaults_and_reports_missing_required():
    out, errors = check({})
    assert out["on"] is True and out["level"] == 5 and out["corners"] == "sharp"
    assert errors == ["inner.name: missing (required)"]


def test_error_paths_and_suggestions():
    _, errors = check({"levle": 3, "corners": "rund", "inner": {"name": "c"}})
    assert "levle: unknown key (did you mean 'level'?)" in errors
    assert any(e.startswith("corners: expected one of sharp, round") and "did you mean 'round'" in e for e in errors)
    assert any(e.startswith("inner.name:") for e in errors)


def test_types_and_ranges():
    _, errors = check({"on": 1, "level": 11, "ratio": True, "start": "25:00", "inner": {"name": "a"}})
    assert len(errors) == 4
    _, errors = check({"level": 2.5, "inner": {"name": "a"}})
    assert errors == ["level: expected a whole number, got 2.5"]
    _, errors = check({"ratio": 1, "inner": {"name": "a"}})  # ints are fine for floats
    assert errors == []


def test_partial_has_no_defaults_or_required_keys():
    errors = []
    out = SCHEMA.as_partial().validate({"level": 3}, "", errors)
    assert errors == [] and out == {"level": 3}
