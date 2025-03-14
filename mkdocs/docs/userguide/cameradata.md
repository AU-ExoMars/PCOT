# Camera data

Each camera used with PCOT has different filters and other associated data.
PCOT needs to know about these. PCOT uses camera data files to store these.
These are in PCOT's archive format and so have the PARC extension.

## Obtaining camera files

Initial version of the files are stored in the PCOT repository with
PCOT itself, in the `cameras` directory. For example, a file for PANCAM
can be found in `PCOT/cameras/pancam.parc`.

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

# filters organised thus:

filters:
  C01L:                     # filter name
    cwl: 640                # centre wavelength
    fwhm: 100               # full-width at half-maximum
    position: L03           # position in camera (e.g. L03 for left wheel, number 3)
    transmission: 1.0       # transmission ratio
    description: 
  C01R:
    cwl: 640
    fwhm: 100
    position: R03
    transmission: 1.0
(and so on)
```

## To be determined

* Extra filter fields (aberration, etc)
* Extra data (darkfields, BRDF data etc)

It's likely these latter will be added by putting filenames in the YAML file,
telling `pcot gencam` to load large blocks of data and store them in the PARC.
