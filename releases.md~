# Releases

## Production releases
None

## Beta releases
None

## Alpha releases

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

### 0.6.1-alpha 2023-10-04 DYNAS COVE (minor release)

* Multifile input can accept BMP files
* Better multifile documentation
* Filter specifications are no longer hardwired and are loaded from CSVs
* PANCAM and AUPE filters are default filter sets loaded in
* Others can be specified in a config file (and can override PANCAM and AUPE)
* Filter set no longer required by PDS4 input


### 0.6.0-alpha 2023-09-11 DRIFT STONES

* uncertainty and error bit propagation in *expr* and all nodes 
* Testing quality and propagation rules (see [Principles](/userguide/principles))
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


### 0.5.0-alpha 2023-03-08 CARLENNO ROUND

* Data quality and bit viewing on canvas
* Palette and canvas interface with collapsable sections
* Annotations (ROIs, legends) are now drawn onto the canvas rather than the image
* Export to PDF, SVG and PNG with those hi-res annotations
* *gradient* is much simpler, can overlay onto the image and can draw a legend

### 0.4.0-alpha 2022-11-30 CAER BRAN

* Annotation system entirely rewritten
* PDF/PNG/SVG exporter
* Gradient legend annotation
* Doc updates

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
    * Testing of the operating principles (see [Principles](/userguide/principles))
        * Source rules
        * ROI rules
* rect node can now be edited numerically
* circle node can add circular ROIs, which can be edited numerically.


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

### 0.1.0-alpha 2022-03-02 ALSIA WELL

* Initial alpha release outside Aberystwyth

