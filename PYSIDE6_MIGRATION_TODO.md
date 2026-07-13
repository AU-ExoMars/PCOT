# PySide6 migration — things to check later

Working notes for the `pyside6` branch. Not permanent documentation — delete once the
migration is merged and verified.

## Environment / packaging

- [ ] `matplotlib` resolved up to `3.10.9` (from the `^3.5.0` range) as a side effect of the
  Python 3.11 / PySide6 resolve — do a sanity check that nothing in `mplwidget.py` /
  `spectrumwidget.py` relies on older matplotlib behaviour.
- [ ] Confirm `proctools = "^0.2.1"` doesn't itself depend on PySide2 (never actually checked
  this — got interrupted mid-check earlier in the migration).
- [ ] Confirm `pds4-tools = "^1.2"` works correctly under numpy 1.26 / Python 3.11 with an
  actual PDS4 load, not just a clean `poetry install`.

## Cross-platform

- [ ] Actually run the app on Ubuntu (not just resolve deps) — check for the `libxcb-cursor0`
  runtime issue documented in the README.
- [ ] Actually run the app on macOS (Apple Silicon) — confirm no repeat of the old
  PySide2/shiboken2 Rosetta problems now that PySide6 ships native arm64 wheels.

## Source rename (`PySide2` → `PySide6`)

- [x] `src/pcot/ui/uiloader.py`
- [x] Remaining files importing `PySide2` — bulk-renamed across all of `src/` (0 left).
- [x] 19 `.exec_()` calls → `.exec()` (removed in Qt6).
- [x] 6 `QAction` references — moved from `QtWidgets` to `QtGui` in Qt6 (`palette.py`,
  `ui/mainwindow.py`, `ui/tabs.py`).

## Fixed crashes found by actually running the app

- [x] **Root cause of the `0xC0000005` startup crash on Windows**: `palette.py` created four
  `QAction`s as class-body attributes, which run at module-import time — long before
  `pcot.setup()` creates the `QApplication`. PySide2/Qt5 tolerated constructing a `QAction`
  with no `QApplication`; PySide6/Qt6 hard-crashes natively instead of raising a Python
  exception. Fixed by making them lazily-created class attributes (set on first instance
  construction in `__init__`).
- [x] `pcotplugins/example1.py` and `pcotplugins/save_envi.py` — outside `src/`, so the bulk
  rename missed them. Both still imported `PySide2` and would have failed to load once the
  `QAction` crash was fixed (all `.py` files in `pcotplugins/` are auto-loaded at startup).
  `save_envi.py` also had the `QAction` QtWidgets→QtGui move to make.

## Qt6 behavioural differences to spot-check once the rename compiles

- [ ] Unscoped enum access (e.g. `Qt.AlignLeft`, `Qt.AlignTop` in `canvas.py`,
  `collapser.py`) — PySide6 forwards most of these for compatibility, but worth confirming
  none silently misbehave rather than trusting the shim blindly.
- [ ] High-DPI rendering — no `AA_EnableHighDpiScaling`/`AA_UseHighDpiPixmaps` flags found (Qt6
  makes high-DPI scaling always-on), but do a visual check on a HiDPI display since default
  behaviour changed even without explicit flags.
- Startup log shows `Designer: ... renderHints ... QPainter::HighQualityAntialiasing ...
  could not be read` — that enum was removed in Qt6. Traced to the `.ui` files, which
  predate Qt5 (created with the Qt4 Designer) and are already slightly out of date, so this
  is an accepted pre-existing quirk rather than something introduced by the migration — not
  chasing it unless it turns out to be visually damaging.

## More crashes/errors found running the app manually

- [x] `QLayout.setMargin()` removed in Qt6 → `setContentsMargins()`. Crashed
  `ui/canvas.py`'s splitter setup via `ui/__init__.py:decorateSplitter`. Fixed (1 call site).
