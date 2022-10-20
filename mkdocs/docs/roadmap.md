# Development roadmap

This is a rough guide, and things may change!

## Next release: BEACON HUT

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

## Future releases

* Data quality
    * uncertainty map
    * pixel data bits (how many?)
    * canvas viewer for both the above
    * use flashing pixels??
    * error propagation in *expr* and all nodes (see [Principles](/userguide/principles))
    * Testing quality rules
    
* Documentation
    * User guide
        * Page each on the main elements of the UI
        * Page on *expr* nodes
        * documentation for properties of nodes for library use (e.g. *expr* nodes have ".expr")
        * How-to for common tasks
        
* Output enhancements
    * Gradient node 
        * should also be able to output image to a matplotlib PDF with a legend
        * How would this work where the gradient is inset?
    * showing text labels on low res images?
        * canvas should display ROIs etc, and not draw onto the RGB of the image as it currently does.
        It should work how the source descriptor works.
        This would avoid the resolution problem. We could do away with "ann" outputs?
        * This could imply a whole new way of adding stuff to images.

* Obtain user stories for analysis of HK data (which could potentially
get messy, as these are likely to be time series)

* Consider a vector type
    * It might be useful if functions
    such as max(), sd() etc. produced a vector of a values
    rather than a single value in multiband image contexts. For example,
    a 4-band image with the first channel set to 1 while all others are zero
    could produce a mean vector of [1,0,0,0]. We would then perform a max()
    on this vector to get a single value.
    

* Preparing for filter aberration and de-hardwiring cameras:
    * Actual values removed from filters.py and put into a config file
    * PANCAM/AUPE camera types no longer hardwired but got from that config
    * Filter aberration parameters added to this config

* Filter aberration
    * Node (or func??) to convert aberration to image
    * Calculate and process in canvas spectrum
    * Calculate and process in *spectrum* node
