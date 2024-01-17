# Important classes

## pcot.document.Document

* PCOT keeps all its user data in a **pcot.document.Document**:
This contains:
    * a **pcot.documentsettings.DocumentSettings** object
    * a **pcot.inputs.inp.InputManager** object handling the inputs
    * a **pcot.document.UndoRedoStore** which uses the serialisation/deserialisation
    system to handle an undo stack
    * A dictionary of **pcot.macros.XFormMacro** objects - the user macros
    * most importantly a **pcot.xform.XFormGraph** - a set of nodes connected together
    to do things.

## pcot.xform.XFormGraph
    
This represents the graph of nodes which take data from inputs and perform
operations on them. There is one inside the document, and instances of
macros also contain their own graphs (and the macro itself contains a "template"
graph from which these are created).

A graph contains:

* A set of **pcot.xform.XForm** objects (usually called **nodes**)
connected together by their `inputs` fields, which are tuples of 
(source node, index of output).
* A graph runs by finding those nodes which have no inputs and performing them;
the entire graph will be recursively traversed.
* Nodes are only run if their inputs have data (if their parent nodes have run).

## pcot.xform.XForm

* All nodes are of the same type. Polymorphism - different nodes behaving
differently - is accomplished through each node having a reference to
a **pcot.xform.XFormType** object in its `type` member
that controls its behaviour.
* Nodes communicate by passing **pcot.datum.Datum** objects.
* When a node runs its `perform` method
    * It reads the inputs by deferencing the `inputs` fields and
    getting the input node and index of the output of that node,
    and reading the Datum stored in that output.
    * It processes the data and stores the results in its `outputs` field
    as Datum objects.
    * It then performs its "child" nodes.

## pcot.datum.Datum

This is the fundamental data type, used both for communicating between
nodes and handling values in the *expr* node. A Datum has

* a **type**, which is a **pcot.datumtypes.Type** object
* a **value**, whose type depends on the type field
* a **source** indicating where the data came from

If the value is `None`, the Datum is null. There is a constant
`Datum.null` for null data.

## pcot.datumtypes.Type

The DatumType object provides methods for serialisation, copying,
and display. Each is a singleton. It's easy to create custom DatumTypes.
The most commonly used builtins are:

* **Datum.IMG**:  contains an **ImageCube**
* **Datum.NUMBER**: contains a **Value**

(these names are for the singleton objects, not their types - for example,
`Datum.IMG` has the type `pcot.datumtypes.ImgType`.)


## pcot.imagecube.ImageCube

This is the fundamental image type, consisting of

* **image data** - 2D (H x W) if there is only one band (channel), 
3D otherwise (H x W x D). Type is float32.
* **uncertainty data**, same shape and type as image data. This is the
standard deviation of each pixel.
* **DQ data**. This a 16-bit bitfield for each pixel, describing possible
problems with the data (e.g. no uncertainty, saturated, results from a division
by zero).
* **regions of interest**
* **annotations** that have been added to the image
* **mapping** used to render the image as RGB
* **sources** for each band

## pcot.value.Value

This is the fundamental numeric type, consisting of

* nominal value
* uncertainty value (standard deviation)
* DQ bits

It's usually used for scalars but can also hold array data. If it
does hold array data, the three elements must be the same shape.

This type supports mathematical operations which propagate uncertainty
and DQ.


