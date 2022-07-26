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
TODO - ROI rules in progress
@@@

Images may contain regions of interest. If this is the case, then 
any operation should only be performed on the region of interest if possible.
However, the rest of the image should be passed through unchanged to
provide context - it is always possible to use a *croproi* node before
the operation if cropping is required.

This rule has the following practical outcomes, in which 

* images are denoted by capitals $A, B, \dots$
* scalars are denoted by lowercase $x, y, \dots$
* the ROIs of image $A$ are the set $R_A$

So:

* In binary operations on an image and a scalar such as $x+A$ or $A+x$, the operation is only performed on the region covered by the union of all ROIs on $A$. 

    Other parts of $A$ are left unchanged in the output, which carries the same ROIs.

* In binary operations on two images $A+B$ etc., the operation is only performed on the region covered by the intersection of the unions of the ROIs. That is
    \\[
        \bigcup R_A \cap \bigcup R_B
    \\]
    Parts of the image which are outside the ROIs are set to the left-hand input image for binary operations.

* In general, a function of a set of images $S$ always attempts to perform the
action on $\bigcap \left(\bigcup_i R_{S_i}\right)$, i.e. the intersection of the unions of
the ROIs of each image. Parts of the image which are not processed are set to
image $S_1$, the first image in the set.

* If the output is an image of a different depth, the unprocessed parts of the output are set to zero.



## Image uncertainty data

@@@
TODO - describe how these are processed. Could probably use a separate
page describing the data?
@@@

Each pixel each band of an imagecube contains an uncertainty value,
which is a root mean squared error. Operations need to 
combine this data in a sensible way. For example,
denoting the RMS error in $a$ as $\Delta a$, binary operations work like this:

\begin{align}
\Delta (a+b), \quad \Delta (a+b) &= \sqrt{(\Delta a)^2 + (\Delta b)^2}\\
\Delta (ab),\quad \Delta (a/b) &= \sqrt{\left(\frac{\Delta a}{a}\right)^2 + \left(\frac{\Delta b}{b}\right)^2}\\
\Delta (a \& b) &= \min (\Delta{a}, \Delta{b})\\
\Delta (a | b) &= \max (\Delta{a}, \Delta{b})
\end{align}

For functions which don't work nicely in this system, **we set the uncertainty
to zero but set the "no uncertainty" error bit** (see below).

@@@ warning
Remember that this only applies if the bands are independent. In reality there
is always a covariance between them.
@@@

## Pixel information bits

@@@
A lot of this is TODO
@@@ 

Each pixel in each band has an associated set of bits which indicate error states, etc. In general, when multiple image bands
are combined (either from the same image or from different images) these are OR-ed together. Bits are:

| Bit name | Meaning | Effect on calculations|
|-----------|------|----|
|ERROR|Pixel is an error in this band|should not be used in any calculation (see below).|
|SAT|Pixel is saturated in this band|**???**|
|NOUNC|No uncertainty data (error propagation was not possible)|**???**|

When a pixel is not used in a particular band, the value is set to zero for that band and the ERROR bit is passed through. 

It should be possible to set bits based on per-pixel conditions with the *bits* node. For example, convert all uncertainties
greater than a given value into errors.

### Error ROIs
It should
be possible to construct an ROI of error or non-error pixels in an image (i.e. pixels which have an error on any band).



## Filter aberration

@@@
A lot of this is TODO
@@@ 

The filter wavelengths are only accurate for pixels in the centre of the image, due to the difference in the light path through the filter
at different angles of incidence. Therefore:

* There will be a system in place to calculate the actual filter wavelength for a given pixel and use this in spectral plots (using the centre
of the ROI for the *spectrum* node)
* A function should be available to generate the filter aberration value in *expr* - this would allow an "image" to be made of
the aberration value which could be used in calculations
* It should be possible to set the ERROR bit for excessive aberration values


