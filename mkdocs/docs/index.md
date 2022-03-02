# PCOT - the PanCam Operations Toolkit

PCOT is a Python program and library which allows users to manipulate 
multispectral images and other data from the ExoMars *Rosalind Franklin* rover.

@@@ warning
This is an early alpha version with serious limitations.

* There is no calibration code of any kind (although the preliminaries are in place)
* PDS4 import capabilities are poor (we support ENVI provided the images
are 32-bit float BSQ, 3-channel PNGs and multispectral images made of multiple
monochrome PNGs)
* Data quality and uncertainty data are not yet handled in any way
* There are probably a *lot* of useful operations missing
* There are certainly a *lot* of bugs.
@@@

## Release history
[Can be found here](releases.md)

## Installing and running PCOT
PCOT is available in two forms:

* **Standalone executables** for Windows and Linux (and hopefully MacOS soon) - these are 
suitable for people who do not need to add their own plugins or use PCOT as a Python library.
They can be obtained from the Aberystwyth team. To run, simply run the downloaded ```pcot``` executable.

* **A Python program typically installed with Anaconda and Poetry** which can be obtained by
downloading the source and running the [installation procedure](github.md) - but this can only be done
if you have access to the source code repository. To run, you will need to activate
the conda environment with ```conda activate pcot``` and then run the ```pcot``` command. 
        
There are a few things which can stop PCOT working - see
[here for a list](github.md#common-runtime-issues).

## Reporting bugs

You should have been given the address and a user ID to access our
bug tracking system. If you haven't, please contact the Aberystwyth team.


## More information

These pages are useful when you are getting started:

* [PCOT concepts](concepts.md) describes the basic ideas behind PCOT
* [Getting Started](gettingstarted.md) introduces the program and gives a basic tutorial
* There is a [video guide](https://www.youtube.com/watch?v=vo5KrOAtMQ8) - please ignore the opening comments
on installation and Anaconda; these only apply to installing from source

Other information

* [Automatically generated documentation](autodocs/index.md) for nodes and
*expr* functions/properties
* [The README.md file from the repository](github.md) which contains
(among other things) details on how to install from source.

