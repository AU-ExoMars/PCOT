# Expression parser syntax

The standard operators +,/,\*,- and ^ all have their usual meanings. When applied to images they work in
a pixel-wise fashion, so if "a" is an image, **2\*a** will double the brightness. If **b** is also an image,
**a+b** will add the two images, pixel by pixel. There are two non-standard operators: **.** for properties
and **$** for slice extraction. These are described below.

Operator | description | precedence 
-------- | ----------- | ----------
\+ | add | 10
\- | subtract | 10 (50 for unary)
/ | divide | 20
\* | multiply | 20
^ | exponentiate | 30
. | get property | 80
$ | get slice | 90

## Properties

The **.** operator takes an identifier on the right hand side, and extracts a property from the value on
the left - typically an image. This is often used to apply parameterless functions to an image.
Note that brackets may be required to stop the parser interpreting the operator as a trailing
decimal - for example **a$780.norm** must be written as **(a$780).norm**.

Properties currently supported are:

Property name | description
--------------| -------
w | image width
h | image height


For example, if **a** and **b** are images, then **(a+b).w** will add the two images and give the
width of the result. 

## Functions

The following functions are supported:

Function | description
-------- | -----------
min | minimum value
max | maximum value
sd | population standard deviation
mean | mean value
sin | sine
cos | cosine
tan | tangent
sqrt | square root 
norm | normalize an image to [0,1] (all bands are considered together)
clip | clip an image to [0,1]
curve(a,mul,add) | apply a logistic sigmoid to the image, first multiplying by *mul* and adding *add*
merge(a,b..) | merge multiple images (or slices) into a single image


## slice extraction

The notation **$name** or **$wavelength** takes an image on the left hand side and extracts a single
slice, generating a new image. The right hand side is either a filter name, a filter position or a wavelength.
Depending on the camera, all these could be valid: **a$780**, **(a+b)$R5_780**, **((a+b)\*2)$780**.


