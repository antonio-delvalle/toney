"""Tests for the colour scheme of the Toney interface."""

import unittest

from textual.theme import BUILTIN_THEMES

from toney.theme import (
    PALETTES,
    THEMES,
    TOKYO_NIGHT,
    TOKYO_NIGHT_THEME,
    TONEY_LIGHT,
    TONEY_LIGHT_THEME,
    decision_color,
    palette,
)

KEYS = ("text", "dim", "keep", "block", "ok", "warn", "primary", "accent")


class ThemeTest(unittest.TestCase):
    """The themes of the interface."""

    def test_the_first_theme_is_tokyo_night(self):
        self.assertEqual(THEMES[0].name, "tokyo-night")

    def test_tokyo_night_keeps_the_colours_textual_ships(self):
        builtin = BUILTIN_THEMES["tokyo-night"]
        for name in (
            "primary",
            "secondary",
            "warning",
            "error",
            "success",
            "accent",
            "foreground",
            "background",
            "surface",
            "panel",
        ):
            self.assertEqual(
                getattr(TOKYO_NIGHT_THEME, name).lower(),
                getattr(builtin, name).lower(),
                name,
            )

    def test_the_light_theme_is_light(self):
        self.assertFalse(TONEY_LIGHT_THEME.dark)

    def test_every_theme_has_a_palette(self):
        for theme in THEMES:
            self.assertIn(theme.name, PALETTES)

    def test_every_palette_has_the_same_keys(self):
        for name, colors in PALETTES.items():
            for key in KEYS:
                self.assertIn(key, colors, name)

    def test_a_theme_carries_the_variables_of_its_palette(self):
        for theme, colors in (
            (TOKYO_NIGHT_THEME, TOKYO_NIGHT),
            (TONEY_LIGHT_THEME, TONEY_LIGHT),
        ):
            variables = theme.variables
            self.assertEqual(variables["toney-dim"], colors["dim"])
            self.assertEqual(variables["toney-keep"], colors["keep"])
            self.assertEqual(variables["toney-block"], colors["block"])
            self.assertEqual(variables["toney-ok"], colors["ok"])
            self.assertEqual(variables["toney-warn"], colors["warn"])
            self.assertEqual(variables["toney-border"], colors["border"])
            self.assertEqual(variables["toney-rule"], colors["rule"])
            self.assertEqual(variables["toney-value"], colors["text"])

    def test_the_palette_of_an_unknown_theme_is_the_default(self):
        self.assertIs(palette("nonsense"), TOKYO_NIGHT)

    def test_the_palette_of_a_theme_is_its_own(self):
        self.assertIs(palette("toney-light"), TONEY_LIGHT)


class DecisionColorTest(unittest.TestCase):
    """The colour of a decision."""

    def test_a_blocked_decision_is_red(self):
        self.assertEqual(decision_color("block", TOKYO_NIGHT), TOKYO_NIGHT["block"])

    def test_an_allowed_decision_is_green(self):
        self.assertEqual(decision_color("allow", TOKYO_NIGHT), TOKYO_NIGHT["ok"])

    def test_a_cached_decision_is_green(self):
        self.assertEqual(decision_color("cache", TOKYO_NIGHT), TOKYO_NIGHT["ok"])

    def test_an_unknown_decision_is_dim(self):
        self.assertEqual(decision_color("hmm", TOKYO_NIGHT), TOKYO_NIGHT["dim"])

    def test_the_colour_follows_the_palette(self):
        self.assertEqual(decision_color("block", TONEY_LIGHT), TONEY_LIGHT["block"])


if __name__ == "__main__":
    unittest.main()
