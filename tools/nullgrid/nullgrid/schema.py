"""A tiny declarative validator for TOML data.

Fields check one value; Table checks a dict of fields, fills in defaults, and reports
unknown keys with a "did you mean" hint. Errors carry a dotted path such as
`theme.colors.primary` so messages point at the exact line to fix.
"""
from __future__ import annotations

import copy
import difflib
import re
from typing import Any

from .color import Color

MISSING = object()


class Invalid(Exception):
    pass


class Field:
    def __init__(self, default: Any = MISSING, doc: str = ""):
        self.default = default
        self.doc = doc

    def check(self, value: Any) -> Any:
        return value


class Bool(Field):
    def check(self, value):
        if not isinstance(value, bool):
            raise Invalid(f"expected true or false, got {value!r}")
        return value


class Number(Field):
    def __init__(self, lo: float, hi: float, *, integer: bool = False, **kw):
        super().__init__(**kw)
        self.lo, self.hi, self.integer = lo, hi, integer

    def check(self, value):
        ok_types = (int,) if self.integer else (int, float)
        if isinstance(value, bool) or not isinstance(value, ok_types):
            raise Invalid(f"expected {'a whole number' if self.integer else 'a number'}, got {value!r}")
        if not self.lo <= value <= self.hi:
            raise Invalid(f"must be between {self.lo} and {self.hi}, got {value!r}")
        return value


def Int(lo: int, hi: int, **kw) -> Number:
    return Number(lo, hi, integer=True, **kw)


def Float(lo: float, hi: float, **kw) -> Number:
    return Number(lo, hi, **kw)


class Str(Field):
    def __init__(self, pattern: str | None = None, hint: str = "", **kw):
        super().__init__(**kw)
        self.pattern = re.compile(pattern) if pattern else None
        self.hint = hint

    def check(self, value):
        if not isinstance(value, str):
            raise Invalid(f"expected a string, got {value!r}")
        if self.pattern and not self.pattern.fullmatch(value):
            raise Invalid(f"expected {self.hint or self.pattern.pattern}, got {value!r}")
        return value


class StrList(Field):
    def check(self, value):
        if not (isinstance(value, list) and all(isinstance(v, str) for v in value)):
            raise Invalid(f"expected a list of strings, got {value!r}")
        return value


class Mapping(Field):
    """A table with free-form keys (checked by whoever uses it)."""
    def check(self, value):
        if not isinstance(value, dict):
            raise Invalid(f"expected a table, got {value!r}")
        return value


class Enum(Field):
    def __init__(self, *choices: str, **kw):
        super().__init__(**kw)
        self.choices = choices

    def check(self, value):
        if value not in self.choices:
            raise Invalid(f"expected one of {', '.join(self.choices)}; got {value!r}{_suggest(value, self.choices)}")
        return value


class ColorField(Field):
    def check(self, value):
        if not isinstance(value, str):
            raise Invalid(f"expected a color like '#5ef2f2', got {value!r}")
        try:
            return Color(value)
        except ValueError as exc:
            raise Invalid(str(exc)) from None


def Time(**kw) -> Str:
    return Str(r"([01]\d|2[0-3]):[0-5]\d", hint="a time like '22:30'", **kw)


class Table(Field):
    """A TOML table with known keys. partial=True: keys without defaults are optional."""

    def __init__(self, fields: dict[str, Field], *, partial: bool = False, doc: str = ""):
        super().__init__(default=MISSING, doc=doc)
        self.fields = fields
        self.partial = partial

    def as_partial(self) -> Table:
        """Same shape, every key optional, no defaults filled in (for override tables)."""
        return Table({k: f.as_partial() if isinstance(f, Table) else _no_default(f)
                      for k, f in self.fields.items()}, partial=True, doc=self.doc)

    def defaults(self) -> dict:
        out = {}
        for key, f in self.fields.items():
            if isinstance(f, Table):
                out[key] = f.defaults()
            elif f.default is not MISSING:
                out[key] = f.default
        return out

    def validate(self, data: Any, path: str = "", errors: list[str] | None = None) -> dict:
        """Return the checked dict (defaults filled in). Problems are appended to errors."""
        errors = [] if errors is None else errors
        where = path or "top level"
        if not isinstance(data, dict):
            errors.append(f"{where}: expected a table, got {data!r}")
            return {}
        out: dict = {}
        for key, value in data.items():
            if key not in self.fields:
                errors.append(f"{_join(path, key)}: unknown key{_suggest(key, self.fields)}")
        for key, f in self.fields.items():
            sub = _join(path, key)
            if key in data:
                if isinstance(f, Table):
                    out[key] = f.validate(data[key], sub, errors)
                else:
                    try:
                        out[key] = f.check(data[key])
                    except Invalid as exc:
                        errors.append(f"{sub}: {exc}")
            elif isinstance(f, Table):
                if not self.partial:
                    out[key] = f.validate({}, sub, errors)
            elif f.default is not MISSING and not self.partial:
                out[key] = copy.deepcopy(f.default)
            elif not self.partial:
                errors.append(f"{sub}: missing (required)")
        return out


def _no_default(f: Field) -> Field:
    c = copy.copy(f)
    c.default = MISSING
    return c


def _join(path: str, key: str) -> str:
    return f"{path}.{key}" if path else key


def _suggest(word: Any, choices) -> str:
    if not isinstance(word, str):
        return ""
    close = difflib.get_close_matches(word, list(choices), n=1, cutoff=0.6)
    return f" (did you mean {close[0]!r}?)" if close else ""
