# Global controls

These are at the bottom right of the PCOT main window, and currently 
consist of:

* **Caption**: select how different bands are labelled in the 
dropdown:
    * **Filter names** - bands will be labelled by the name of the filter,
    e.g. "C01L" for the 640nm left-hand red broadband colour filter.
    * **Filter positions** - the filter's position will be used, e.g.
    "L07" will be used for the C01L band, because it is the filter in
    position 7 on the left WAC.
    * **Wavelengths** labels bands according to their centre wavelength,
    so the same band will be labelled "640" under this scheme.
* **Autorun on change** will cause each node to automatically perform
its action when it is changed (either an input has changed or one of the
controls in its tab). This will also cause all nodes "downstream" of it
in the graph to change. It is sometimes useful to turn this off when
changing a node will trigger a very slow action.
If you have done this, you can run a single node by clicking on it
with the Ctrl key held down.
* **Run all** will cause all root nodes (nodes without inputs) in the graph
to run, thus causing all their downstream nodes to run. Effectively, it
runs all the nodes in the graph in the correct order.


