# PCOT - the PanCam Operations Toolkit

PCOT is a Python program and library which allows users to manipulate 
multispectral images and other data from the ExoMars *Rosalind Franklin* rover.

@@@ warning
This is an alpha version with serious limitations.

* There is no calibration code of any kind (although the preliminaries are in place)
* PDS4 import capabilities are poor - we only support spec-rad products
from the ExoMars PANCAM instrument - but we also support
    * ENVI provided the images are 32-bit float BSQ
    * RGB PNGs
    * multispectral images made of multiple monochrome PNGs
    * multispectral images made of monochrome raw files in various formats
    * and adding new PDS4 formats should be relatively straightforward
* There are probably a *lot* of useful operations missing
* There are certainly a *lot* of bugs.
@@@

<div class="pt-5 pb-5 text-center">
<a href="gettingstarted/" class="btn btn-primary" role="button">Getting Started</a>
<a href="userguide/" class="btn btn-primary" role="button">User Guide</a>
<a href="roadmap" class="btn btn-primary" role="button">Dev Roadmap</a>
</div>

<div class="pb-5 text-center">
<a href="autodocs/" class="btn btn-primary" role="button">Automatically generated node and function docs</a>
</div>



## Reporting bugs

There are known issues which can stop PCOT running - see
[issues](gettingstarted/issues.md). If your problem isn't described there
please create a new issue on Github or contact the Aberystwyth team.

## Release history
[Can be found here](releases.md)

