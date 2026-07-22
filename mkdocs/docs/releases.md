# Releases

Releases are named after 
[Megalithic sites in the UK](https://m.megalithic.co.uk/asb_mapsquare.php)
running through letters of the alphabet and roughly south to north, trying to
stick with more memorable names. For a very minor release, we sometimes
don't change the letter.

For fun I've added Google Maps and NLS references to each site and a little
bit of info. You can look them up on the Megalithic Portal for more.


## Production releases
None

## Beta releases

## 1.0.0-beta DATE TBD LITTLE DENNIS

The big one: PCOT has been migrated from PySide2 (Qt5) to PySide6 (Qt6), which is why this is
the first major version bump. Most of the migration is invisible to users - it's the same UI -
but there's a long tail of small Qt6-shaped fixes alongside it, and a couple of unrelated fixes
that were sitting on `dev` at the same time.

**Because this is a major version change (PySide2 to PySide6), you'll need to run `poetry
install` again to pick up the new dependencies - your existing environment won't do it
automatically.**

* **Migrated to PySide6/Qt6** throughout the application (was PySide2/Qt5).
* Dark mode support (follows the OS theme).
* Windows now uses the Fusion style rather than the OS-native one, for consistency.
* Workaround for a GNOME/Wayland dialog decoration bug, and a config-editor checkbox crash, both
found during the migration.
* Canvas cursor hotspot and mouse-to-image mapping precision fixed at HiDPI scale factors.
* Canvas mouse-wheel zoom now actually zooms to the cursor position rather than drifting towards
the centre of the view, and middle-button panning now tracks the cursor properly instead of
moving at half speed.
* Fixes to circle ROI shift/ctrl-drag behaviour, the palette collapse/expand-all button, PDF
export, and a DQDelegate crash - all regressions found during the Qt6 migration.
* Multifile loader: left-justified bit-depth handling, and preset handling consolidated into a
single implementation (fixes a bug where presets could be double-applied).
* New `pix()` datumfunc to get a pixel value directly.
* Fixed `Value.out` to correctly use `config.data.sigfigs` (was a mutable default argument bug).
* PDS4 directory scan now skips invalid files instead of aborting the whole scan.

Site

* TODO: Google maps link
* TODO: NLS map link
* [Megalithic Portal entry](https://www.megalithic.co.uk/article.php?sid=29324)
* A promontory fort (cliff castle), probably Iron Age, on a headland at St Anthony-in-Meneage
on the Lizard - the earthworks cutting off the headland show up well on LIDAR, though on the
ground it's mostly reduced to crop marks and a bank on the sloping southern side.


## 0.13.0-beta 2026-07-03 KENWYN FOUR BURROWS

Quite a lot in this one. We don't have HRC colour correction yet, but it's
being worked on - it's a difficult problem (more accurately, getting it
into PCOT without pulling in a library that's 20 times bigger than PCOT itself
is difficult).

* [Favourites and macros](userguide/favesandmacros/index.md) - save nodes with
particular settings and also collections of nodes which work like a single node.
Both favourites and macros can be saved to archives which can be loaded on startup.
* PCOT now also has Malvar-He-Cutler and Menon (DDFAPD) demosaicing algorithms.
* Demosaicing now uses the "classical" Bayer pattern names (e.g. RGGB) and
not the rather weird OpenCV names.
* *PCA* node does both principal component analysis and decorrelation
stretches, and does so on all bands (not just the RGB representation).
* ***decorrstretch* node deprecated** - use *PCA* instead
* Search box for palette!
* [Settings dialog](userguide/settings.md) should make life easier for changing settings quickly.
* Unconnected *expr* inputs give a null datum rather than raising an
exception.
* *reflectance* node supports angle data (filter angle and $\phi$, $\theta$ for target).
* Raw loader crops overlong data and warns.
* [GUPPY](devguide/guppy.md), the Guide to Uncertainty in PCOT Python - how to write code that
propagates uncertainty.
* `TabData` is now `TabGeneric`, and if you use TaggedAggregate parameters
in your node it will incorporate an editor for those parameters.

* Refactoring of the `func_wrapper` and `stats_wrapper` mechanisms for
processing uncertainty.
* `genimg` datumfunc to quickly create images.
* Fixes to the *gen* node to make the pattern mode actually visible in the table columns.
* Better checking on "headless" setups (i.e. working on a server with no windowing system).
* New `config` subcommand for viewing/editing configuration from the command line.
* Better infinity/NaN handling when raising values to fractional powers (i.e. complex results).
* A lot of work on the system underlying the settings dialog: the
`AggregateEditorDialog`; this can also be used for node and macro params.
* Comparison operators `<` and `>`, and `ifelse` and `isnone` datumfuncs.
* Icon on canvas reset button.
* Log window can clear all text.


Site

* [Google maps](https://maps.app.goo.gl/xAyB7ho1L7fWrxbM8)
* [NLS map](https://maps.nls.uk/geo/explore/#zoom=17.6&lat=50.29125&lon=-5.14329&layers=168&b=osm&o=100&marker=50.291376,-5.143622)
* Barrow Cemetery in Cornwall, which straddles the old A30 just west of Chybucca.
Three of the barrows lie to the south, and one to the north.



## 0.12.0-beta 2026-03-04 JOANEY HOW

I've had to go quite a long way north to get a name I liked; this one's in
Somerset. There is a minor backward compatibility issue (camera data) but I'll
still make it a minor bump; most things will still work.

* Separation of camera and reflectance data
* *reflectance* node now calculates known reflectance from filter reponses
and patch reflectances
* measured filter and reflectance spectra supported (rather than simulated)
* transmission angles and patch incident stereo angles supported
* canvas spectrum widget has a variable area
* DATA type (e.g. from *spectrum* node) is now TABLE
* Better indexing operator for bands in *expr* allows e.g. `a[640,540]` or `a[R,G]`
* *decorr stretch* much improved: outputs eigenvals and SDs, permits variable
stretch, variable clipping of outliers (i.e. contrast stretch)
* archives hold metadata: type, author, date and a history if files are overwritten
* gamma correction on canvas
* multifile cache handling improvements
* many bug fixes

Site

* [Google maps](https://maps.app.goo.gl/qAyRYBYGGsFH9MbQ8)
* [NLS map](https://maps.nls.uk/geo/explore/#zoom=17.9&lat=51.17402&lon=-3.56298&layers=173&b=osm&o=100&marker=51.173872,-3.563206)
* One of three cairns on Dunkery Hill, near Minehead.


## Alpha releases

## 0.11.0-alpha 2025-10-24 IGNIOC STONE

Fenton, where are you?

* Some UI changes and fixes
* Various internal fixes to do with object deepcopy
* Basic debayering in the RGB input method (just bilinear, edge-aware and variable number of gradients)
* Separate plots in reflectance node to help check the line-fitting visually
* Graph updates to show progress as it runs
* Ctrl-click on a node to force recalculation
* *gradient* node is now *colourmap*

Site

* [Google maps](https://maps.app.goo.gl/LP64ezJdR6zuanhf9)
* [NLS map](https://maps.nls.uk/geo/explore/#zoom=19.5&lat=50.25550&lon=-5.01631&layers=173&b=ESRIWorld&o=100&marker=50.255610,-5.016593)
* An ancient stone cross, on which is written VITALI FILI TORRICI, in the village
of St. Clement, near Truro.


## 0.10.0-alpha 2025-06-12 HALWYN ROUND

I still miss Fenton Saurus. 

* New system for storing camera data in PARC files
* Subcommand system with special commands (lscams, gencam etc.)
* Reflectance correction (given data from the camera and a calib target)
* Various objects no longer require Documents for deserialisation
* Colorchecker (i.e. Macbeth) calibration target locator
* Some new nodes and functions (roicull, getflags, reflectance..)
* Small changes to canvas DQ viewing
* Staying at Python 3.9 for now

Site

* [Google maps](https://maps.app.goo.gl/McFRBkRP1fJBJhVw5)
* [NLS map](https://maps.nls.uk/geo/explore/#zoom=17.2&lat=50.08069&lon=-5.55111&layers=173&b=LIDAR_DTM_1m&o=100&marker=50.080691,-5.551571)
* Again, not much to see today, but the site of an ancient village near
Mousehole (pronounced "Mowzel" as I'm sure you're aware), which was
[revealed by cropmarks by the drought of 1976](https://www.megalithic.co.uk/article.php?sid=48151).


## 0.9.0-alpha 2025-02-17 GODOLPHIN HILL

I'll miss Fenton Saurus, that was a great name.

* New system for node parameters - the TaggedAggregate system. All nodes
updated to this where it makes sense.
* Batch runner (`pcotbatch`) first draft, which allows a graph to be run
from the command line with inputs and nodes able to be modified with a
text file, and outputs able to be captured and saved.
* Complete rewrite of `manual register` node
* "PARC" input and output file format - allows multispectral images with
uncertainty to be stored (and other data types too)
* Various bits of refactoring
* Issue fixes
* Yet more tests
* Nodes are now created by left-click dragging from the palette
* Nodes which have been renamed from their defaults have their name text
shown in bold
* Forced to downgrade minimum Python version to 3.9 temporarily

Site

* [Google maps](https://maps.app.goo.gl/cTNRrdoFFKnP3fzz8)
* [NLS map](https://maps.nls.uk/geo/explore/#zoom=16.6&lat=50.13351&lon=-5.37000&layers=168&b=osm&o=100&marker=50.132610,-5.370510)
* A stone age village, or rather the stones thereof, between
Penzance and Helston. Oddly no reference
to it on OS maps, [but it is real](https://www.megalithic.co.uk/article.php?sid=26603).

### 0.8.0-alpha 2024-07-25 FENTON SAURUS

Yes, really: [Fenton Saurus](https://www.megalithic.co.uk/article.php?sid=8106)

* More unit tests
* colour connector "swatch" generator script
* started work on dark/flat field generator
* Datum archives - a file format (.PARC) for saving Datum objects, with an associated
input method and exporters. Required because we have no other way of saving images
with uncertainty and DQ.
* DatumStore class wraps Archive objects so we can store Datum (this is used for the datum archives)
* *expr* uses a DataWidget, as does TabData.
* 1D vectors supported as a Datum.NUMBER type. Modifications made to datumfuncs
and operators permit this. Notably, the semantics of `mean`, `sd`, `sum`, `min` and
* square bracket parsing in expressions generates vector-creation and vector-index instructions
`max` have changed to operate band-wise and generate a vector when performed on images.
* Multiband extraction, e.g. `a$[640,550,440]`.
* `.bands` property generates a vector of wavelengths, so we can do `a$b.bands`, to get
the bands in `a` that are also in `b`, in the same order as in `b`.
* `.u` property
* properties graph tests and QoL work for test building
* precedence adjustments in expressions
* getSelection in document can help get selected nodes in plugins
* serialiseFields does a deepcopy - fixes undo bugs
* fixes to *roiexpr*; it no longer keeps UI data in the node so undo works better
* Cookbook in progress, but not part of the main repository to allow it to be updated more frequently
* First release for Zenodo

Site

* [Google maps](https://maps.app.goo.gl/gZNyVnhtnWJZD7gP6)
* [NLS map](https://maps.nls.uk/geo/explore/#zoom=19.0&lat=50.18107&lon=-5.44429&layers=173&b=osm&o=100&marker=50.181070,-5.444292)
* I can find very few references to this holy well in Lelant (near Hayle),
no accurate maps - and that's a shame because
it's an absolutely top-notch name.
Honestly, I'm [not making this one up](https://palden.co.uk/shiningland/files/Shining-Land-AppendixOne-SitesList.pdf). *Fenton* is probably
cognate with Welsh *ffynnon* (and English *fountain* for that matter).


### 0.7.0-alpha 2024-05-03 EAST PENTIRE

* Very many more unit tests
* Bug fixes
* Complete rewrite of spectrum system, using the SpectrumSet object
* Multidot now does painted regions and floodfill
* Joseph's PCT detector outputs image with ROIs
* Dump removed and sink enhanced
* TabData shows sources
* Inputs decoupled from Sources - Sources now use composition, not inheritance
* Comment box for nodes removed (it was never used)
* Direct multifile loading
* Direct PDS4 loading - required refactoring of entire PDS4 layer
* Direct ENVI loading
* Raw file loading from mono images supporting lots of formats
* Loader presets for multifile
* Operator overloading on Datum objects 
* The "datumfunc" system replacing hand-registration of functions
* flip and rotate functions (datumfuncs)
* String datum objects and strings usable in expr
* Docs on library usage
* Changes to nodes so that slow nodes can be disabled and very slow nodes start disabled. This
functionality existed before, but was "ad-hoc"
* Document.changed() is now Document.run() and forces disabled nodes to run
* Most nodes now store data in their outputs rather than a "node.out" which is then written to
an output
* Changes to multidot - doc improvements, UX and bug fixes

Site

* [Google maps](https://maps.app.goo.gl/z26XqeFk2d2qxQBA7)
* [NLS map](https://maps.nls.uk/geo/explore/#zoom=19.0&lat=50.41242&lon=-5.12464&layers=173&b=osm&o=100&marker=50.412152,-5.124204)
* Not much left of this barrow near Newquay due to erosion.

### 0.6.1-alpha 2023-10-04 DYNAS COVE (minor release)

* Multifile input can accept BMP files
* Better multifile documentation
* Filter specifications are no longer hardwired and are loaded from CSVs
* PANCAM and AUPE filters are default filter sets loaded in
* Others can be specified in a config file (and can override PANCAM and AUPE)
* Filter set no longer required by PDS4 input

Site

* [Google maps](https://maps.app.goo.gl/Gi4JDQDmLVubr2Cu7)
* [NLS map](https://maps.nls.uk/geo/explore/#zoom=17.9&lat=50.00484&lon=-5.10670&layers=173&b=osm&o=100&marker=50.004943,-5.106693)
* [Historic England says it's dubious](https://www.heritagegateway.org.uk/Gateway/Results_Single.aspx?uid=426425&sort=2&type=promontory%20fort&rational=a&class1=None&period=None&county=None&district=None&parish=None&place=&recordsperpage=10&source=text&rtype=&rnumber=&p=5&move=n&nor=240&recfc=0&resourceID=19191#aRt), given everyone's just *assuming*
there's a fort there because of the name (Cornish *dynas* is cognate with Welsh
*dinas* which now means "city" but also means "hillfort.") On the Lizard.


### 0.6.0-alpha 2023-09-11 DRIFT STONES

* uncertainty and error bit propagation in *expr* and all nodes 
* Testing quality and propagation rules (see [Principles](userguide/principles.md))
* Test graphs for nodes and other high-level functionality
* Test nodes for those graphs
* Tabular output on spectrum and histogram nodes
* Gen node for test patterns
* Refactoring of Datum
* Utility nodes - e.g. *roidq* for generating an ROI from DQ bits
* Output enhancements
    * Gradient node can export to PDF
    * Annotations (e.g. text labels) are now drawn on the painter at 
    high res, and have been refactored hugely
    * Annotations use thickness zero by default (the Qt "cosmetic" thickness)
* PCT detector node    
* ROI negation and refactoring of operators
* *roiexpr* node for composing ROIs using expressions
* Crude band depth node (needs work)
* A lot of bug fixes and regression fixes

Site

* [Google maps](https://maps.app.goo.gl/h3XQD2hbApq8NAng6)
* [NLS map](https://maps.nls.uk/geo/explore/#zoom=17.8&lat=50.09982&lon=-5.58473&layers=173&b=osm&o=100&marker=50.099463,-5.585171)
* A pair of nice standing stones near Penzance.


### 0.5.0-alpha 2023-03-08 CARLENNO ROUND

* Data quality and bit viewing on canvas
* Palette and canvas interface with collapsable sections
* Annotations (ROIs, legends) are now drawn onto the canvas rather than the image
* Export to PDF, SVG and PNG with those hi-res annotations
* *gradient* is much simpler, can overlay onto the image and can draw a legend

Site

* [Google maps](https://maps.app.goo.gl/E4dUxtzNa8YACXYd7)
* [NLS map](https://maps.nls.uk/geo/explore/#zoom=17.0&lat=50.22751&lon=-5.35716&layers=173&b=LIDAR_DTM_1m&o=64&marker=50.227777,-5.357533)
* An oval feature, site of a village, near Camborne.

### 0.4.0-alpha 2022-11-30 CAER BRAN

* Annotation system entirely rewritten
* PDF/PNG/SVG exporter
* Gradient legend annotation
* Doc updates

Site

* [Google maps](https://maps.app.goo.gl/R9WMNFJgoAnMmjg28)
* [NLS map](https://maps.nls.uk/geo/explore/#zoom=15.0&lat=50.10463&lon=-5.62712&layers=6&b=ESRIWorld&o=100&marker=50.104626,-5.627117)
* A small but perfectly formed circular hillfort west of Penzance.

### 0.3.0-alpha 2022-10-27 BEACON HUT

* Open source!
* PDS4 importer with proctools
* Ad-hoc Spectrum viewer in canvas
* Significant rewrite of expression execution code, permitting custom
types to have operations defined on them
* Direct input method for library use
* Improved default RGB mapping in canvas
* Testing
    * Basics testing
    * Testing of the operating principles (see [Principles](userguide/principles.md))
        * Source rules
        * ROI rules
* rect node can now be edited numerically
* circle node can add circular ROIs, which can be edited numerically.

Site

* [Google maps](https://maps.app.goo.gl/ZJc6vgXuQ66AAg8W6)
* [NLS map](https://maps.nls.uk/geo/explore/#zoom=17.8&lat=50.13336&lon=-5.22988&layers=6&b=ESRIWorld&o=100&marker=50.133545,-5.230464)
* A chambered cairn, or it could possibly be a hut, between Helston and
Falmouth.

### 0.2.0-alpha 2022-04-21 ANJARDEN SPRING


* "pixel scanning" on canvases, shows spectrum of pixel when active
* custom cursor, pixel under cursor highlighted at high zooms
* text toggle button (currently unused)
* fixes to example plugin
* added macos.spec for pyinstaller
* archive system shows progress when loading each archive element
* Issue 1 fix (multiple tab closes when main window reinitialised)
* dynamic type determination for expr output
* can connect incompatible node outputs to inputs; indicated as red arrows
* infinite recursion in ROI nodes fix
* splash screen for Windows/Linux pyinstaller startup (not yet supported
on MacOS pyinstaller)
* custom Datum and connection brush types now easy
* expr resizing regression fix
* multiple input buttons after load/resize fix
* status bar repaints on ui.msg, so it's updated in load and perform
* context menu on editable text caused a crash (bug in Qt). Workaround.
* comment boxes

Site

* [Google maps](https://maps.app.goo.gl/cWShaVzuMTzHM2nz6)
* [NLS map](https://maps.nls.uk/geo/explore/#zoom=19.0&lat=50.10180&lon=-5.61240&layers=173&b=ESRIWorld&o=100&marker=50.101840,-5.612444)
* A rather boggy sacred spring near Penzance.

### 0.1.0-alpha 2022-03-02 ALSIA WELL

* Initial alpha release outside Aberystwyth

Site

* [Google maps](https://maps.app.goo.gl/NarVjkFAhuqsHUL68)
* [NLS map](https://maps.nls.uk/geo/explore/#zoom=17.3&lat=50.06951&lon=-5.64255&layers=173&b=ESRIWorld&o=100&marker=50.069042,-5.644670)
* A holy well near Land's End, recently refurbed.
