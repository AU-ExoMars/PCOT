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
.file = out.csv
.clobber = y
.node = spectrum
```
The first line creates a new output and sets the path. The next
three lines modify the structure at that path - the output just created.



@@@danger
Not yet written below here
@@@

### Going up levels with multiple dots

### List notation for ordered dicts

Some parameters are grouped together

### Using Jinja2 templates

## Inputs, outputs and nodes
