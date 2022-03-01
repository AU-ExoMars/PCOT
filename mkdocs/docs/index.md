# PCOT - the PanCam Operations Toolkit

PCOT is a Python program and library which allows users to manipulate 
multispectral images and other data from the ExoMars *Rosalind Franklin* rover.

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


## More information

These pages are useful when you are getting started:

* [PCOT concepts](concepts.md) describes the basic ideas behind PCOT
* [Getting Started](gettingstarted.md) introduces the program and gives a basic tutorial

Other information

* [Automatically generated documentation](autodocs/index.md) for nodes and
*expr* functions/properties
* [The README.md file from the repository](github.md) which contains
(among other things) details on how to install from source.

