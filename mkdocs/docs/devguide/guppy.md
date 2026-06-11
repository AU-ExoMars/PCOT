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
|$a^b$|$\sqrt{a^{2b-2} \left((a \sigma_b \ln a)^2 + (b \sigma_a)^2\right)}$|If $b=1$, $\sigma_a$ is output. If $a=0$ and $b<0$, zero is output. Upstream code in Value catches this and sets the DQ UNDEF bit (i.e "undefined")|
|$\sin(a)$|$\sqrt{\left(\sigma_a\cos a\right)^2}$||
|$\cos(a)$|$\sqrt{\left(\sigma_a\sin a\right)^2}$||
|$\tan(a)$|$\sqrt{\left(\sigma_a\sec^2 a\right)^2}$|If the secant would be large, e.g. $a=\frac{\pi}{2}$, it is clipped at a very large value and DIVZERO is set in the DQ bit of the output.|
|$a \wedge b$|$\min(\sigma_a,\sigma_b)$|i.e. the fuzzy logic "OR" operator, "\|" in Python |
|$a \vee b$|$\max(\sigma_a,\sigma_b)$|i.e. the fuzzy logic "AND" operator, "&" in Python|
|$\sqrt{a}$|calculated as $a^{0.5}$||

Other operations (negation, inversion) leave the uncertainty unchanged.

## Calculations with uncertainty using `Datum`

This is usually the best way to work with uncertainty, particularly when
`ImageCube` objects (i.e. images) are involved. `Datum` is the data type that
wraps everything that travels between nodes in PCOT, and particularly deals with
converting ImageCube into Value objects so that calculations involving both can
be performed. It also handles regions of interest in images.

The `Datum` class implements most operations as "dunder" methods, so writing
the operations is easy. First, however, you will probably need to wrap your data.

### Wrapping values

The `Value` class represents numerical data (scalars or arrays) along with their uncertainty and DQ bits.
(Images are represented by ImageCube objects instead, with extra information for regions
of interest etc.)
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
will set the NOUNC (no uncertainty) DQ bit.

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

### Retrieving data from Datum objects

You can get your data out of a Datum by using the `get()` method if you know the Datum's type (which you should), e.g.:

```python
v = Datum.get(Datum.IMG)
```

### Performing calculations

Once the data is wrapped in Datum objects, all of the following operations will work and propagate uncertainty correctly on any pairing of ImageCube and Value:

* addition, subtraction, multiplication, division, exponentiation
* Min and max (using & and | respectively)
* unary negation
* unary inversion (i.e $1-x$) (with "~" in Python)

In addition, the following functions are defined as method on Datum:

* sin, cos, tan
* sqrt
* abs

The following are also defined, but act differently depending on the underlying type:

* mean, sd, sum
* min, max

For these methods

* A 1D or 2D value will produce a single result
* A multiband image will produce a vector Value of results with the result for each band.

For example, if **d** is an RGB image, calling `d.mean()` will return a Value holding an array with three elements: the mean for each band.
Calling `mean` on that again, by running `d.mean().mean()`, will produce the mean of those three values.


### Example of Datum calculations
Below is an example of using Datum to perform a calculation on an ImageCube while
propagating uncertainty. The (rather unusual) calculation is

$A' = (0.2 \pm 0.01) \sin(A) + 0.3$

That is, we are taking the sine of every pixel in the image, multiplying it by the 
constant $0.2 \pm 0.01$, and finally adding $0.3$, all while propagating uncertainty.

Here is the code:
```python
# Create a Datum holding 0.2 +/- 0.01. We could do this with Datum.k() but it's
# good to see it in full
Datum v = Datum(Datum.NUMBER, Value(0.2, 0.01), Datum.null)
# Wrap an existing ImageCube in a Datum and calculate the sine of all pixels
imgD = Datum(Datum.IMG, myImageCube).sin()
# Multiply the two Datum objects together and add 0.3
out = (v * imgD) + Datum.k(0.3)
# Get the ImageCube out of the result
out = Datum.get(Datum.IMG)
```
More briefly,
```python
Datum.k(0.2,0.01) * Datum(Datum.IMG,myImageCube).sin() + Datum.k(0.3)
```

