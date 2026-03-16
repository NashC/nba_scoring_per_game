from __future__ import annotations

from typing import Any

from dash import html

_DEFAULT_SIZES = {"nav": 48, "hero": 280}
_REDUCED_MOTION_VALUES = {None: "system", True: "true", False: "false"}


def LiveLogo3D(
    variant: str = "nav",
    size: int | float | str | None = None,
    animated: bool = True,
    interactive: bool = True,
    glow: bool = True,
    reduced_motion_override: bool | None = None,
    decorative: bool = True,
    aria_label: str | None = None,
    class_name: str | None = None,
    id: str | None = None,
) -> html.Div:
    if variant not in _DEFAULT_SIZES:
        raise ValueError("variant must be 'nav' or 'hero'")
    if reduced_motion_override not in (None, True, False):
        raise ValueError("reduced_motion_override must be None, True, or False")

    resolved_size = _normalize_size(size if size is not None else _DEFAULT_SIZES[variant])
    classes = " ".join(
        part
        for part in (
            "live-logo",
            f"live-logo--{variant}",
            "live-logo--animated" if animated else "live-logo--static",
            "live-logo--interactive" if interactive else "live-logo--passive",
            "live-logo--glow" if glow else "live-logo--no-glow",
            class_name,
        )
        if part
    )
    props: dict[str, Any] = {
        "className": classes,
        "style": {"--live-logo-size": resolved_size},
        "data-live-logo": "true",
        "data-variant": variant,
        "data-size": resolved_size,
        "data-animated": str(animated).lower(),
        "data-interactive": str(interactive).lower(),
        "data-glow": str(glow).lower(),
        "data-reduced-motion": _REDUCED_MOTION_VALUES[reduced_motion_override],
        "children": [
            html.Canvas(className="live-logo-canvas", **{"aria-hidden": "true"}),
            _build_static_logo_fallback(),
        ],
    }
    if id is not None:
        props["id"] = id

    if decorative:
        props["aria-hidden"] = "true"
    else:
        props["role"] = "img"
        props["aria-label"] = aria_label or "Heat Check live logo"

    return html.Div(**props)


def build_brand_lockup(
    title: str | None = "🏀 🔥 Heat Check",
    kicker: str | None = "The NBA's Greatest Single Game Scoring Performances",
    *,
    id: str | None = None,
    class_name: str | None = None,
) -> html.Div:
    copy_children = []
    if title:
        copy_children.append(html.Div(title, className="brand-lockup-title"))
    if kicker:
        copy_children.append(html.Div(kicker, className="brand-lockup-kicker"))

    classes = " ".join(part for part in ("brand-lockup", class_name) if part)
    props: dict[str, Any] = {
        "className": classes,
        "children": [
            html.Div(
                className="brand-lockup-copy",
                children=copy_children,
            ),
        ],
    }
    if id is not None:
        props["id"] = id
    return html.Div(**props)


def _build_static_logo_fallback() -> html.Div:
    return html.Div(
        className="live-logo-fallback",
        **{"aria-hidden": "true"},
        children=[
            html.Div(className="live-logo-fallback-aura"),
            html.Div(
                className="live-logo-fallback-flame-stack",
                children=[
                    html.Span(className="live-logo-fallback-flame live-logo-fallback-flame--outer"),
                    html.Span(className="live-logo-fallback-flame live-logo-fallback-flame--mid"),
                    html.Span(className="live-logo-fallback-flame live-logo-fallback-flame--core"),
                ],
            ),
            html.Div(className="live-logo-fallback-shadow"),
            html.Div(
                className="live-logo-fallback-ball",
                children=[
                    html.Span(className="live-logo-fallback-grain"),
                    html.Span(className="live-logo-fallback-seam live-logo-fallback-seam--left"),
                    html.Span(className="live-logo-fallback-seam live-logo-fallback-seam--right"),
                    html.Span(className="live-logo-fallback-seam live-logo-fallback-seam--top"),
                    html.Span(className="live-logo-fallback-seam live-logo-fallback-seam--bottom"),
                    html.Span(className="live-logo-fallback-highlight"),
                ],
            ),
        ],
    )


def _normalize_size(size: int | float | str) -> str:
    if isinstance(size, (int, float)):
        if size <= 0:
            raise ValueError("size must be positive")
        return f"{size:g}px"
    return str(size)
