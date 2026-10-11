"""Theme tokens. Every theme is checked for WCAG AA text contrast in tests."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    name: str
    emoji: str
    dark: bool
    bg_start: str
    bg_mid: str
    bg_end: str
    text: str
    text_muted: str
    heading: str
    surface: str  # translucent card fill
    surface_solid: str  # opaque equivalent used for contrast checks
    border: str
    accent: str
    accent_2: str
    accent_text: str
    input_bg: str
    sidebar_bg: str
    chart_series: tuple[str, ...]
    chart_surface: str
    chart_grid: str


# Categorical chart palette validated with the dataviz validator (light & dark surfaces).
LIGHT_SERIES = ("#6250d6", "#e87ba4", "#2a78d6", "#1baf7a", "#eda100")
DARK_SERIES = ("#9085e9", "#d55181", "#3987e5", "#199e70", "#c98500")

THEMES: dict[str, Theme] = {
    "Unicorn Dream": Theme(
        "Unicorn Dream", "🦄", False, "#FFF9FD", "#FFE1EF", "#E9DDFF", "#4A315E", "#5F4677", "#4A315E",
        "rgba(255,255,255,0.62)", "#FCF4FB", "rgba(183,156,237,0.45)", "#B79CED", "#F7B7D2", "#2E1C3F",
        "#FFFFFF", "linear-gradient(180deg,#FFF0F7 0%,#EFE6FF 100%)", LIGHT_SERIES, "#FFFFFF", "#EEE6F7",
    ),
    "Lavender Galaxy": Theme(
        "Lavender Galaxy", "🌌", False, "#F6F1FF", "#E7DBFF", "#D6C4FF", "#33204A", "#4F3B68", "#33204A",
        "rgba(255,255,255,0.58)", "#EFE7FF", "rgba(150,120,220,0.45)", "#9F7FE6", "#C9E8FF", "#1E1030",
        "#FFFFFF", "linear-gradient(180deg,#EFE6FF 0%,#DCC8FF 100%)", LIGHT_SERIES, "#FFFFFF", "#E9E1F7",
    ),
    "Rose Gold Luxury": Theme(
        "Rose Gold Luxury", "🌹", False, "#FFF8F4", "#FBE6DF", "#F2D3CC", "#4A2E2B", "#664541", "#4A2E2B",
        "rgba(255,255,255,0.6)", "#FBEFEA", "rgba(217,165,160,0.55)", "#D9A5A0", "#FFF0D5", "#2E1A18",
        "#FFFFFF", "linear-gradient(180deg,#FFF3EE 0%,#F6DCD6 100%)", LIGHT_SERIES, "#FFFFFF", "#F1E4E0",
    ),
    "Midnight Mermaid": Theme(
        "Midnight Mermaid", "🧜‍♀️", True, "#101B30", "#1B2340", "#2A1B3D", "#F4F0FF", "#D4CCEA", "#FFFFFF",
        "rgba(255,255,255,0.08)", "#1E2440", "rgba(127,227,208,0.35)", "#7FE3D0", "#B79CED", "#0E1A2B",
        "#1E2440", "linear-gradient(180deg,#0E182B 0%,#24193A 100%)", DARK_SERIES, "#2A1B3D", "#3A2D52",
    ),
    "Pearl Princess": Theme(
        "Pearl Princess", "🫧", False, "#FFFFFF", "#FFF7EC", "#FFF0D5", "#4A315E", "#5F4677", "#4A315E",
        "rgba(255,255,255,0.7)", "#FFF8F0", "rgba(217,165,160,0.4)", "#F7B7D2", "#DCC8FF", "#2E1C3F",
        "#FFFFFF", "linear-gradient(180deg,#FFFFFF 0%,#FFF0D5 100%)", LIGHT_SERIES, "#FFFFFF", "#F2ECE4",
    ),
}
DEFAULT_THEME = "Unicorn Dream"


def get_theme(name: str) -> Theme:
    return THEMES.get(name, THEMES[DEFAULT_THEME])


def _luminance(hex_color: str) -> float:
    hex_color = hex_color.lstrip("#")
    channels = [int(hex_color[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast_ratio(foreground: str, background: str) -> float:
    lighter, darker = sorted((_luminance(foreground), _luminance(background)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def css_variables(theme: Theme) -> str:
    return (
        f"--mf-bg-start:{theme.bg_start};--mf-bg-mid:{theme.bg_mid};--mf-bg-end:{theme.bg_end};"
        f"--mf-text:{theme.text};--mf-muted:{theme.text_muted};--mf-heading:{theme.heading};"
        f"--mf-surface:{theme.surface};--mf-surface-solid:{theme.surface_solid};--mf-border:{theme.border};"
        f"--mf-accent:{theme.accent};--mf-accent-2:{theme.accent_2};--mf-accent-text:{theme.accent_text};"
        f"--mf-input-bg:{theme.input_bg};--mf-sidebar-bg:{theme.sidebar_bg};"
    )
