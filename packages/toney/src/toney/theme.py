"""The colour scheme of the Toney interface.

The palette is deliberately small: a handful of semantic colours that every
widget refers to, so the whole interface can be recoloured from this one
place.  The same values are used twice: once as Textual theme variables for
the stylesheet, and once as plain hex strings for the Rich text that the
views build.  The views ask for the palette of the theme that is on screen,
so a change of theme reaches the text as well as the stylesheet.

The dark theme is Textual's *tokyo-night*: its purple, blue, orange, green,
red and yellow over its deep blue background.  The colours are the ones
Textual ships with, so the two agree.
"""

from __future__ import annotations

from typing import Dict, Optional

from textual.theme import Theme

TOKYO_NIGHT: Dict[str, str] = {
    "text": "#A9B1D6",
    "dim": "#565F89",
    "keep": "#7AA2F7",
    "block": "#F7768E",
    "ok": "#9ECE6A",
    "warn": "#E0AF68",
    "primary": "#BB9AF7",
    "accent": "#FF9E64",
    "background": "#1A1B26",
    "surface": "#24283B",
    "panel": "#414868",
    "border": "#3B4261",
    "rule": "#292E42",
}

TONEY_LIGHT: Dict[str, str] = {
    "text": "#1F2328",
    "dim": "#59636E",
    "keep": "#0969DA",
    "block": "#CF222E",
    "ok": "#1A7F37",
    "warn": "#9A6700",
    "primary": "#0969DA",
    "accent": "#BC4C00",
    "background": "#FFFFFF",
    "surface": "#F6F8FA",
    "panel": "#EAEEF2",
    "border": "#D0D7DE",
    "rule": "#D8DEE4",
}

PALETTES: Dict[str, Dict[str, str]] = {
    "tokyo-night": TOKYO_NIGHT,
    "toney-light": TONEY_LIGHT,
}

COLORS = TOKYO_NIGHT

DECISION_COLORS = {
    "allow": "ok",
    "cache": "ok",
    "block": "block",
    "blocked": "block",
    "error": "warn",
}


def palette(name: str) -> Dict[str, str]:
    """The colours of a theme, by name."""
    return PALETTES.get(name, TOKYO_NIGHT)


def decision_color(decision: str, colors: Optional[Dict[str, str]] = None) -> str:
    """Return the colour that matches what the filter decided."""
    key = DECISION_COLORS.get(str(decision or "").strip().lower(), "dim")
    return (colors or COLORS)[key]


def _variables(colors: Dict[str, str]) -> Dict[str, str]:
    """The toney-* variables of a palette, for the stylesheet."""
    return {
        "toney-dim": colors["dim"],
        "toney-keep": colors["keep"],
        "toney-block": colors["block"],
        "toney-ok": colors["ok"],
        "toney-warn": colors["warn"],
        "toney-border": colors["border"],
        "toney-rule": colors["rule"],
        "toney-value": colors["text"],
        "button-color-foreground": colors["surface"],
    }


TOKYO_NIGHT_THEME = Theme(
    name="tokyo-night",
    primary=TOKYO_NIGHT["primary"],
    secondary=TOKYO_NIGHT["keep"],
    accent=TOKYO_NIGHT["accent"],
    success=TOKYO_NIGHT["ok"],
    warning=TOKYO_NIGHT["warn"],
    error=TOKYO_NIGHT["block"],
    foreground=TOKYO_NIGHT["text"],
    background=TOKYO_NIGHT["background"],
    surface=TOKYO_NIGHT["surface"],
    panel=TOKYO_NIGHT["panel"],
    dark=True,
    variables=_variables(TOKYO_NIGHT),
)

TONEY_LIGHT_THEME = Theme(
    name="toney-light",
    primary=TONEY_LIGHT["primary"],
    secondary=TONEY_LIGHT["keep"],
    accent=TONEY_LIGHT["accent"],
    success=TONEY_LIGHT["ok"],
    warning=TONEY_LIGHT["warn"],
    error=TONEY_LIGHT["block"],
    foreground=TONEY_LIGHT["text"],
    background=TONEY_LIGHT["background"],
    surface=TONEY_LIGHT["surface"],
    panel=TONEY_LIGHT["panel"],
    dark=False,
    variables=_variables(TONEY_LIGHT),
)

THEMES = (TOKYO_NIGHT_THEME, TONEY_LIGHT_THEME)
