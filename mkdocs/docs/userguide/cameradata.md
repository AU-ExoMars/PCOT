# Camera data

Each camera used with PCOT has different filters and other associated data.
PCOT needs to know about these. PCOT uses camera data files to store these.
These are in PCOT's archive format and so have the PARC extension.

## Obtaining camera files

Initial version of the files are stored in the PCOT repository with
PCOT itself, in the `cameras` directory. For example, a file for PANCAM
can be found in `PCOT/cameras/pancam.parc`. Currently these files hold
no calibration data, just the filter information.

@@@primary
Later you will be able to download camera files containing full
data for AUPE and PanCam
from the [pcot.aber.ac.uk](pcot.aber.ac.uk) site.
@@@

When you start PCOT for the first time 
you will need to tell it where to find these files. PCOT will load all
the camera files from the provided directory, storing them under
the names given in the camera parameter file (see below).



## Creating camera files

Camera data is generated from a YAML parameter file (and possibly extra data)
and stored in a PARC file.

To create a camera data file, run the `pcot gencam` command:

```
pcot gencam cameraname.yaml cameraname.parc
```

## Format of the YAML file

The camera parameter file should have the following form at minimum:

```yaml
name: AUPE                  # short name of the camera
date: 2025-03-04            # date of the camera data in YYYY-MM-DD format (ISO 8601)
author: Jim Finnis <jcf12@aber.ac.uk>       # author of the camera data


# longer description of the camera

description: |
    The Aberystwyth University PANCAM Emulator
    This dataset represents AUPE as it was on 4th March 2025.

# Filters organised thus:

filters:
  C01L:                     # filter name
    cwl: 640                # centre wavelength
    fwhm: 100               # full-width at half-maximum
    position: L03           # position in camera (e.g. L03 for left wheel, number 3)
    transmission: 1.0       # transmission ratio
    description: "Red broadband"    # short phrase describing the filter
  C02L:
    cwl: 540
    fwhm: 80
    position: L02
    transmission: 1.0
    description: "Green broadband"
(and so on)
```

## Flatfield data

The `gencam` command will build flatfield data from a large number of images captured for
each filter. These images should be stored in a directory for each filter, named for the filter
name. For example:

```text
filters
|-- C01L
|   |-- 001.png
|   |-- 002.png
|   |-- 003.png
|   |-- 004.png
|   `-- 005.png
`-- C02L
    |-- 001.png
    |-- 002.png
    |-- 003.png
    |-- 004.png
    `-- 005.png
```
The name of the directory should be the name or position of the filter according to the filters
section of the file. Which is used depends on the `key` field (see below).
The number and names of the files within the directories is unimportant, but they must be
monochrome images of the same format and size.

To prepare this data

The YAML file should contain a `flats` section like this:

```yaml
flats:
    enabled: yes        # can be switched to "no" if you need to save space and not store flats
    directory: foo/filters  # the path to the directory, e.g. "filters" in example above
    extension: png      # extension of image files (png or bin)
    bitdepth: 10        # how many bits are used in the data
    key: name           # "name" or "position" - the filter directories can be named for either
    preset: AUPE        # a multifile loader preset for binary (bin) files (see below)
        
```
See the [multifile docs](/userguide/multifile.md) for more details on presets for loading binary
files. You do not need to specify a preset if PNGs are used.

The files are processed as follows:

* All files are loaded in and processed into floating point data in the range $[0,1]$.
* The files are scanned for saturated data (data equal to 1) and these pixels are masked out.
* The mean is found of each pixel, disregarding saturated pixels, and the results stored in
a single image.
* The uncertainty is calculated as the std. dev. of the pixels used.
* If all bits for a pixel were saturated, the DQ SAT bit for that pixel is set and its
value is set to zero.

@@@warn
The result is not divided by the mean or processed further in any way - later this may
be done when darkfields are implemented, but this can be done downstream for the moment.
@@@

## Further work

Later, more information will be added to the camera data files:

* Extra data (darkfields, BRDF data etc)
* Extra filter fields (aberration, etc)