## The Value class
As mentioned above, numeric values and arrays are stored using the [`Value` class](/devguide/values),
and occasionally it may be necessary to work at this level. It is also useful to understand
some of the extra work that is done here in addition to the "raw" uncertainty
calculations which are mentioned in the final section.

Binary operators on Value objects are supported, as well as the negation and inversion
unary operators ("-" and "~" respectively). However, both sides of the operator must be Values - if you want to work on
different types you must wrap them in Datum, as described above. The Datum class will convert ImageCubes into Value
objects internally and operate on those.

As well as the "core" uncertainty propagation, the following takes place:

* DQ bits from both "parents" are propagated into the result using bitwise OR.
* Division by zero will mark the result as DIVZERO and set mean and uncertainty to zero. Dividing zero by zero will also set the UNDEF bit. 
* If the result of exponentiation is infinite or complex, it will be set to zero and the COMPLEX bit will be set (e.g. finding the root of -1).
* Bitwise AND and OR actually find the min and max respectively, and set the uncertainty and DQ from that value too.
* `sqrt` is defined, and raises to the power of 0.5 using the pow method, so uncertainty is propagated.
* `sin` and `cos` are defined and uncertainty is propagated using code here, not in the lower level code.
* `tan` is defined, but using the secant for uncertainty (since we can't use sin/cos for this since the values are uncertain). That means we have an edge case where the angle is close to zero - we set DIVZERO here.
* The `uncertainty` method will give the uncertainty, and if the value is an array the uncertainty will be pooled using Rudmin's method (see below).


## Low level functions for uncertainty in binary operations

Functions in `value.py` deal with numpy arrays or Python numbers, and generally take values $a$ and $b$ and their uncertainties $ua$ and $ub$ 
expressed as standard deviation. These are used by the above functions and methods, and you probably shouldn't deal with  them directly. However, you 
may find these occasionally useful.

* **add_sub_unc(ua,ub)** adds the values in quadrature: $\sqrt{ua^2+ub^2}$ giving the uncertainty for the sum or difference.
* **add_sub_unc_list(a,b)** is like the above, but works on a list or array of uncertainties
* **mul_unc(a,ua,b,ub)** gives the uncertainty for multiplication of two values $a\pm ua$ and $b\pm ub$  by calculating $\sqrt{a\cdot ub^2+b\cdot ua^2}$ , which is a simplification of the standard formula.
* **div_unc(a,ua,b,ub)** gives the uncertainty for division of two values $a\pm ua$ and $b\pm ub$  by calculating $\frac{\sqrt{a\cdot ub^2+b\cdot ua^2}}{b^2}$ , which is a simplification of the standard formula.
* **pow_unc(a,ua,b,ub)** does the same for raising $a$ to the power $b$, 
	* It uses the moderately horrific expression $\sqrt{a^{2b-2} \left((a \sigma_b \ln a)^2 + (b \sigma_a)^2\right)}$
	* If $b=1$ it outputs $ua$ directly
	* If $a=0$ and  $b<0$ it outputs zero; upstream code will catch this case and mark DQ as UNDEFINED.
	* It doesn't handle the case where the results are complex (e.g. $a<0$ and $b=1.25$). This is handled upstream.

### Pooling uncertainty

Often we need to find the uncertainty of a set of values, each of which has its own uncertainty. An example is finding the uncertainty of a region
of pixels in an image, where each pixel has its own uncertainty.

To do this, we pool the uncertainty using Rudmin's method[^1]: the pooled variance is the mean of the variances plus the variance of the means.
That is, we calculate the mean of the individual variances, and add the variance of the mean values.

This is done in the `pooled_sd(means,uncs,axis=None)` function in `pcot.utils.maths`:

* **means** is a list or array containing the means
* **uncs** is a list or array containing the standard deviations
* **axis** is the axis along which the calculations should be performed - it is passed into `np.var` and `np.mean`. `None` means we flatten the array into
a 1D array first.

Note that this function operates on standard deviations and returns a standard deviation - conversion to and from variance is done inside the function.

[^1]: Rudmin, J. W. (2010) "Calculating the exact pooled variance" arXiv preprint arXiv:1007.1012
