# Operating principles

PCOT nodes need to follow a set of rules to ensure that the information
they process is handled consistently. This page describes these rules,
most of which apply to image data.

## Source handling rules
Each datum handled by PCOT has a "source set" describing where that
datum ultimately comes from. Sources vary: in images, each band in an input image carries
a source datum describing where it comes from. For a PDS4 source it could be a LIDVID, or it
could simply be a filename (although ideally it should have some archive indexing data).

Because data can be combined in various ways, each datum could have multiple
sources. Image data in PCOT have a separate source set for each band. 

The rules for sources are simple:

* Every datum has a source set.
* This may be a null source if the datum is generated internally (consider the output from *constant* nodes).
* In the case of an image, this source set is actually a separate source set for each band, but may still be considered as a single
source set for some operations (since the union of the band sets is available).
* If a datum, or band in a multi-band image, is constructed from data from more than once source set, the resulting datum or band
consists of the union of the sets.


As an example, consider the rather contrived example below.

![!An example graph with each datum marked as a black circle. Image inputs are in yellow,
scalar inputs are in blue.](SourcesExample.svg)

We have three inputs into the graph:

* Input 0 has an image with three bands centered on 640nm, 540nm and 440nm.
* Input 1 has a different image with four bands.
* Input 2 has a numeric value of 0.2 (perhaps a housekeeping datum of some kind).

These data are then combined in various ways:

* Input 1 is converted to a single greyscale band and multiplied by input 2 (the scalar 0.2)
* The result of this operation is then added to the 540nm band of input 0.

What do the sources look like for each datum?

* Datum A is an image, and as such it has one source set per band. 
Each source set consists of a single "image source" giving details of input and
filter wavelength. So here, the sources for A could be written as

        [ {0:640}, {0:540}, {0:440} ]

    That is, a list of three sets, each of which contains a single source which I've written
    in the form ```input:wavelength```.

* Datum B is the extracted 540nm band of input A, so its sources are:

        [ {0:540} ]

* Datum C is another multiband image, this time from input 1:

        [ {1:780}, {1:640}, {1:540}, {1:440} ]

* Datum D is the greyscale conversion of Datum C above. This creates a single-band image,
but that band combines all the bands of datum C. This results in a single source set containing
all the bands:

        [ {1:780, 1:640, 1:540, 1:440} ]
        
* Datum E is the only non-image source. I will denote it here as just "2" indicating that it
is input 2. It is worth noting here that sources may contain a lot of extra data describing
exactly where they come from. For example, this input may come from PDS4, in which case at least
the LIDVID will be included. But for now this is simply

        {2}
        
    Note that this is not shown as a list because it is not a multiband source.


* Datum F multiplies each band in datum D by the scalar E. This means that the source for E must
be added to the source set for each band. There is only one band at this point because of the 
greyscale conversion:

        [ {1:780, 1:640, 1:540, 1:440, 2} ]
        
* Finally, we add the single-band images B and F together, resulting in another single-band image.
This addition is done bandwise. There is only one band, so the result is:

        [ {1:780, 1:640, 1:540, 1:440, 2, 0:540} ]

## ROI rules

@@@
TODO - describe how ROIs are processed. When they are accounted for,
when they aren't.
@@@


## Uncertainty and error

@@@
TODO - describe how these are processed. Could probably use a separate
page describing the data?
@@@
