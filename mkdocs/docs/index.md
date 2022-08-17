# PCOT - the PanCam Operations Toolkit

PCOT is a Python program and library which allows users to manipulate 
multispectral images and other data from the ExoMars *Rosalind Franklin* rover.

@@@ warning
This is an early alpha version with serious limitations.

* There is no calibration code of any kind (although the preliminaries are in place)
* PDS4 import capabilities are poor - we only support spec-rad products
from the ExoMars PANCAM instrument - but we also support
    * ENVI provided the images are 32-bit float BSQ
    * RGB PNGs
    * multispectral images made of multiple monochrome PNGs
    * and adding new PDS4 formats should be relatively straightforward
* Data quality and uncertainty data are not yet handled in any way
* There are probably a *lot* of useful operations missing
* There are certainly a *lot* of bugs.
@@@

<div class="text-center">
<a href="gettingstarted/" class="btn btn-primary" role="button">Getting Started</a>
<a href="userguide/" class="btn btn-primary" role="button">User Guide</a>
<a href="roadmap" class="btn btn-primary" role="button">Dev Roadmap</a>
</div>


## Reporting bugs

There are a known issues things which can stop PCOT running - see
[issues](gettingstarted/issues.md). If your problem isn't described there, you should have
been given the address and a user ID to access our bug tracking system. If you
haven't, please contact the Aberystwyth team.

## Release history
[Can be found here](releases.md)