- [x] `Qt.MidButton` removed in Qt6 → `Qt.MiddleButton`. Fixed 2 call sites in `canvas.py`
  (mouse press/release handlers for pan-by-middle-click).
- [x] `QWheelEvent.pos()` removed entirely in Qt6 (confirmed via `hasattr` check — unlike
  `QMouseEvent`/`QDropEvent`, which still have a deprecated-but-present `pos()`). Replaced
  with `.position().toPoint()` at all 4 call sites: `canvas.py` (x2, `wheelEvent`),
  `graphview.py` (x1), `linear.py` (x1). Confirmed no other `.pos()` calls in the codebase
  are on `QWheelEvent` objects.
- **Not fixed, flagged instead**: `ui/number.py:12` — `changed = QtCore.pyqtSignal(float)`.
  `pyqtSignal` is a **PyQt** API, not PySide — PySide's equivalent is `Signal`. This means
  `NumberWidget` was already broken under PySide2 (would have raised the same kind of
  `AttributeError` at class-definition time), so it's a pre-existing bug rather than
  something the migration caused. Confirmed **dead/unreachable**: `NumberWidget` is only
  promoted in `assets/tabtest.ui`, and nothing in `src/`, `tests/`, or `pcotplugins/`
  references `tabtest.ui` or `NumberWidget` — no xform wires it up, and `TabGeneric` doesn't
  load `.ui` files by name convention. Not a live risk; left alone.
- [x] `QFileDialog.getExistingDirectory()` crashed with a `TypeError` (`PosixPath` where `str`
  expected) in `mainwindow.py:_ensureDataPresent` — found running on the Ubuntu VM, but not
  Linux-specific: `pcot.config.getDefaultDir()` returns a `pathlib.Path` (schema in
  `config.py`), and PySide6 enforces the `str` type strictly where PySide2's SIP bindings
  didn't. Never hit on the Windows dev box because that config already had `cameras`/
  `reflectances` directories set, so the empty-check loop never reached the dialog call.
  Every other file-dialog call site already wraps the value in `os.path.expanduser(...)`,
  which stringifies via `os.fspath` as a side effect — this one skipped that. Fixed by
  wrapping in `str(...)` at the one offending call site.
