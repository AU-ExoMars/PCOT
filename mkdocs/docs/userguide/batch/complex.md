# A more complex example

Here's a slightly more complex example that makes use of 
[Jinja2](https://jinja.palletsprojects.com/en/stable/templates/)
templates. Jinja is usually used to generate web pages, but it can
also be used to manipulate batch files before they are actually run.

Here, we use it to loop through a set of filenames stored in a
separate file, so we can run a PCOT document on each one.
I'll go through the code line by line (more or less) and then show
it all at the end.

## Jinja basics

Jinja is a templating system. It uses special codes embedded in
the batch file to manipulate it and change its contents, before
the file is actually interpreted by the batch system.

* Codes of the form `{%...%}` are Jinja "statements", which control
the flow of what Jinja is doing and set variables.

* Codes of the form `{{...}}` are "expressions" - Jinja calculates the
expression's value and inserts it into the document. The expression
is often just a variable name, and in this case Jinja will replace the
code with that variable's value.

There's a lot more detail in [the Jinja2 docs](https://jinja.palletsprojects.com/en/stable/templates/)
but bear in mind they are written very much from the point of view
of web design.


## The walkthrough

We start by setting up our input. We're going to use a single input -
input 0 - and it's going to load and debayer an RGB image.
This sets up input 0 to use the RGB method, and says that it should
use Malvar-He-Cutler debayering:

```txt
inputs.0.rgb.debayer_algo = MHC
```

Still on input 0's RGB method, we tell it to use the GRGB debayer pattern.
Remember that if we start with a leading `.`, that means we are setting
a parameter in the subsystem in which we last set a parameter,
in this case `inputs.0.rgb`:

```txt
.debayer_pattern = GRBG
```

We now add a new output (output 0) using the `+` operator, telling it
that it should generate the output from a node called "sink":
```txt
outputs.+.node=sink
```
and we tell this output that's it's OK to overwrite existing files:
```txt
.clobber = y
```

So far, this should all be familiar to you from the rest of the batch
file documentation. Now we'll use the Jinja templating system to
load a list of files from another file called `list.txt`, 
and we'll loop through them. This is done with 
Jinja's `{% for.. %}` / `{% endfor %}` statements in association with
the `loadlist` function, which loads lines of text from a file (stripping
comments and blank lines):
```txt
{% for name in loadlist("list.txt") %}
```

Within the loop we create the input and output filenames, storing
them as Jinja variables. We do this using `{% set var = expression %}`
statements. 

First, we create the input name by just copying the `name` variable.
```txt
	{% set input = name %}
```

We then generate the output name by using
Jinja's built-in `replace` 
[filter](https://jinja.palletsprojects.com/en/stable/templates/#filters){:target="_blank}
to replace the `.png` at
with `_corrected.png`:
```txt
	{% set output = name | replace(".png","_corrected.png") %}
```
Now we can set the input filename within the input we set up
earlier:
```txt        
	inputs.0.rgb.filename = d:\PCOTdata\HRCdata\{{input}}
```
Naturally your full filename will be different; it doesn't have
to be a full path, I'm just showing here what's possible. As noted
above, putting
a name inside `{{..}}` tells Jinja to substitute that variable's
value into the batch file.

Similarly we tell output 0 where to put the result, which we've already
specified will come from the sink node:
```txt
	outputs.0.file = {{output}}
```
Finally we actually do the work, using the batch system's `print` statement
to output messages and the `run` statement to actually run the PCOT document
with the modified settings:
```txt
	print {{input}} read
	run
	print {{output}} written
```

And finally finally, we end the loop we started earlier
```txt
{% endfor %}
```


## Input file format
For reference, the input file might look something like this;
```txt
# some files (this is a comment)
file1.png
file2.png # another comment
```
Anything after a `#` is ignored by `loadlist`, as are blank lines and 
leading and trailing whitespace.

## The whole batch file

```txt
{# Set the RGB input method on input 0, and tell it 
   to use the Malvar He Cutler debayering method. #}
    
inputs.0.rgb.debayer_algo = MHC

{# Still on input 0's RGB method, tell it to use the GRGB debayer pattern. #}

.debayer_pattern = GRBG

{# Add a new output (which will be output 0), and tell it to read
   from the node called "sink" #}

outputs.+.node=sink

{# Tell that output that's it's OK to overwrite existing files #}

.clobber = y

{# Now use Jinja to go over the filename list, which we load from
   another file. #}

{% for name in loadlist("list.txt") %}

        {# create the input and output filenames #}
        
	{% set input = name %}
	{% set output = name | replace(".png","_corrected.png") %}

        {# set the input filename in the input method #}
        
	inputs.0.rgb.filename = d:\PCOTdata\HRCdata\{{input}}
	
        {# set the output name in the output #}

	outputs.0.file = {{output}}

        {# run the PCOT document with those settings, printing out
           some logging information #}
           
	print {{input}} read
	run
	print {{output}} written

{% endfor %}
```
