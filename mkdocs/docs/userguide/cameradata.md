# Camera and reflectance target data

Each camera used with PCOT has different filters and other associated data.
PCOT needs to know about these, and stores them in camera data files.
These are in PCOT's archive format and so have the PARC extension.

Similarly, reflectance targets you calibrate against have data, such
as spectra for each patch.

When you start PCOT for the first time 
you will need to tell it where to find these files. PCOT will load all
the camera and reflectance files from the provided directories,
storing them under names given in the files themselves.

## Obtaining camera and reflectance files

You should be able to download camera and reflectance files containing full
data for AUPE and PanCam from the [PCOT Cookbook](https://pcot.aber.ac.uk) site.

Store the camera files in a separate directory from the reflectances.
In my own system, I've created `cameras` and `reflectances` directories
in my PCOT install directory. [wibble](/wobble)

The rest of this page describes how to make your own data files if you
are working with a new camera or target.

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

## Filter response data

As well as the above parameters, filters typically have a CSV file containing filter response data
at each wavelength.
You should add a "response" field to the filter in this case, with the name of the file. For example:

```yaml
  G11:
    cwl: 950
    fwhm: 50
    position: R10
    transmission: 0.994
    description: Medium band infrared
    response: ../wac_filters/Geol 950_50.csv
```
In the CSV file, the lines can be in one of two forms. In simple data, it is just wavelength and response at that
wavelength. For example:
```csv
wavelength,response
200,0.0
250,10.0
```
In more complex data each wavelength has a different response at different angles. Here, the first column is the wavelength
and the remaining columns are the responses at different angles. The angles themselves are extracted from the header.
For example:
```csv
Wavelength (nm),0degs,3degs,6degs,9degs,12degs,15degs,18degs,21degs,24degs,27degs,30degs
761,0.0534,0.0581,0.0756,0.071,0.0838,0.1026,0.1114,0.1513,0.1563,0.1915,0.3277
762,0.0539,0.0543,0.0718,0.0757,0.0995,0.0858,0.1162,0.1539,0.1599,0.1947,0.3684
```
The system will extract any numerical angles from the header, disregarding other text, but the
angles must be in degrees.

There are two other important fields that may be added to the filter definition:

* ```response_percentage``` indicates that the filter responses are percentages. This is true by default,
and setting it to false says that the responses are in the range 0-1.
* ```response_clip_percentage``` tells the system how to deal with filter responses that are greater than 100%. 
Usually this will cause an error. If this is set to a value, the responses will be clipped at this level.
This will cause a warning when the data is loaded and will be visible in the Show Filters dialog.

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
trying to reconstruct the data. See the [multifile docs](multifile.md) for more details on presets for loading binary
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

Reflectance data is also stored in `.parc` files, and these are created by the `pcot genrefl` command in a similar
manner, from a YAML file and some extra data.

### Simple reflectances
Simple reflectance data records the spectrum of each patch at a single angle only. We typically use it
for lab targets such as Spectralon patches or the Macbeth/Babel ColorChecker. The YAML file looks like this:

```yaml
name: Spectralon
date: 2026-01-14
author: Jim Finnis <jcf12@aber.ac.uk>

short: Spectralon patches
description: |
  Data captured from spectralon patches

format: simple

file: spectralon_refl.csv
```
and the referenced CSV file like this:
```
patch,wavelength,mean,sd
S20,250,0.2007,0.0
S20,251,0.2004,0.0
S20,252,0.2001,0.0
S20,253,0.1996,0.0
...
S99,250,0.9725,0.0
S99,251,0.9723,0.0
S99,252,0.9737,0.0
S99,253,0.9742,0.0
S99,254,0.9741,0.0
S99,255,0.9745,0.0
```
with entries for each patch at every wavelength (and the same wavelengths for all patches). 
The reflectances should in the range 0-1.

### Complex reflectance data

This is data in which each patch has a different response at different angles, typically
given as $(\phi,\theta)$ where $\phi$ is the azimuth and $\theta$ is the polar angle.

@@@warn
This format is currently temporary; I refer to it as "Jack's format" because the data
comes from processing Jack Langston's data as little as possible (there's a lot of it!)
@@@

Instead of a single `file` element, the YAML file has a `patches` map. This gives the directory
in which the data for each patch is stored. Here's an example:
```yaml
patches:
    NG4: black
    Pyroceram: white
    BG18: green
    WCT2065: brown
    NG11: grey
    RG610: red
    BG3: blue
    OG515: yellow
```
The keys are the patch names, the values are the directories.

Within each patch directory are subdirectories for each $\phi$ angle. These have names in the form
`Phi_angle` where `angle` is `00` for zero or some other angle in degrees (e.g. `Phi_00`, `Phi_90`, `Phi_210`).

Within each of these $\phi$ directories is a large number of `.sed` files, each named `*_scannumber.sed` (where
`*` can be anything). The scan number maps onto $\theta$:
$$
\theta = 5n-80
$$
Each `.sed` file is directly taken from the RS-3500 instrument; we use the Reflect. (reflectance) percentage field.


## Listing camera data using PCOT

@@@info
Some of this information is duplicated in [the multifile input docs ](multifile.md)
@@@

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

As with all commands you can get a help text with

```commandline
pcot lscams -h
```

For example, to show filters and full details for `AUPE_LEFT` we could
run

```commandline
pcot lscams -fl AUPE_LEFT
```

## Listing reflectance data using PCOT

Similarly, the `lsrefls` command will show the reflectance data the system knows about. The basic command
lists the reflectances, and providing an argument will show only that target. Options are:

* `-l` will show a long-format result with all patch details and the angles stored
* `-p` will plot the reflectances (at $\phi=0$ and $\theta=0$)
* `-F` will take a filename rather than a reflectance target name




## Further work

Later, more information will be added to the camera data files:

* Extra data (darkfields, BRDF data etc)
* Extra filter fields (aberration, etc)

