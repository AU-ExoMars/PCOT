# PySide6 migration — things to check later

Working notes for the `pyside6` branch. Not permanent documentation — delete once the
migration is merged and verified.

## Environment / packaging

- [x] `matplotlib` resolved up to `3.10.9` (from the `^3.5.0` range) as a side effect of the
  Python 3.11 / PySide6 resolve — confirmed working (`mplwidget.py` / `spectrumwidget.py`
  exercised via the promoted-widgets checks below).
- [x] Confirm `proctools = "^0.2.1"` doesn't itself depend on PySide2 — confirmed working
  (PDS4 import exercised, Jim 2026-07-15).
- [x] Confirm `pds4-tools = "^1.2"` works correctly under numpy 1.26 / Python 3.11 —
  confirmed with an actual PDS4 data import (Jim, 2026-07-15).

## Cross-platform

- [x] Actually run the app on Ubuntu (not just resolve deps) — runs under Ubuntu 26
  (Jim, 2026-07-15).
- [x] Actually run the app on macOS (Apple Silicon) — runs; no repeat of the old
  PySide2/shiboken2 Rosetta problems. Confirmed by Helen Miles on an M4 Pro
  (November 2024 model) running macOS Tahoe 26.5 (2026-07-15).

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

- [x] Unscoped enum access (e.g. `Qt.AlignLeft`, `Qt.AlignTop` in `canvas.py`,
  `collapser.py`) — PySide6 forwards most of these for compatibility, but the shim is a
  deprecated transition aid and the stubs don't declare the old names (hence IDE warnings).
  **Fixed by a codebase-wide sweep to Qt6 scoped enums** (383 rewrites, 56 files): a script
  found every `X.Member` candidate, resolved it through the live PySide6 shim, and rewrote
  it to exactly the scoped member the shim returns (`Qt.Vertical` →
  `Qt.Orientation.Vertical`), so every replacement is equivalent by construction. Two
  manual fixes for Qt5 QFlags-alias spellings: `QFileDialog.Options()` →
  `QFileDialog.Option(0)` (`config.py`) and the `Qt.ItemFlags` return annotation →
  `Qt.ItemFlag` (`ui/tablemodel.py`). Verified: rescan finds 0 remaining, import sweep of
  all `pcot` modules clean (except the known-dead `ui/number.py`), full pytest matches the
  pre-sweep baseline (1018 passed, 2 xfailed, only the known-unrelated
  `test_disabled_nodes_dont_run` failure), GUI launches and runs. (`oldconf.py` is
  untracked and was deliberately left with its deprecated `Options()` alias.)
- [x] High-DPI rendering — no `AA_EnableHighDpiScaling`/`AA_UseHighDpiPixmaps` flags found (Qt6
  makes high-DPI scaling always-on). Visual check done at `QT_SCALE_FACTOR=1.5` (Jim,
  2026-07-15); found and fixed one real bug plus some latent sub-pixel issues:
  - **Canvas cursor hotspot offset at fractional scale** (the visible bug: registered point
    ~8 device px up-left of the crosshair at 150%, absent at 1x). Root cause is a Qt
    asymmetry, verified in Qt 6.11's `qwindowscursor.cpp`: the *pixmap*-cursor path scales
    both sprite and hotspot for HiDPI, but the monochrome *bitmap+mask* path (which the
    canvas XOR crosshair uses) scales only the bitmaps and passes the hotspot through
    unscaled. Fixed in `canvas.py:getCursor` by building the bitmaps pre-scaled to the
    screen DPR and tagging them with it (Qt's scaling becomes a no-op; hotspot given in
    device px). Windows-only path; other platforms unchanged; reduces to the old 32/16
    values at 1x. Cursor is cached, so a DPR change mid-session (mixed-DPI monitor drag)
    isn't handled.
  - Latent canvas precision fixes made along the way (all scale factors): mouse mapping and
    ROI/annotation painter now use the scale the image is *actually displayed at*
    (`cutw/dispw`, recorded in `paintEvent` - the displayed size is floored, so it isn't
    exactly `getScale()`) and the floored crop origin; mouse handlers use full-precision
    `e.position()` rather than integer `e.pos()` (also the brush preview in `roiedit.py`);
    the spectrum overlay dot is drawn centred instead of bounding-box-cornered.
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
- [x] `QPdfWriter.setPageSizeMM()` removed in Qt6 → `setPageSize(QPageSize(size, Unit.Millimeter))`.
  Would have crashed PDF export in `imageexport.py:exportPDF`. Fixed (1 call site).
