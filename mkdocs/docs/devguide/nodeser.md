# Node serialisation

This page discusses how to serialise the parameters for 
node types. If you don't know what that means, you're either in the wrong
place or haven't read [Writing PCOT plugins](plugins.md).

Nodes typically store parameters and data as attributes of their `XForm`
objects. It's not really "polite" programming, but this is the kind of thing
you can do with Python. For example, the *expr* node contains a string also
called *expr*, which is the expression to be run. These values are initialised in
the constructor for the node's `XFormType`.

When you write nodes you will probably need to save and load some of these values,
both to files and so that the undo mechanism will work.

This process - converting node data into data which can be saved to archives -
is called **serialisation**, and there no less than four different mechanisms
for doing it. This is largely for historical reasons, but also because the
different mechanisms serve different needs:

In order of preference, with the best at the top:

* **TaggedAggregate serialisation** - the data is JSON-serialisable but we want to make it possible to
edit it from a batch/parameter file (see [batch mode](/userguide/batch)). **Probably the best choice if you can.**
* **complex serialisation via TaggedAggregate** - the data is not serialisable, but we want to
edit it from a parameter file. **Probably the second-best.**
* **autoserialisation** - for when your data is already JSON-serialisable and you 
don't need to edit it from a parameter file. It is very simple to implement.
* **complex serialisation** - for when your data is not directly JSON-serialisable (for example,
regions of interest) and you don't need to edit it from a parameter file.

## TaggedAggregate serialisation

This is the method we use when we want to be able to edit the parameters of nodes in batch mode,
using parameter files (see [batch mode](/userguide/batch)). It is probably the best method
to use because of this, but it is rather more complicated.

We make use of **tagged aggregate structures**, which can be found in
`pcot.utils.taggedaggregate`. These are dictionaries and lists, but
each has a formal, typed structure with "tags" giving the names of the
members, their types, and default values. Each is described by a type
singleton object

For example, here is a `TaggedDictType` definition for a rectangle. 
This is for an ordered dict, so it will be serialised
to a tuple. Hopefully it is self-explanatory:

```python
taggedRectType = TaggedDictType(
    x=("The x coordinate of the top left corner", Number, 0),
    y=("The y coordinate of the top left corner", Number, 0),
    w=("The width of the rectangle", Number, 10),
    h=("The height of the rectangle", Number, 10)).setOrdered()
```
@@@info
Bear in mind that there are functions for generating rectangle and colour type object in
pcot.utils.taggedaggregates: taggedColourType and taggedRectType. You probably shouldn't
create a rectangle type yourself.
@@@

This could then be embedded in a `TaggedDictType`:
```python
taggedThingType = TaggedDictType(
    rect=("The rectangle", taggedRectType),
    somenumber=("Some numerical value",Number,0))
```
which we could then form into a list:
```python
listOfThingsType = TaggedListType("list of things",taggedThingType,0)  # default zero means empty list
```
We could then create a new list and add things like this:
```python
listOfThings = TaggedListType.create()
listOfThings.append_default()
```    
We can then access these items:
```python
print(listOfThings[0].rect.x)
```
For more details on how to use these structures, read the tests in `tests/test_taggedaggs.py`.

@@@info
You might wonder why we don't make all tagged dicts ordered, so they
are all serialised as tuples. The answer is that doing that would make
it harder to implement backcompatibility - if we serialise as a tuple,
adding and removing fields in the future becomes difficult. Only 
use ordered dicts for things like rectangles, where we are very unlikely
to change the structure. In fact, I'm only doing it for legacy support.
@@@

You'll note that all the elements of a TaggedAggregate structure are JSON-serialisable, although
some can be numpy arrays. However, the nature of the structure allows defaults - and documentation -
to be generated automatically.

## Using TaggedAggregates to serialise nodes

To use a TaggedAggregate to serialise node data, create a `TaggedDictType ` and assign
it to the `params` member of the `XFormType` in the constructor. For example:
```python
        self.params = TaggedDictType(
            mul=("multiplicative factor (done first)", float, 1.0),
            add=("additive constant (done last)", float, 0.0))
```
When a new node is created, a default structure will be created from this type and stored in the
node's `params` field where it can be accessed:
```python
output = node.params.add + node.params.mul * node.getInput(0, Datum.IMG)
```
When the node is serialised, the structure will be serialised.

## complex TaggedAggregate serialisation (CTAS)

The previous method dealt with data which can be JSON-serialised directly. If
we need to modify non-JSON-serialisable data with parameter files, we need to
do something similar to the complex serialisation method described above but
going through a TaggedAggregate: we set the TaggedAggregate from our complex
data, and then PCOT will serialise that.

To do this, we create a `params` in the type as we did in the previous
section, containing a TaggedDictType which we will build from our actual data.

Now we write `serialise` as before, but building a TaggedDict from the
data and storing it in the node's `params`. It should return None, because we're not using a standard Python
dict for serialisation. Here's an example:

