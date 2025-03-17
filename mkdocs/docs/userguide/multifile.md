# The Multifile input method

@@@ primary
Documentation for the other methods is forthcoming.
The regex aspect of multifile is complicated, so documenting it was 
a priority.
@@@

The multifile input method allows multiple monochrome files of "standard"
types like PNG and BMP to be imported as multispectral images. It can
also read raw binary files.

Each file is flattened to greyscale in the process (if it is RGB) by finding
the mean of the three channels for each pixel.


## Filter CSV files

In order to analyse the images,
PCOT needs to be able to find out which filter was used for each image. This
is done by storing a set of filters in a CSV file and using parts of the image
files' names to work out which filter is used.

Two files are available by default. These are PANCAM (for the actual
ExoMars camera) and AUPE (Aberystwyth PANCAM Emulator). These can be
found in the `src/pcot/assets/` directory.

Here's an example of part of such a file:
```csv
cwl,fwhm,transmission,position,name
570,12,0.989,L01,G04
530,15,0.957,L02,G03
610,10,0.956,L03,G05
```
In each line:

* **cwl** is the centre wavelength
* **fwhm** is the bandwidth as as full width at half maximum
* **transmission** is how much energy the filter lets through at the CWL
* **position** is the position of the filter in the filter wheel, typically as a camera letter
(e.g. R or L) and an index number
* **name** is the name of the filter.

If you need to add a new filter set, edit the `.pcot.ini` file in your 
home directory and a `[filters]` block if one does not exist. To this block,
add a line like this:
```ini
[filters]
myfilterset=filename
```
For example
```ini

[filters]
JCFCAM=c:/users/jim/jimfilters.csv
```
This new set, called JCFCAM, will be loaded when PCOT is started.

## Setting a file pattern

PCOT needs to be able to work out which filter was used to capture an
image. This is done by extracting the filter name or position from the
filename using a regular expression (or *regex*).
If you have some experience with regular expressions (or access to someone
with this experience), it will [help immensely](https://xkcd.com/208/).

Regular expressions describe patterns which texts might match. For example,
the regex `c[a-z]t` will match any three-letter string starting with `c` and
ending with `t`: it's `c`, followed by any character between `a` and `z`, 
followed by `t`.

* [Beginner's guide](https://www.regular-expressions.info/index.html)
* [Useful 'playground' to try out expressions](https://regex101.com/)

The default pattern looks something like this:
```txt
.*(?P<lens>L|R)WAC(?P<n>[0-9][0-9]).*
```

This means:

* `.*` matches any number of any character, so there could be anything
at the start of the filename
* `L|R` means "either `L` or `R`" - but we have specified a "named match"
with brackets and the `?P<..>` notation: `(?P<lens>L|R)`. This means 
"either `L` or `R` and store the result under the name `lens`".
* `WAC` means we must then have the sequence of letters `WAC`
* `(?P<n>[0-9][0-9])` means we must now match two digits (`[0-9]`) and
store them as `n`
* The final `.*` means that there can now be any number of any character again -
so there could be anything at the end of the filename.

The idea is that a filename like `/home/jim/files/DogBiscuitLWAC02Fish.jpg`
will be matched, and will result in `L` being stored as `lens` and 
`02` being stored as `n`.

### Named matches and how they are used

Only one of the following should be true (e.g. you can't use
`name` and `n` together):

* `lens` and `n`: if these are found, they are joined together
to form a filter position which is looked up in the filter set (by
the `position` column).
The idea is that `lens` indicates either the left or right camera
and `n` identifies a filter. They're separate because many early
files used names like `LWAC02` or `LWideAngle02`, in which the
two elements were separate.
* `pos`: if this is found, it us used to match a filter position using the
`pos` column - as such, it's a simpler version of the `lens`/`n` combination
* `name`: if this is found, it is used to match a filter using the `name`
column
* `cwl`: if this is found, it is used to match a filter using the `cwl`
(wavelength) column


If you need assistance, or this isn't flexible enough, contact us.


## Reading raw binary files

Data is often provided "as is" from the camera, in a raw binary format.
Reading these files requires a little more information in advance:

* What the numeric format of the data is (e.g. 16-bit unsigned integer)
* How big the image is in pixels
* Whether there is a header at the start which should be skipped and
how big it is (the "offset")
* Whether the image needs to be rotated and/or flipped
* Whether the data is "big-endian" or "little-endian."

These can be set by clicking the "raw loader settings" dialog. 

@@@ primary
For images from AUPE, the settings are:

* 16-bit unsigned integer
* 1024x1024
* 48 byte offset
* Rotate 90 degrees
* Big-endian data
@@@

## Presets
You can save
and load these values - and most other settings for multifile input, such
as the pattern and filter - using the "Presets" button. Presets are currently stored
in your home user directory in a file called `MFPresets.json`. Users can
easily copy this file from other users.

