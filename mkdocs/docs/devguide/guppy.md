# GUPPY: Guide to Uncertainty in PCOT Python

When you are writing code which uses PCOT as a library, or adding
new nodes or other functionality to PCOT itself, you will be dealing
with quantities which have inherent uncertainty. Every number, including
individual pixels in images, has a standard deviation. 

It is important that calculations on these quantities
propagate the uncertainty correctly. For example,

\\[
2 \pm 0.1 + 3 \pm 0.1 = 5 \pm \sqrt{0.2}
\\]

because the standard deviations add in quadrature:

\\[
\sigma_{a+b} = \sqrt{\sigma^2_a + \sigma^2_b}
\\]

This document will show the formulae that are used to propagate uncertainty
and show how you can write code using PCOT's implementations of these 
formulae at several different levels.

## Assumption of independent variables

All this assumes that the **variables are independent**: given the complexity
of some the calculations in PCOT, the paths data can take through a graph, and
the nature of the sources, it would be impossible to work out all the
covariances. You need to consider this carefully both in your calculations
and how you use PCOT [as we have seen before](/gettingstarted/concepts/#uncertainty).


## Formulae used

|Operation|Formula|Notes
|------|------|--------|
|$a+b, a-b$|$\sqrt{\sigma^2_a+\sigma^2_b}$||
|$a \times b$|$\sqrt{(a \sigma_b)^2+(b \sigma_a)^2}$||
|$a / b$|$\sqrt{(a \sigma_b)^2+(b \sigma_a)^2}/{b^2}$||
|$a^b$|$\sqrt{a^{2b-2} \left((a \sigma_b \ln a)^2 + (b \sigma_a)^2\right)}$|If $b=1$, $\sigma_a$ is output. If $a=0$ and $b<0$, it outputs zero. Upstream code in Value catches this and sets the DQ UNDEF bit (i.e "undefined")|
|$\sin(a)$|$\sqrt{\left(\sigma_a\cos a\right)^2}$||
|$\cos(a)$|$\sqrt{\left(\sigma_a\sin a\right)^2}$||
|$\tan(a)$|$\sqrt{\left(\sigma_a\sec^2 a\right)^2}$|If the secant would be large, e.g. $a=\frac{\pi}{2}$, it is clipped at a very large value and DIVZERO is set in the DQ bit of the output.|
|$a \wedge b$|$\min(\sigma_a,\sigma_b)$|i.e. the fuzzy logic "OR" operator|
|$a \vee b$|$\max(\sigma_a,\sigma_b)$|i.e. the fuzzy logic "AND" operator|
|$\sqrt{a}$|calculated as $a^{0.5}$||

Other operations (negation, inversion) leave the uncertainty unchanged.

## Calculations with uncertainty using `Datum`

This is usually the best way to work with uncertainty, particularly when
`ImageCube` objects (i.e. images) are involved. `Datum` is the data type that
wraps everything that travels between nodes in PCOT, and PCOT knows how to
propagate uncertainty through calculations that involve images and values.

The `Datum` class also implements most operations as "dunder" methods, so writing
the operations is easy. First, however, you will probably need to wrap your data.

### Wrapping values

The `Value` class represents numerical data (scalars or arrays) along with their uncertainty and DQ bits.
When wrapping a Value, you will need to provide information about the source of the data as a `SourceSet`
object. If you are just dealing with a constant, or an arbitrary value which has not come from mission data, you 
just use the "null" source, and wrap your value like this:
```
d = Datum.k(0.5)        # wraps the number 0.5
```
or if you need to provide uncertainty:
```
d = Datum.k(0.5,0.001)
```
The **k** stands for "constant." Note that if you provide an uncertainty of exactly zero, the Value constructor
(which this calls) will set the NOUNC (no uncertainty) DQ bit.

If you need to wrap a Value that has come from some other calculation, you may need to provide a source.
That's beyond the scope of this part of the documentation, but if you are dealing with data 
from an image you can use the `getSources()` method in `ImageCube`. Wrap the data with:

```
d = Datum(Datum.NUMBER,value,source)
```

### Wrapping images

Wrapping an ImageCube is usually easy, because the object itself contains its source
information. Typically you can just do

```
d = Datum(Datum.IMG, my_imagecube)
```

### Retrieving data from `Datum`

You can get your data out of a Datum by using the `get()` method if you know the Datum's type (which you should):

```python
d = Datum(Datum.IMG, my_imagecube)
v = Datum.get(Datum.IMG)
```
will get out the image you put in.

### Performing calculations

Once the data is wrapped in Datum objects, all of the following operations will work and propagate uncertainty correctly on any pairing of ImageCube and Value:

* addition, subtraction, multiplication, division, exponentiation
* Min and max (using & and | respectively)
* unary negation
* unary inversion (i.e $1-x$) (with "~" in Python)

So you can write
```python
# Create a Datum holding 0.2 +/- 0.01. We could do this with Datum.k() but it's
# good to see it in full
Datum v = Datum(Datum.NUMBER, Value(0.2, 0.01), Datum.null)
# Wrap an existing ImageCube in a Datum
imgD = Datum(Datum.IMG, myImageCube)
# Multiply them together and add 0.2
out = (v * imgD) + Datum.k(0.2)
# Get the ImageCube out of the result
out = Datum.get(Datum.IMG)
```
In addition, the following functions are defined as method on Datum:

* sin, cos, tan
* sqrt
* abs

The following are also defined, but act differently depending on the underlying type:

* mean, sd, sum
* min, max

For these methods

* A 1D or 2D value will produce a single result
* A multiband image will produce a vector Value of results, one for each band.

For example, if **d** is an RGB image, calling `d.mean()` will return a Value holding an array with three elements, one for each band.
Calling `mean` on that again, by running `d.mean().mean()`, will produce the mean of those three values.

