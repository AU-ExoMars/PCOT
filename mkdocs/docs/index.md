# PCOT - the Pancam Operations Toolkit

PCOT is a Python program and library which allows users to manipulate 
multispectral images and other data from the ExoMars *Rosalind Franklin* rover.

## Installation
PCOT is available in two forms:

* **Standalone executables** for Windows and Linux (and hopefully MacOS soon) - these are 
suitable for people who do not need to add their own plugins or use PCOT as a Python library.
They can be obtained from the Aberystwyth team.
* **A Python program typically installed with Anaconda and Poetry** which can be obtained by
downloading the source and running the installation procedure - but this can only be done
if you have [access to the source code repository](github.md).

## Running the application

* If you are using the standalone version, simply run the executable you downloaded.
* If you installed the source code into an Anaconda environment you should start a command line shell
(an Anaconda Powershell on Windows) and run the following commands:

        conda activate pcot
        pcot
        
There are a few things which can stop PCOT working - see
[here for a list](github.md#common-runtime-issues)


## More information

* [PCOT concepts](concepts.md) describes the basic ideas behind PCOT
* [Getting Started](gettingstarted.md) introduces the program and gives a basic tutorial
* [Automatically generated documentation](autodocs/index.md) for XForms (nodes) and *expr* functions/properties


