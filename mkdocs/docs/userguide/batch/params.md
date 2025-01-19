# Parameter file format


## The basics

Parameter files are just lists of changes to be made 
to a structure. This structure contains information about the document's
inputs and nodes, and how the system should output the resulting data
once the document has run.

Each line in the file changes an element in the structure. For example,

```txt
inputs.0.rgb.file = mydata/foo.png
```
tells the system to change input 0's RGB loading method that it should
load the file `mydata/foo.png`. Only one loader can be active for each
input, and this change will "activate" input 0's RGB loader.

Another change could be:
```txt
k.val = 2
```
which assumes that there is a node called `k`, whose parameter `val`
we now set to 2 (this is probably a [constant](/autodocs/constant) node).


## Lists

Some of the elements in the parameter structure file are lists. We
can add to lists by putting a `+` in the path. For example, there
is a list of filenames to load inside each input's multifile loader.
We can add elements to it like this:

```txt
inputs.0.multifile.directory = mydata/multi
inputs.0.multifile.filter_pattern = *Filter(?P<lens>L|R)(?P<n>[0-9][0-9]).*
inputs.0.multifile.filenames.+ = FilterL02.png
inputs.0.multifile.filenames.+ = TestFilterL01image.png
inputs.0.multifile.filenames.+ = FilterR10.png
```
This tells the multifile loader where the files are (the `directory`
element), how to decode the names to get a filter (the `filter_pattern`
element) and finally adds three filenames to the filename list.

What the `+` element actually does is create a new item at the end of
the list and start modifying that item. In the example above each item
is just a string, but they could be structures. Adding a new structure
to a list creates a default structure and adds it, and we can then
immediately modify it.

For example, we can add a new output like this:
```txt
outputs.+.file = out.csv
outputs.0.clobber = y
outputs.0.node = spectrum
```
The first line creates a new default output element in the outputs and
sets its `file` to `out.csv`. The next two lines modify other values within
that same output, which is the first output (numbered zero).

We can write this more concisely using a relative path.

## Relative paths

The left-hand side of each line is called the "path" because
it describes how to get to each item we need to change. 
You'll notice from the above example that there can be a lot of repetition in
paths as we change a lot of elements at the same level within the
structure. So far we have seen *absolute* paths describing route in full,
but if we start a path with a `.` - making a *relative* path - we 
are assumed to be at the same place as the last change.

We can change the previous output example to this:
```txt
outputs.+.file = out.csv
.clobber = y
.node = spectrum
```
The first line creates a new output element and sets its `file` to "out.csv".
The next two lines modify that output element, because the last thing we set
was `output.0.file`, inside `output.0`. 

We can also modify the input example the same way:
```txt
inputs.0.multifile.directory = {globaldatadir}/multi
.filter_pattern = *Filter(?P<lens>L|R)(?P<n>[0-9][0-9]).*
.filenames.+ = FilterL02.png
.+ = TestFilterL01image.png
.+ = FilterR10.png
```
The leading `.` means "stay at the same level," which in this case is
`inputs.0.multifile`.

## Path setters

If we write a path without setting a value, it just sets the current path for
the next items - this kind of line is called a **path setter**. 
We could also write the output example like this:
```txt
outputs.+
.node = spectrum
.file = out.csv
.clobber = y
```
The first line creates a new output and sets the path. The next
three lines modify the structure at that path - the output just created.



### Going up levels with multiple dots

In the example above we add an output and then modify it. We could add another output
by adding an extra set of lines, like this:
```txt
outputs.+.file = out.csv
.clobber = y
.node = spectrum

outputs.+.file = out2.csv
.node = spectrum2
```
But we can also do this:
```txt
outputs.+.file = out.csv
.clobber = y
.node = spectrum

..+.file = out2.csv
.node = spectrum2
```
That's because after the first output, our path is set to `output.0.`. Using two dots
lets us go back up the path one level, to `output.`, so we can now add a new output.

### List notation for ordered parameters

