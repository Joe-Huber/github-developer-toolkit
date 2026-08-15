"""Reproducible text heuristics shared by the analyzers (issues #24/#26).

These are deliberately conservative regular expressions and phrase lists.
They detect *obvious* placeholder scaffolding and generic template wording;
they are heuristics, not claims about intent. Every match is surfaced as a
finding with the matched text as evidence, never as ground truth.

False-positive caveats: a company genuinely named "Example", a bio that
quotes ``lorem ipsum``, or a README that intentionally uses template
wording can all match. Matching text is always included in the evidence so
an analyst can judge the match themselves.
"""

from __future__ import annotations

import re

_PLACEHOLDER_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\blorem ipsum\b", re.IGNORECASE),
    re.compile(r"\bexample\.com\b", re.IGNORECASE),
    re.compile(r"\byourdomain\b", re.IGNORECASE),
    re.compile(r"\bexample-domain\b", re.IGNORECASE),
    re.compile(
        r"\b(your|my|insert)\s+"
        r"(company|domain|website|site|project|handle|username|name|bio)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bchange ?me\b", re.IGNORECASE),
    re.compile(r"\bcoming soon\b", re.IGNORECASE),
    re.compile(r"\btodo\b", re.IGNORECASE),
    re.compile(r"\bplaceholder\b", re.IGNORECASE),
    re.compile(r"\btbd\b", re.IGNORECASE),
    re.compile(r"\b@your(username|handle|twitter)\b", re.IGNORECASE),
    re.compile(r"<your[^>]*>|<insert[^>]*>", re.IGNORECASE),
)

_BOILERPLATE_PHRASES: tuple[str, ...] = (
    "this is a readme",
    "this is a profile readme",
    "this is my readme",
    "here is my readme",
    "welcome to my github profile",
    "you found my github profile",
    "feel free to use this template",
    "made from a template",
    "built with a template",
    "based on a template",
)

__all__ = ["find_boilerplate", "find_placeholders"]


def find_placeholders(value: str) -> list[str]:
    """Return every placeholder pattern matched in ``value``.

    The returned strings are the literal matched text fragments, so callers
    can attach them to finding evidence. Matches are case-insensitive.
    """
    return [
        pattern.pattern for pattern in _PLACEHOLDER_PATTERNS if pattern.search(value) is not None
    ]


def find_boilerplate(text: str) -> list[str]:
    """Return every generic template phrase found in ``text``.

    Phrase matching is lowercase substring matching, so "Welcome to my
    GitHub profile" is caught as well as the lowercase form. See the module
    docstring for false-positive caveats.
    """
    lowered = text.lower()
    return [phrase for phrase in _BOILERPLATE_PHRASES if phrase in lowered]
