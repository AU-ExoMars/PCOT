# Concepts

**How PCOT works (and why)**

PCOT was originally designed to help scientists and engineers analyse PanCam
data and produce useful secondary data. It acts downstream from the
Rover Operations Control Centre (ROCC) on
images which have already been processed to some extent, and is a successor to
ExoSpec [^1]. As such, its primary purpose is to generate relative reflectance
images and spectral parameter maps, although it will also be able to produce
spectra from regions of interest. Indeed, it should be flexible enough
to perform a wide range of unforeseen calculations.

PCOT can also handle many other kinds of data. It is particularly suited
to processing multispectral images with uncertainty and error data, and can
currently read PDS4 and ENVI formats, alongside more common RGB formats
which can be collated into multispectral images.

Of paramount importance is the verifiability and reproducibility of data
generated from PCOT. To this end, a PCOT document is a data product which can
be shared between users, which also fully describes how the data was generated
from the initial import to the final output. Users are encouraged to exchange
PCOT documents in addition to, or instead of, the generated images or data.

## The Graph

To achieve this, a PCOT document manipulates data in a graph - a network of
nodes, each of which takes some data, works on it, perhaps displays some
data, and perhaps outputs derived data. 
Technically speaking, this is a "directed acyclic graph": each connection
has a direction, going from the output of one node to the input
of another, and there can't be any loops.

As an example, consider that we might want
to overlay some kind of spectral parameter map, converted to a colour
gradient, over an RGB image (note: I'm not a geologist, I'm a software
engineer, so perhaps this is a very artificial example). One way to do it
might be this:

![!An example graph](671438grad.png)

We can see the graph in the panel on the right, showing each node as a box
with connections to other nodes (ignore the green numbers, they just show
how many times each node has run - it's a debugging aid!)
Here's what each node in the graph is doing:

* The *input 0* node reads input number 0 into the graph. The inputs are set up separately from the graph,
and can be multispectral images or other data (e.g. housekeeping) from outside PCOT.
* The *rect* node lets the user draw a rectangle on the image to define a region of interest. Images
can have many regions of interest and several different kinds are available.
* The node with 4 inputs *a,b,c,d* is an *expr* node, which 
calculates the result of a mathematical expression performed on each pixel. The node is showing the expression it
is running: ```a$671 / a$438```.
This will read the bands whose wavelengths are 671nm and 438nm in the node's *a* input, and find their ratio for every pixel.
The result will be a single-band image. *Expr* nodes can perform much more complex calculations than this.
* The *gradient* node will convert a single-band image into an RGB image with a user-defined gradient and
inset it into the RGB representation of another image - here we are insetting into the input image, using
the RGB representation used by that node.

Here is another example, showing a spectral plot:

* The *input* node again brings a multispectral image into the graph.
* The *multidot* node adds a number of small, circular regions of interest. Each has a different name and colour, in this case set
automatically to just numbers and random colours. Creating the regions is
as easy as clicking on the image.
* The *spectrum* node plots a spectrogram of the regions present in the image for all the wavelengths in that image.

![!Spectrogram example](spec.png)

Here I have "undocked" the *spectrum* node's view to be a separate window for easy viewing. The spectrum can also be saved as a PDF
or converted into CSV data. I'm also showing the entire app, including the menu bar and four input buttons.

## The Document
A PCOT document is a file which can be shared among users. It consists of 

* The **inputs** - data loaded from sources external to PCOT. These are kept
separate from the graph, because you might want to use a different graph on
the same inputs, or the load the same inputs into a different graph. There are
currently up to four inputs, but this can easily be changed. 
* The **graph** - a set of nodes and connections between them which define
operations to be performed on inputs, as shown above.
* The **settings** - these are global to the entire application.
* **Macros** - these are sets of nodes which can be used multiple times and
appear as single nodes in the graph, although each one has its own "private"
graph. Currently very experimental (and largely undocumented).

@@@ primary
**Important**

The data being sent out of the inputs into the graph is saved
and loaded with the document, so the original source data does not need
to be stored - you can send the document to someone and it will still work
even if they don't have the sources.
@@@

Move on to [a First Tutorial](../tutorial)

[^1]: 
Allender, Elyse J., Roger B. Stabbins, Matthew D. Gunn, Claire R. Cousins,
and Andrew J. Coates. 
["The ExoMars spectral tool (ExoSpec): An image analysis tool for ExoMars 2020 PanCam imagery."](https://www.spiedigitallibrary.org/conference-proceedings-of-spie/10789/107890I/The-ExoMars-Spectral-Tool-ExoSpec--an-image-analysis-tool/10.1117/12.2325659.short?SSO=1)
In 
*Image and Signal Processing for Remote Sensing XXIV*, vol. 10789, pp. 163-181. SPIE, 2018.
[link to PDF](https://research-repository.st-andrews.ac.uk/bitstream/handle/10023/16973/Allender_2018_ExoMars_SPIE_107890I.pdf)
