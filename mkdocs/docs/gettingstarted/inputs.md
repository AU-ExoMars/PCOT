# Loading different image formats

The examples in [the tutorial](../tutorial) use ENVI images, but
other image formats are available:

* plain RGB
* "multiband" images (multiple monochrome PNG images, one per band)
* PDS4 products (work in progress)

## Loading an ENVI image

To reiterate, this is how to load an image from an ENVI file:

* Click an input button to open an input, and select ENVI.
* Click on "Select Directory" and choose a directory with ENVI files.
* Double click on `.hdr` files in the main file view.
This will load the file into the input.

Note
that ENVI is a "two-file" format - the `.dat` files contain the data, while
`.hdr` files of the same name in the same directory contain information
about the data. We only show the `.hdr` file in the file view, but the 
corresponding `.dat`
file must be present too.

ENVI files are a useful multispectral format, and we can provide scripts to
convert raw image sets into ENVI if required. We currently only support
images which are 32-bit floating point in the 
[BSQ (band-sequential)](https://www.nv5geospatialsoftware.com/docs/ENVIImageFiles.html) format.


## Loading an RGB image
To load RGB, open an input
and click the RGB button. A dialog will appear which is very similar to the
[ENVI file dialog above](#inputenvi), 
but showing ENVI header files instead of image files. Double-click on such a
file to load its associated data,
which is assumed to be in the same directory with the same name. RGB images don't
have filters, so there is no wavelength information - instead, the channels are named
R, G and B and these names can be used in *expr* nodes (e.g. ```a$R```).

## Loading a "multiband" image

Sometimes data is provided as a set of monochrome PNG files, although this is
clearly far from ideal. In this case we need to tell PCOT how to work out
which filter is being used for each file. Again, we open the dialog by
clicking on an input button and clicking the appropriate method - "Multifile"
in this case. This will open the ENVI dialog, which is rather more complex
than the RGB or ENVI dialogs:

![!An open Multiband input|inputmulti](inputmulti.png)

The procedure here is roughly this:

* Make sure the file names contain the the lens (left or right) as L or R,
and the filter position number.
* Work out a regular expression which can find these in the file name.
Hopefully you can just use the default, which assumes that the filename 
contains a string like ```LWAC01``` for left lens, position 01; or
```RWAC10``` for right lens, position 10. If your filenames don't have this
format and it's too difficult to rename them, you'll have to write
an RE yourself or find a handy IT person to help.
* Get the files into a single directory and open the input dialog as shown
above.
* Determine which camera configuration produced the images
(PANCAM or AUPE are supported
but more can be added) 
and set the Camera option accordingly. Different setups use
different filter sets, and will translate filter positions into different
filter wavelengths and names.
* Click the "Get Directory" button.
* In the new dialog, select a directory containing the image files and
and click "Choose."
* A lot of files will appear in the Files box.
* Double-click images to preview them as a single channel.
If they are dark, select an appropriate multiplier and double-click again.
* Click in image checkboxes to select them; selected images will be combined into a single multispectral image.

Close the dialog when you have the selected images you want. It might be a good idea to create an *input* node
to examine the resulting multispectral image.

There is more detail on the regular expression syntax 
[here](/userguide/multifile).

## PDS4 products

This is very much work in progress - please contact the developers if you need
this functionality soon.
