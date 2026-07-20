"""Colours that need to differ between light and dark colour schemes.

Most widgets need nothing from here - they should just rely on the Qt palette (or QSS
`palette(role)` syntax) and they'll follow the active scheme automatically. This module is
for the handful of colours that don't map onto any palette role: status indicators ("needs
to be rerun", warnings, errors) and the yellow tint used to flag macro/favourite palette
buttons and macro editor windows.

We deliberately don't support live colour-scheme switching (listening for
QStyleHints.colorSchemeChanged and re-applying every stylesheet) - the scheme is read fresh
each time one of these helpers is called, which is fine because nothing in PCOT changes it
after startup.
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication


def isDarkMode() -> bool:
    app = QApplication.instance()
    if app is None:
        return False
    return app.styleHints().colorScheme() == Qt.ColorScheme.Dark


def _pick(light, dark):
    return dark if isDarkMode() else light


def setStaleStyle(button, stale: bool):
    """Colour a button to show it needs to be clicked to bring it up to date (a Run/Recalc/
    Replot button whose node's parameters have changed since it was last run)."""
    if stale:
        button.setStyleSheet(f"background-color: {_pick('rgb(255,100,100)', 'rgb(160,60,60)')};")
    else:
        button.setStyleSheet("")


def setDisabledRunStyle(button, needsRun: bool):
    """The generic per-tab Run button (ui/tabs.py): reddened while the node is disabled (so
    autorun won't run it for you) and hasn't been run manually yet."""
    if needsRun:
        button.setStyleSheet(f"background-color: {_pick('rgb(200,100,100)', 'rgb(130,50,50)')};")
    else:
        button.setStyleSheet("")


def errorLabelStyle() -> str:
    return f"QLabel {{ color: {_pick('rgb(200,0,0)', 'rgb(255,120,120)')}; }}"


def warningLabelStyle() -> str:
    bg = _pick('white', '#3a1a1a')
    fg = _pick('red', '#ff6b6b')
    return f"QLabel {{ background-color: {bg}; color: {fg}; }}"


def macroTagStyle() -> str:
    """Yellowish tint used to flag macro/favourite buttons in the node palette."""
    return f"background-color: {_pick('rgb(220,220,140)', 'rgb(100,95,40)')};"


def macroWindowStyle() -> str:
    """Pale yellow background for a macro's own editor window (GraphView)."""
    return f"background-color: {_pick('rgb(255,255,220)', 'rgb(60,58,30)')};"


def methodButtonStyle(active: bool) -> str:
    """Input window's method-select buttons (RGB/Multifile/...): highlight the active one."""
    if active:
        bg = _pick('rgb(200,200,255)', 'rgb(70,70,130)')
    else:
        bg = _pick('rgb(200,200,200)', 'rgb(80,80,80)')
    return (f"border-style: outset; padding: 4px; border-width: 1px; "
            f"border-color: palette(mid); background-color: {bg};")


def graphLineColor() -> QColor:
    """Colour for node-graph line art that sits directly on the QGraphicsView canvas
    background rather than inside a node's own box (which is always a fixed light colour,
    so text/borders drawn *inside* a node box don't need this - only connector arrows,
    connector name labels, and node box borders, which sit on the canvas itself and so need
    to flip along with it: the canvas background follows the palette (light grey in light
    mode, dark grey in dark mode via Fusion), but graphscene.py draws these with QPen/QBrush
    rather than QSS, so they don't get that for free."""
    return QColor(220, 220, 220) if isDarkMode() else QColor(0, 0, 0)


def setSwatchColour(button, r, g, b):
    """Set a button's background to a literal RGB colour that's genuine data (a user-chosen
    ROI/annotation colour, not theming) - kept exactly as chosen in both colour schemes -
    with a contrasting black/white label so the button's text stays legible against light or
    dark swatches."""
    button.setAutoFillBackground(True)
    t = 255 if r + g + b < (128 * 3) else 0
    button.setStyleSheet(f"background-color: rgb({r},{g},{b}); color: rgb({t},{t},{t});")
