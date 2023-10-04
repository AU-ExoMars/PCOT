# Development roadmap

This is a rough guide, and things may change!

## Next major release: 0.7.0 EAST PENTIRE

* Reorganise the node palette
* Obtain user stories and feedback
* Documentation
    * User guide
        * Page each on the main elements of the UI
        * Page on *expr* nodes
        * documentation for properties of nodes for library use (e.g. *expr* nodes have ".expr")
        * How-to for common tasks
        
## Future releases

* Calibration: the PCT detection node is fine, but does nothing!

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