- [x] **GNOME/Wayland dialog decoration bug**: on the Ubuntu VM (GNOME/Wayland session),
  `QDialog`s (e.g. `cameras/show.py`'s "Filters and Reflectances" dialog) rendered with only
  a minimal flat Qt-drawn title bar (no real OS decoration) and overlapped the main window.
  `qt6-wayland` (Ubuntu's name for Debian's `qtwayland6`) was installed, so not a
  missing-package issue — Mutter simply doesn't give these windows a server-side decoration.
  Confirmed workaround: `QT_QPA_PLATFORM=xcb` (routes through XWayland) restores normal
  decorations. Implemented as an auto-detected default: `app.py:setup_qt_platform()` now
  checks `XDG_CURRENT_DESKTOP` and forces `xcb` when running GNOME on Wayland with no X11
  `DISPLAY`; overridable via the new `qt_platform` config key (`auto`/`native`/`xcb`,
  `config.py`) for other desktops (KDE's Wayland decorations are reportedly fine) or if a
  future GNOME fixes this. Also fixed a related gap while in there: `setup_qt_platform()`
  was only ever reached via `checkApp()` (used by headless/library callers) — the
  interactive `app.run()` path built the `QApplication` directly without calling it first, so
  none of this (including the pre-existing headless/offscreen detection) ever actually ran on
  a normal GUI launch. Now called explicitly in `run()` before `QApplication` is constructed.
  Not yet tested on KDE or other Wayland compositors — worth a spot-check if anyone runs one.
- [x] Config editor (`taggedaggregates/editors.py:MaybeEditor.setStateFromInnerEditor`)
  crashed with a `TypeError` calling `setChecked(Qt.Checked)`/`setChecked(Qt.Unchecked)` —
  PySide6's `QAbstractButton.setChecked()` requires a plain `bool`, not the `Qt.CheckState`
  enum PySide2 tolerated. Fixed both call sites to `True`/`False`; removed the now-unused
  `Qt` import from that file.
- [x] Input window method-select buttons (RGB/Multifile/etc.) showed no text. Root cause:
  `ui/inputs.py:MethodSelectButton.showActive()` sets `padding: 40px` in its stylesheet,
  while `sizeHint()` forces the button height down to `textSize.height() + 15` (~31px) —
  40px padding on all sides leaves no room for the text, so it never draws. Confirmed via a
  scratch repro (rendered the button under `windows11`, `windowsvista`, and `Fusion` styles)
  that this reproduces identically under all three, i.e. **not** caused by the `windowsvista`
  style change above — a latent pre-existing bug, just not previously noticed. Fixed by
  changing `padding: 40px` to `padding: 4px`.

## Dark mode / Fusion style

- The Windows style override in `app.py:run()` changed from `windowsvista` to `fusion`.
  `windowsvista` is light-only (Qt keeps a light palette when it's active, so dark mode
  never engages); Fusion is palette-driven and follows the system colour scheme (Qt 6.5+),
  while still keeping the compact stacked spin-box arrows that motivated overriding the
  `windows11` default in the first place.
- [x] **Interim: light colour scheme pinned** in `app.py:run()` via
  `app.styleHints().setColorScheme(Qt.ColorScheme.Light)` (`QStyleHints.setColorScheme` is
  Qt 6.8+, which `pyproject.toml`'s `PySide6 = "^6.8"` guarantees). This stops a dark system
  theme applying to PCOT until the stylesheet audit below is done, so the Fusion switch
  lands with no visual change. Remove the pin as the final step of that audit.
- [ ] **Audit hardcoded light-assuming stylesheet colours, then remove the light pin.**
  Many `setStyleSheet` calls hardcode colours that would clash with a dark palette. The
  plan, by category:
  - *Colour swatch buttons* (`xformrect`, `xformmultidot`, `xformpoly`, `xforminset`,
    `xformpainted`, `xformroiexpr`, `xformroidq`, `xformcolourmap`, `xformcirc`) show a
    user-chosen annotation colour — these are data, not theming, so keep them literal;
    just also set a contrasting text colour so the label reads on any swatch
    (pre-existing issue).
  - *Semantic status colours* — the "stale, needs re-run" red buttons
    (`rgb(255,100,100)` in `xformexpr`, `xformspectrum`, `xformhist`, `xformreflectance`,
    `xformtests`; `rgb(200,100,100)` in `ui/tabs.py`), the red-on-white warning labels in
    `ui/canvas.py`, the yellow group headers in `palette.py` and help prompt in
    `ui/graphview.py`. Fix via a small new `pcot/ui/theme.py`: detect the scheme once at
    startup (`QApplication.styleHints().colorScheme()`), expose named colour constants
    (`STALE_BUTTON_BG`, `WARNING_FG`/`BG`, `GROUP_HEADER_BG`, …) with light/dark variants,
    plus helpers like `setStaleStyle(button, stale: bool)` for the toggle pattern
    duplicated across ~6 files.
  - *Colours restating the default* — e.g. `ui/tabs.py`'s `rgb(240,240,240)` lower area is
    essentially the stock light window colour: delete it, or where a distinct tint is
    genuinely wanted use QSS `palette(role)` syntax (`background-color: palette(window)`
    etc.), which tracks the palette with no Python-side logic. Prefer `palette(role)`
    wherever a colour maps onto a palette role; the theme module is for colours that
    don't (yellows, status reds).
  - Deliberately **not** supporting live scheme switching (`colorSchemeChanged` +
    re-applying everything): read the scheme at startup and be done.
  - Decide deliberately whether matplotlib widgets (`mplwidget.py`) keep white-background
    plots in dark mode (probably yes — better for export).
  - Rejected alternative: one app-wide QSS with dynamic properties
    (`QPushButton[stale="true"]`) — the "proper Qt" route, but PCOT toggles styles
    imperatively all over, so it means touching every call site plus
    unpolish/repolish boilerplate for less benefit than the theme module.

## pytest run

- [x] `QFontMetrics.width()` removed in Qt6 (renamed `horizontalAdvance()`) — was breaking 4
  tests (`test_outputs.py::test_cannot_append_non_parc_images`,
  `test_outputs.py::test_explicit_image_format`, `test_runner.py::test_colourmap`,
  `test_runner.py::test_image_export_sizes`). Fixed the 4 call sites: `utils/annotations.py`,
  `ui/spectrumwidget.py`, `xforms/xformcolourmap.py` (x2).
- `tests/graphs/test_disabled.py::test_disabled_nodes_dont_run` still fails (reproduces in
  isolation, not test-order pollution) — confirmed **known pre-existing issue, unrelated to
  the PySide6 migration** (per Jim). Not chasing further here.
- Full suite otherwise green: 1014 passed, 2 xfailed.

## Docs/examples still referencing PySide2 (non-blocking)

- [ ] `mkdocs/docs/devguide/plugins.md`, `mkdocs/docs/gettingstarted/genbrushes.py`,
  `mkdocs/docs/gettingstarted/installrun.md` — published docs with PySide2 example code/
  instructions. Not load-bearing for the app itself, but will mislead anyone following them.

## Functional verification (once rename is done)

- [x] App now launches and stays running (was previously crashing with `0xC0000005` before
  any code ran).
- [ ] General smoke test of the full app: node graph canvas, tabs, spectrum/matplotlib
  widgets, dialogs (`.exec()` sites).

### Promoted widgets to exercise (extracted from all 57 `.ui` files' `<customwidgets>`
sections — confirms `loadUi`/`UiLoader.createWidget` resolves each one correctly under
PySide6). `tabtest.ui`/`NumberWidget` deliberately excluded — confirmed dead/unreachable
above.

- [ ] `Canvas` (`pcot.ui.canvas`) — by far the most common, used in ~30 tab/input `.ui` files
- [ ] `DataWidget` (`pcot.ui.datawidget`) — `inputparc.ui`, `tabdata.ui`, `tabexpr.ui`
- [ ] `GraphView` (`pcot.ui.graphview`) — `main.ui`
- [ ] `TextEditWithHelp` (`pcot.ui.textedit`) — `main.ui`
- [ ] `PlainTextEditWithHelp` (`pcot.ui.textedit`) — `tabexpr.ui`
- [ ] `Collapser` (`pcot.ui.collapser`) — `main.ui`
- [ ] `MplWidget` (`pcot.ui.mplwidget`) — `showcamsrefls.ui`, `tabcurve.ui`,
  `tabhistogram.ui`, `tabreflectance.ui`, `tabspectrum.ui`
- [ ] `LinearSetWidget` (`pcot.ui.linear`) — `inputpdsfile.ui`
- [ ] `VariantWidget` (`pcot.ui.variantwidget`) — `tabbinop.ui`
- [ ] `DatumTypeWidget` (`pcot.ui.variantwidget`) — `tabconnector.ui`
- [ ] `Gradient` (`pcot.ui.gradient`) — `tabcolmap.ui`
- [ ] `DQWidgetVertical` (`pcot.ui.dqwidget`) — `tabdqmod.ui`
- [ ] `DQWidget` (`pcot.ui.dqwidget`) — `tabroidq.ui`
- [ ] `TableView` (`pcot.ui.tablemodel`) — `tabgen.ui`, `tabpixtest.ui`, `tabroiexpr.ui`
- [ ] `MouseReleaseSpinBox` (`pcot.ui.smallwidgets`) — `tabmultidot.ui`
- [ ] `ModeWidget` (`pcot.xforms.xformmultidot`) — `tabmultidot.ui`