```python
def serialise(self, node):
    node.params = self.params.create()
    
    # fill in the node.params with data
    node.params.foo = some_data_or_other
    node.params.bar = some_data_or_other
    

    # we don't return anything, because node.params will have been set to
    # represent our data; we don't need to add anything directly to the
    # JSON-serialisable dict.
    
    return None
```

Instead of a `deserialise` method we should write `nodeDataFromParams`. This
takes a node, and uses its `params` field (a TaggedDict) to set the
node's internal data:

```python
def nodeDataFromParams(self, node):
    # convert some data in node.params into our own private data
    our_data = some_function_of(node.params.foo, node.params.bar)
```

**Maybe**

Types and TaggedAggregate type objects can be "wrapped" in `Maybe` objects if they might be null:
```python
    tdt = TaggedDictType(
        a=("a", int, 10),
        b=("b", Maybe(str), "foo"),        # string or null
        c=("c", float, 3.14)
    )
    td = tdt.create()           # create new dict
    td.b = "hello"              # this is fine
    td.b = None                 # and so is this
```

@@@info
Note: I would have used Optional from the typing package, but that can only take actual types -
not the type objects we use here.
@@@

@@@danger
Avoid using Maybe for tagged aggregates etc., because you can't
*create* a new one using a parameter file, just modify values in an
existing one.
@@@

**TaggedVariantDicts**

Sometimes it is necessary to store different kinds of object in a list. We can do this with
TaggedAggregates, provided the objects are all TaggedDicts and there is a field in all the dicts
which tells us which type it is - a "discriminator". 

[You can find more details on TVDs here](taggedvardicts.md)


@@@info
**Where to find examples**

Probably the most complex but straightforward example of CTAS is the *gradient* node. This
converts a monochrome image to a false colour RGB gradient based on a set of gradient colours. This
exists as a pcot.utils.gradient.Gradient object which is a wrapper around a list of (x,(r,g,b)) tuples
defining the colour *r,g,b* at value *x*. 

The CTAS methods are responsible for converting tagged aggregate data and this
Gradient object. They also handle a *preset* string which can override the
data when set from a [parameter file](/userguide/batch).

[Regions of interest are a rather more complex example...](roi_ctas.md)
@@@


## Autoserialisation

In the simplest case, the data stored in the `XForm` object for a particular
node is already JSON-serialisable: that is, it is either a Python
primitive type (number, string, tuple, list or dict) or a Numpy array
(PCOT handles serialising these automatically). In this case you can simply
list the names of the attributes in a tuple called `autoserialise` in the `XFormType`,
along with some defaults which are used in case the items are not found in the saved data.

For example, the constructor for `XFormSpectrum` looks like this:

```python
        super().__init__("spectrum", "data", "0.0.0")
        self.autoserialise = ('sortlist', 'errorbarmode', 'legendFontSize', 'axisFontSize', 'stackSep', 'labelFontSize',
                              'bottomSpace', 'colourmode', 'rightSpace',
                              # these have defaults because they were developed later.
                              ('ignorePixSD', False),
                              ('bandwidthmode', BANDWIDTHMODE_NONE),
                              )
        for i in range(NUMINPUTS):
            self.addInputConnector(str(i), Datum.IMG, "a single line in the plot")
        self.addOutputConnector("data", Datum.DATA, "a CSV output (use 'dump' or 'sink' to read it)")
```
Note that the default values are optional - if you don't specify a default you can just
use the attribute name rather than a `(name, default)` tuple, but you will get an error if
you try to load from data which doesn't have that attribute stored.

When the system serialises the node it will read the named fields from the node, and it will
do the reverse when it deserialises a node (i.e. load it from an archive).

## Complex serialisation

In this case, we have data which isn't JSON-serialisable. We have to provide code to do this.
This is done by adding `serialise` and `deserialise` methods to the `XFormType` to 
convert our data to and from data
which is JSON-serialisable. The `serialise` method will take the node and return a dict
(which is JSON-serialisable), while the `deserialise` method will take the node and the dict
and set the appropriate values a newly created node. The dict returned by `serialise` will be merged
with the dict generated by autoserialisation and other, general node data (e.g. canvas data). 
Make sure you use unique names and not any of:
```txt
canvas, displayName, inputTypes, ins, outs, mapping, md5, type, ver, w, xy, outputTypes
```

An example: imagine our node stores a list of objects of some class
`Foo`. We could write our methods thus:

```python
def serialise(self, node):
    return {'foolist': [(x.a, x.b) for x in node.foo_list]}

def deserialise(self, node, d):
    node.foo_list = [Foo(a, b) for a, b in d['foolist']]
```    
In this case we are converting the Foo objects into tuples to serialise them,
and constructing them from the tuples when we deserialise. It would probably be
better to write `Foo` so that it can serialise itself and has a deserialise constructor:

```
class Foo:
    def __init__(self...):
        ...
        
    def serialise(self)->dict:
        return ...
        
    @staticmethod
    def deserialise(d: dict):
        return Foo(...)
```

and

```python
def serialise(self, node):
    return {'foolist': [x.serialise() for x in node.foo_list]}
    
def deserialise(self, node, d):
    node.foo_list = [Foo.deserialise(x) for x in d['foolist']]
```    

