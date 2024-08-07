# The *expr* node

The *expr* "expression" node performs mathematical operations on its four inputs, which
(currently) must be images or scalar values. Constant scalars can also be used.

The node can be found in the "maths" section of the palette. It has four inputs and one output,
and these can be of any type - the output type will be determined when the expression runs.

The *expr* node is unusual in that the node's box in the graph
will show the expression being calculated:

![!An example of a graph showing an expr node which is running a merge function,
combining the channels of two images into a single image.](exprexample.png)

In this example, two images showing slightly different views of the same scene
with different bands (one visible light, one infra-red) 
are registered using the *manual register* node. They are then merged together using the
`merge` function. The box shows this function, and also `IMG[12]` indicating that the
result is a 12-band image.

## Functions

Merge is one of a large number of functions that *expr* supports, and more can be added
using the [plug-in mechanism](/devguide/plugins/). Full details of built-in functions 
can be found [in the autodocs](/autodocs/#expr-functions)

## Properties

Certain types of value have "properties" which can be extracted with the dot operator.
For example, `a.w` will extract the width of the image in variable $a$, and 
`(a+b).n` will return the number of pixels in the image which results from adding images
$a$ and $b$. There aren't many properties, but those that exist are listed
[in the autodocs](/autodocs/#expr-properties).

## Autodocs
@@@info
The text below is drawn from the [automatically generated documentation](/autodocs/) for
the node, and is the authoritative documentation.
@@@

--8<-- "autodocs/expr.md"
