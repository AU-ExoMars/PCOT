# Development roadmap

This is a rough guide, and things may change!

## Next major release: 0.9.0
        
## Future releases

* Batch and parameter files, major changes to node serialisation internals required by this
* Reorganise the node palette
* Obtain user stories and feedback
* Documentation
    * User guide
        * Page on *expr* nodes
        * documentation for properties of nodes for library use (e.g. *expr* nodes have ".expr") (Note: now should be automatically produced by parameter file definitions to some extents)
        * How-to for common tasks (the "cookbook")

* Calibration: the PCT detection node is fine, but does nothing!

* Filter aberration
    * Filter aberration parameters need to be obtained and added to config
    * Node (or func??) to convert aberration to image
    * Calculate and process in canvas spectrum
    * Calculate and process in *spectrum* node

* Obtain user stories for analysis of HK data (which could potentially
get messy, as these are likely to be time series)

