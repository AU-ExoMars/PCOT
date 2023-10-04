# Releases

## Production releases
None

## Beta releases
None

## Alpha releases

### 0.6.1-alpha 2023-03-08 DYNAS COVE (minor release)

* Multifile input can accept BMP files
* Better multifile documentation
* Filter specifications are no longer hardwired and are loaded from CSVs
* PANCAM and AUPE filters are default filter sets loaded in
* Others can be specified in a config file (and can override PANCAM and AUPE)
* Filter set no longer required by PDS4 input


### 0.6.0-alpha 2023-03-08 DRIFT STONES

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