Some parameters have an implicit ordering. These are marked in the documentation as
"(ordered)". For example, the *circle* node type [autodocs](/autodocs/circle/) contain
this:

<table border='1' style='border-collapse: collapse;'>
<tr><td rowspan="3" style="border-right: none;">croi</td><td rowspan="3" style="border-left: none;">circle definition (ordered)</td><td rowspan="1" style="border-right: none;">x: integer (default 0)</td><td rowspan="1" style="border-left: none;">Centre x coordinate</td></tr>
<tr><td rowspan="1" style="border-right: none;">y: integer (default 0)</td><td rowspan="1" style="border-left: none;">Centre y coordinate</td></tr>
<tr><td rowspan="1" style="border-right: none;">r: integer (default -1)</td><td rowspan="1" style="border-left: none;">Radius</td></tr></table>

That means that while you can set the region of interest within a *circle* node with this:
```txt
circle.croi.x = 100
.y = 100
.r = 20
```
you can also use a list, and the values will be assigned from the list with the order given
in the documentation:
```txt
circle.croi = [100,100,20]
```

### The 'run' directive - running multiple times

If the file contains a line with just the word `run` (excluding comments), PCOT will
run with the parameters as they stand at the current point in the file. That means you can
write things like this:
```txt
outputs.+.file = double.csv
expr.expr = a*2
run

outputs.0.file = triple.csv
expr.expr = a*3
run

outputs.0.file = quad.csv
expr.expr = a*4
run
```
Here we are running the same graph three times, with three different expressions in the
node called `expr`. Each time we are modifying the first (and only) output filename. Note
that we need to create output for the first run,
and then we modify its filename for subsequent runs.

### Using Jinja2 templates

Before they are run, each parameter file is processed using the
[Jinja2 templating engine](https://jinja.palletsprojects.com/en/stable/templates/), more typically
used to create websites (as is obvious from its documentation).

Here is an example of a file written to make use of this facility. It performs some
manipulations on an image, writing the results to a single PARC (PCOT archive) file.
It will generate four images.

```txt
outputs.+.file = output.parc
.annotations = n    # annotations not supported in PARC
.node = striproi(a,1)
.name = main   # the name the output will have in the PARC file
.description = Primary output image     # description in the PARC
run

# now we run a loop for values 1,2,3 using Jinja2

{% for i in range(1,4) %}
    # just one output, keep the same file and settings but append.
    outputs.0.append = y    # we are now appending to the PARC
    .node = test{{i}}       # get output from node1, node2 or node3.
    .name = testimg{{i}}    # call it testimg1, testimg2 or testimg3
    .description = Test image {{i}}
    run
{% endfor %}
# normally a "run" is silently appended to the end of a parameter file,
# but this won't happen if the previous command was also a "run", which
# it will be here.
```

PCOT automatically sets up the following Jinja2 variables for you to use:

|variable name|description|
|-----------|----------|
|{{docpath}}|the path to the document (with backslashes replaced by forward slashes)|
|{{docfile}}|the name of the document file (i.e. the final part of the path)|
|{{datetime}}|the current date and time in ISO 8601 format|
|{{date}}|the current date in ISO 8601 format|
|{{count}}|the number of times the document has been run (useful in loops)|
|{{parampath}}|the path to the parameter file (if one is used, it is "NoFile" otherwise)|
|{{paramfile}}|the name of the parameter file (if one is used, it is "NoFile" otherwise)|

We also set up some Jinja2 "filters" to manipulate filenames, etc.:

|filter|action|
|-------|-----------|
|basename|return the last part of a file path: "foo/bar.png" becomes "bar.png"|
|dirname|return the directory part of a file path: "foo/bar.png" becomes "foo"
|stripext|remove extension: "foo.bar" becomes "foo"|
|extension|get extension: "foo.bar" becomes ".bar"|

This lets us do things like this, which will add the parameter file name
as a prefix to any text output, but strip off any directory elements:
```txt
output.0.prefix = {{paramfile | basename}}
```




@@@danger
Not yet written below here
@@@


## Inputs, outputs and nodes
