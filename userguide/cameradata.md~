# Camera data

Each camera used with PCOT has different filters and other associated data.
PCOT needs to know about these, and stores them in camera data files.
These are in PCOT's archive format and so have the PARC extension.

When you start PCOT for the first time 
you will need to tell it where to find these files. PCOT will load all
the camera files from the provided directory, storing them under
names given in the files themselves.

## Obtaining camera files

Initial version of the files are stored in the PCOT repository with
PCOT itself, in the `cameras` directory. For example, a file for PANCAM
can be found in `PCOT/cameras/pancam.parc`. Currently these files hold
very little calibration data, just the filter information.

You should be able to download camera files containing full
data for AUPE and PanCam
from the [PCOT Cookbook](pcot.aber.ac.uk) site. Data will be added
to this server when it becomes available.


The rest of this page describes how to make your own data files if you
are working with a new camera.

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
# short description of the camera, much less than 80 chars
short: The left WAC on the Aberystwyth University PanCam Emulator

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

For flats to be included the YAML file should contain a `flats` section like this:

```yaml
flats:
    # enabled: yes      # uncomment this line to avoid saving flatfield data (to save space)
    directory: foo/filters  # the path to the directory, e.g. "filters" in example above
    extension: png      # extension of image files (png or bin)
    bitdepth: 10        # how many bits are used in the data - this is 16bit data but only 
                        # the lower 10 bits are used - data will be multiplied up
    key: name           # "name" or "position" - the filter directories can be named for either        
```
If you are creating the data from raw files - and this is typically the case - you will need to
specify how those files should be loaded. This can be done with the `rawloader` subsection, which consists of a
full specification for the raw loader (recommended) or a preset. You do not need to specify a preset if PNGs are used.
To specify the raw loader fully use the following format:
```yaml
flats:
    directory: flats
    key: position         # the subdirectories are named for the filter position
    extension: bin        # loading raw files
    bitdepth: 10
    rawloader: # u16, 1024x1024, 48-bit offset, bigendian, rotate 90 CCW
        # preset: pancamraw   
        format: u16     # 16-bit unsigned integer data; others are f32, u8
        width: 1024
        height: 1024
        bigendian: true
        offset: 48      # offset in bytes to the start of the data
        rot: 90         # rotate the data 90 degrees counter-clockwise
        horzflip: false # horizontal flip? No.
        vertflip: false # vertical flip? No.
```
To use a preset instead, you can use the following format:
```yaml
flats:
    # ... other fields as above
    rawloader: 
      preset: pancam-rawloader  # use this multifile preset for loading PANCAM files
```
where the preset has been created in the multifile input. However, It's best to specify the data fully rather than risk another user not having the preset when
trying to reconstruct the data. See the [multifile docs](/userguide/multifile.md) for more details on presets for loading binary
files. 

### Remapping filter names in flatfield data

Sometimes the directory names are not the same as the filter names or positions. In
this case you can use a `directory_map` dictionary inside the `flats` section, like this:

```yaml
flats:
    # ... other fields as above
    
    directory_map:
        # Each key below is a filter position, the value is the directory in which to find that filter.
        "01": "01"
        "02": "02"
        "03": "some_other_dir"  # e.g. if filter 03 is in a different directory
        "04": "yet_another_dir"  # e.g. if filter 04 is in a different directory
        # ... and so on.
```
Note that every filter position must be listed in the `directory_map` dictionary, even if the value is the same as the key.

## Reflectance data

@@@warn
This section is likely to change in the future as reflectance data becomes more complex!
@@@

You can store the reflectance data for each filter in the camera data file for a given calibration target.
To do this, you need to add a `reflectance` section to the YAML file, like this:

```yaml
reflectance:

  # PCT Colourimetry data from this directory:
  # ABU-Exomars - Colourimetry\2023-11-21_colour_targets\pct\*-full-br\*BS* images

  PCT: lwac_from_colourimetry_pct.csv
  
  # reflectance data from the Babelcolour ColourChecker dataset
  # https://babelcolor.com/colorchecker-2.htm#CCP2_data
  
  macbeth: lwac_from_babelcolour_colorchecker.csv
```
The CSV files contain the reflectance per filter for each patch in the target, with the
following columns:

* `ROI`: (region of interest) the name of the patch in the target
* `filter`: the name of the filter
* `n`: the mean of the reflectance for that patch in that filter
* `u`: the uncertainty in the reflectance for that patch in that filter

Here are the first few lines of the `lwac_from_colourimetry_pct.csv` file:

```csv
ROI,filter,n,u
NG4,C03L,0.07009,0.0052
NG4,C02L,0.07165,0.00442
NG4,C01L,0.07126,0.00565
NG4,G0a,0.07174,0.0043
NG4,G0b,0.06581,0.00508
NG4,G0c,0.07276,0.00456
...
```

## Listing camera data using PCOT
You can find out which cameras are available and what data they have using the `lscams` subcommand:
```commandline
pcot lscams
```
The basic command will just list the cameras, the filename they are stored in, and their short description.
Given a camera name, it will only give data for that camera.
There are more options:

* `-f` will list the filters 
* `-l` (long) will list the full description of the camera and whether it has flats and reflectance data
* `-F` (file) will take a camera data filename rather than a camera name

## Further work

Later, more information will be added to the camera data files:

* Extra data (darkfields, BRDF data etc)
* Extra filter fields (aberration, etc)

