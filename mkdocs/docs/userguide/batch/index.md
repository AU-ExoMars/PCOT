# Batch mode

Batch files - sometimes called parameter files - let you create a PCOT graph
and then run it several times from the command line, modifying its inputs,
outputs or nodes each time.

For example, imagine that we have a graph like this to generate a false colour
spectral parameter map across an entire image:

![A simple graph](gradient.png)

The *expr* node is set to the parameter we want to generate, which
in this case is `a$670/(a$440+0.1)` and we've renamed it back to
*expr* for reasons which will become apparent (*expr* nodes usually change
their name to their expression).

The
*gradient* node is set to the defaults, but with the legend in the left margin
rather than inside the image.

When we run this on some data (assuming it has the two wavelengths we need),
and right-click on the image inside the *gradient* node, we can save as a PDF.
That PDF will look something like this:

![!Example spectral parameter map||style=max-height:400px;](gradient_result.png)

This is great, but we might want to run this on multiple images. We can
do that using batch files. For example, this file will use the same
settings for all the nodes and inputs, but replace the input filenames
with those specified (we're using a [multifile](/userguide/multifile) input
here):

```txt
inputs.0.multifile.directory = H:\PancamData\SamplesGeologyFilter
inputs.0.multifile.filenames.+ = R01.bin
.+ = R02.bin
.+ = R03.bin
.+ = R04.bin
.+ = R05.bin
.+ = R06.bin

outputs.+.node=gradient
.file=gradient.pdf
.annotations=y
.clobber=y
```
The inputs will keep their settings (e.g. raw loader parameters and filter)
but new files will be used.

If we want to do this several times, we can either write multiple batch
files, or we can run the graph several times in one file, changing it
each time. Here's an example that runs the graph twice:

```txt
inputs.0.multifile.directory = H:\PancamData\SamplesGeologyFilter
inputs.0.multifile.filenames.+ = R01.bin
.+ = R02.bin
.+ = R03.bin
.+ = R04.bin
.+ = R05.bin
.+ = R06.bin

outputs.+.node=gradient
.file=gradient1.pdf
.annotations=y
.clobber=y

run

inputs.0.multifile.directory = H:\PancamData\Data2
expr.expr = a$440
gradient.preset = magma
reset inputs.0.multifile.filenames
inputs.0.multifile.filenames.+ = *1712*Training Model-R01*.bin
inputs.0.multifile.filenames.+ = *1713*Training Model-R05*.bin
outputs.0.file = gradient2.pdf
run
```
Here, we are running the graph once as above and then making some changes:

* changing the input directory
* changing the input to read different filenames, this time loaded using ["wildcards"](https://tldp.org/LDP/GNU-Linux-Tools-Summary/html/x11655.htm)
* changing the *expr* node's expression to show just the 440nm channel
* changing the gradient's appearance with a preset
* changing the output to write to a different filename

@@@todo
Write more on how the inputs work - intro here, more in params.md or
elsewhere. Write more in general. Note [autodocs](/autodocs).

Finish.
@@@

* [Parameter file format](params.md)


