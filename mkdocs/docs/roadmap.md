# Development roadmap

This is a rough guide, and things may change!

## Next release: BEACON HUT

* Open source!
* PDS4 importer with proctools (**done** for ExoMars)
* Data quality
    * uncertainty map
    * pixel data bits
    * canvas viewer for both the above
    * error propagation in *expr* and all nodes (see [Principles](/userguide/principles))
    
* Testing
    * Testing of the operating principles (see [Principles](/userguide/principles))
        * Source rules (**in progress**)
        * ROI rules
        * Image quality rules

* Documentation
    * User guide
        * Page each on the main elements of the UI
        * Page on *expr* nodes
        * documentation for properties of nodes for library use (e.g. *expr* nodes have ".expr")
        * How-to for common tasks
        
* Obtain user stories for analysis of HK data (which could potentially
get messy, as these are likely to be time series)


## Future releases

* Preparing for filter aberration and de-hardwiring cameras:
    * Actual values removed from filters.py and put into a config file
    * PANCAM/AUPE camera types no longer hardwired but got from that config
    * Filter aberration parameters added to this config
* Filter aberration
    * Node (or func??) to convert aberration to image
    * Calculate and process in canvas spectrum
    * Calculate and process in *spectrum* node
    