- [x] **Long-standing pre-existing bug** (not migration-caused, found while clearing the
  IDE's scoped-enum warnings): `DQDelegate.createEditor` in `ui/tablemodel.py` read
  `self.model.tags[i].dq`, but no table model has ever had a `tags` attribute — double-
  clicking a DQ cell raised `AttributeError` since the delegate was written. Fixed to read
  `self.model.d[i].dq`, and the data list was hoisted into the `TableModel` base
  constructor so `d` is guaranteed on the base class (both subclasses updated).
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

- [x] **Checkbox `stateChanged` handlers comparing the signal argument to
  `Qt.CheckState.Checked`** — `stateChanged` emits a plain `int`, and PySide6 enums are real
  Python `enum.Enum`s, so `int == enum` is silently always `False`. The affected params could
  never be set `True`; the checkbox then visibly reverted when `onNodeChanged()` wrote the
  stale value back. Six handlers affected: `xformspectrum.py` (`ignorePixSD`, `fixedYAxis`)
  and `xformreflectance.py` (`show_patches`, `sep_plots`, `zero_fudge`,
  `simpler_data_fudge`). Fixed by connecting to `checkStateChanged` instead (Qt 6.7+, fine
  under our `^6.8` pin), which emits a genuine `Qt.CheckState`, making the enum comparison
  correct as written. All other `stateChanged` handlers were audited and are safe — they use
  `!= 0`, `isChecked()`, or ignore the argument.
- [x] Sweep the remaining `stateChanged` connections over to `checkStateChanged`
  (`stateChanged` is deprecated from Qt 6.9): done for `cameras/show.py`,
  `inputs/pds4input.py`, `ui/canvas.py`, `ui/dqwidget.py`, `ui/taggedaggregates/editors.py`,
  and xforms `circ`, `multidot`, `painted`, `pct`, `pctpatchdetection`, `poly`, `rect`,
  `roicull`, `roiexpr`, `roidq`. Handlers taking the state argument switched from `!= 0` to
  `== Qt.CheckState.Checked`; `Qt` imports added where missing (`circ`, `painted`, `poly`,
  `rect`, `roidq`). Zero `stateChanged.connect` calls remain in `src/`.

## Dark mode / Fusion style

- The Windows style override in `app.py:run()` changed from `windowsvista` to `fusion`.
  `windowsvista` is light-only (Qt keeps a light palette when it's active, so dark mode
  never engages); Fusion is palette-driven and follows the system colour scheme (Qt 6.5+),
  while still keeping the compact stacked spin-box arrows that motivated overriding the
  `windows11` default in the first place.
- [x] ~~Interim: light colour scheme pinned~~ — pinned via
  `app.styleHints().setColorScheme(Qt.ColorScheme.Light)` while the audit below was done,
  then **removed** (2026-07-20) now that the audit is complete; `app.py:run()` no longer
  touches the colour scheme at all and just follows the system setting.
- [x] **Audit hardcoded light-assuming stylesheet colours, then remove the light pin.**
  Done 2026-07-20. New `pcot/ui/theme.py` holds every colour that doesn't map onto a Qt
  palette role, with light/dark variants picked via `isDarkMode()` (reads
  `QApplication.styleHints().colorScheme()`, called fresh each time — no live
  scheme-switching support, as planned):
  - *Stale/needs-rerun red buttons* (`xformexpr`, `xformspectrum`, `xformhist`,
    `xformreflectance`, `xformtests`) → `theme.setStaleStyle(button, stale)`. `ui/tabs.py`'s
    generic Run button (a slightly different red, since it means "disabled by autorun and
    not yet run" rather than "click to update") → `theme.setDisabledRunStyle(button,
    needsRun)`, kept as a separate constant rather than merged into the first to avoid any
    visible colour change.
  - *Warning labels* (`ui/canvas.py`'s missing-filter-data / bad-pixels labels, red-on-white)
    → `theme.warningLabelStyle()`.
  - *Error text* (`ui/tabs.py`'s dark-red error label — not called out explicitly in the
    original plan, but the same problem: low contrast on a dark background) →
    `theme.errorLabelStyle()`.
  - *Macro/favourite tagging* — the yellow palette-button tint (`palette.py`, was
    `rgb(220,220,140)`) → `theme.macroTagStyle()`; the pale-yellow macro editor window
    background (`ui/graphview.py`, was `rgb(255,255,220)`) → `theme.macroWindowStyle()`.
  - *Input method-select buttons* (`ui/inputs.py`'s active/inactive highlighting, not called
    out explicitly in the original plan but the same category) → `theme.methodButtonStyle
    (active)`; the hardcoded `border-color:black` became `palette(mid)` so the border doesn't
    vanish/clash on a dark palette.
  - *Colour swatch buttons* (`xformrect`, `xformmultidot`, `xformpoly`, `xforminset`,
    `xformpainted`, `xformroiexpr`, `xformroidq`, `xformcolourmap`, `xformcirc`,
    `xformcomment`) — genuine user-chosen data, kept literal via `theme.setSwatchColour(button,
    r, g, b)`, which also fixes the pre-existing issue of 8 of the 9 not setting a
    contrasting label colour (`xformcomment` already did this per-colour; the others just
    had no text-colour rule at all, so a very light or very dark chosen colour could make
    the "Colour" caption unreadable — now all 9 go through the same contrast logic).
  - *Colours restating the default* — `ui/tabs.py`'s `rgb(240,240,240)` lower-panel
    background (essentially the stock light window colour) deleted outright;
    `ui/collapser.py`'s hardcoded `background-color: white` on `CollapserSection`'s content
    area changed to `palette(base)`.
  - **Node graph view (`ui/graphscene.py`)** — found by Jim visually testing dark mode after
    the rest of the audit: the `QGraphicsScene` canvas itself already follows the palette
    (dark grey via Fusion in dark mode), but connector arrows, connector name labels, node
    box borders, and connector-pad (`GConnectRect`) borders are drawn with `QPen`/`QBrush`
    directly, not QSS, so they don't pick up the palette automatically and were hardcoded
    black — invisible against a dark canvas. Added `theme.graphLineColor()` (black in light
    mode, light grey in dark mode) and used it for: `GArrow`'s pen for compatible
    connections (incompatible stays red — semantic, fine on either background), the two
    `GText` connector-name labels in `makeConnectors`, `GMainRect`'s border pen in
    `setColourToState()` (was unconditionally `(0,0,0)` when enabled), and `GConnectRect`'s
    border pen (previously unset, so it used Qt's default black cosmetic pen — the last of
    these was missed on the first pass and caught by Jim testing again). Node box *fill* and
    title text were already fine untouched: `getDefaultRectColour`/`getTextColour` default
    to white/black and the box is always a fixed light colour regardless of scheme, so black
    title text inside it never had a contrast problem. Confirmed working in both light and
    dark mode by Jim (2026-07-20).
  - matplotlib widgets (`mplwidget.py`) were checked and already don't override any
    background — plots stay on matplotlib's own white figure background regardless of the
    Qt palette, which is the deliberate choice (better for export).
  - Verified: full pytest matches the established baseline (1018 passed, 2 xfailed, only the
    pre-existing unrelated `test_disabled_nodes_dont_run` failure); all touched modules
    import cleanly.

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

- `mkdocs/docs/devguide/plugins.md` and `mkdocs/docs/gettingstarted/installrun.md` have
  since been updated elsewhere and no longer mention PySide2 (re-checked 2026-07-19).
- [x] `mkdocs/docs/gettingstarted/genbrushes.py` — imports switched to `PySide6`; also
  updated the two unscoped enum uses it had (`QImage.Format_RGB888` →
  `QImage.Format.Format_RGB888`, `Qt.white` → `Qt.GlobalColor.white`), verified against the
  live PySide6 shim. Only other `.py` files under `mkdocs/` are mkdocs build tooling with no
  Qt/PySide usage, so nothing else to migrate there.

## Functional verification (once rename is done)

- [x] App now launches and stays running (was previously crashing with `0xC0000005` before
  any code ran).
- [x] General smoke test of the full app: node graph canvas, tabs, spectrum/matplotlib
  widgets, dialogs (`.exec()` sites). Canvas/tabs/matplotlib covered by the promoted-widget
  checks below; all GUI/CLI-reachable `.exec()` dialogs exercised and working
  (Jim, 2026-07-15): settings editor (menu and `pcot config`), node rename, macro rename,
  multifile preset dialog (incl. preset save/rename name dialogs), raw loader settings,
  import-from-document dialog, spectrum reorder, reflectance gradients table, colourmap
  colour-stop picker, PCT patch detection help box. (`configui.py:107` is in a dev-only
  `runtest()` harness, not reachable from the app; `app.exec()` is the main loop.)

### Promoted widgets to exercise (extracted from all 57 `.ui` files' `<customwidgets>`
sections — confirms `loadUi`/`UiLoader.createWidget` resolves each one correctly under
PySide6). `tabtest.ui`/`NumberWidget` deliberately excluded — confirmed dead/unreachable
above. **All exercised manually and working (Jim, 2026-07-15).**

- [x] `Canvas` (`pcot.ui.canvas`) — by far the most common, used in ~30 tab/input `.ui` files
- [x] `DataWidget` (`pcot.ui.datawidget`) — `inputparc.ui`, `tabdata.ui`, `tabexpr.ui`
- [x] `GraphView` (`pcot.ui.graphview`) — `main.ui`
- [x] `TextEditWithHelp` (`pcot.ui.textedit`) — `main.ui`
- [x] `PlainTextEditWithHelp` (`pcot.ui.textedit`) — `tabexpr.ui`
- [x] `Collapser` (`pcot.ui.collapser`) — `main.ui`
- [x] `MplWidget` (`pcot.ui.mplwidget`) — `showcamsrefls.ui`, `tabcurve.ui`,
  `tabhistogram.ui`, `tabreflectance.ui`, `tabspectrum.ui`
- [x] `LinearSetWidget` (`pcot.ui.linear`) — `inputpdsfile.ui`
- [x] `VariantWidget` (`pcot.ui.variantwidget`) — `tabbinop.ui`
- [x] `DatumTypeWidget` (`pcot.ui.variantwidget`) — `tabconnector.ui`
- [x] `Gradient` (`pcot.ui.gradient`) — `tabcolmap.ui`
- [x] `DQWidgetVertical` (`pcot.ui.dqwidget`) — `tabdqmod.ui`
- [x] `DQWidget` (`pcot.ui.dqwidget`) — `tabroidq.ui`
- [x] `TableView` (`pcot.ui.tablemodel`) — `tabgen.ui`, `tabpixtest.ui`, `tabroiexpr.ui`
- [x] `MouseReleaseSpinBox` (`pcot.ui.smallwidgets`) — `tabmultidot.ui`
- [x] `ModeWidget` (`pcot.xforms.xformmultidot`) — `tabmultidot.ui`
