# Development roadmap

## In progress
* Decorr stretch / PCA should have a better UI and should sort with most significant component first.
UI should allow users to select components for view.
* Macro import and export (i.e. macro collections) and users should be able to specify a set of collections
to load
* Similarly we should be able to import/export/store a collection of favourite nodes

## In next release

* Refactoring to get macros working again
* Favourite nodes can be saved - this is a single node with all its parameters
* Decorrelation stretch allows more than 3 bands
* Raw loader crops overlong data (and warns)
* Log window has Clear All Text menu option
* Palette has a search box - enter a string to view only nodes with that string
* Icon on canvas to reset to entire image
* The *reflectance* node now permits the angles to be entered

# Others

* Cull nodes which can be *expr* functions
* Reorganise the node palette
* Obtain user stories and feedback

* Change from Conda+Poetry to UV for virtual environment and dependency
management. This will change the installation procedure.
* Change to PySide6. This will take some time.

* Filter aberration
    * Filter aberration parameters need to be obtained and added to config
    * Node (or func??) to convert aberration to image
    * Calculate and process in canvas spectrum
    * Calculate and process in *spectrum* node

* Obtain user stories for analysis of HK data (which could potentially
get messy, as these are likely to be time series)

