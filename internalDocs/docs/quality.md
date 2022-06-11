# Dealing with image quality

This document is a rough set of notes on how we might deal with the various
image quality measures.

There are several measures which might be called "image quality," each of
which need to be stored **for each band** of an imagecube:

* **Error flag** for each pixel indicating whether the pixel is "bad" or not.
Such pixels should usually be ignored (error flags for an entire image
are referred to as the *error mask* below).
* **Data quality flags** for each pixel. Each of these has
a meaning. These are as yet undefined, and those eventual definitions may be 
quite fluid so this needs to be flexible. Example: pixel saturated high.
* **Uncertainty** for each pixel. This will (?) be in the same number format as the
main pixel data, and is a $\pm$ value.

## Proposal

### Error flag

* The canvas will by default display error pixels as (say) red.
** How do we deal with different bands in the image having different
error pixels? **
    * Option : using a drop-down, select which band we are viewing error pixels
    for. Default is "all bands", that is, the union of error pixels
    across the entire depth of the image.
    * Any better ideas?
* Nodes which perform pixel-wise operations on images propagate the 
error flags through to the images they produce, but still perform the
operation. Thus the addition operator will add both images, but will
set an output error mask with the union of the masks of the input images.
* Nodes which produce a scalar result from an image will
ignore the error pixels (e.g. finding the mean value).
* Nodes which perform an operation such as a Gaussian blur will have to
propagate the error flag to all affected pixels, so a single error pixel
will lead to a "blob" of error pixels in the output.

### DQ flags

* DQ flags can be promoted to error flags by a special node, or this
could be a global setting **???**.
* Similarly, operations on images will be performed but will propagate
the DQ flags through to their results.
* Nodes which produce a scalar will work as normal, NOT ignoring the DQ
pixels.
* DQ flags will be propagated in blur-like operations (surely there's a word
for this?) in similar ways to error flags **???**

### Uncertainty

* Uncertainty can be promoted to error flags (or DQ flag?) by a special
node which looks compares the uncertainty with a threshold.
* Uncertainty is propagated through all operations.

## The error handling node

A special node is mentioned above (or it could be several nodes). This will

* Display DQ, error and uncertainty data in the canvas (and perhaps output that
image as RGB). We'll have to bear in mind when writing this node that this
data will be different **for each band** in the image, so displaying it will
get complicated.
* Output this data as images in their own right (e.g. uncertainty as a greyscale)
* Turn specified DQ bits into error bits in the output
* Turn uncertainty values above a specified threshold into error bits
(or perhaps DQ bits???) in the output.
* Allow data for separate bands to be merged?
