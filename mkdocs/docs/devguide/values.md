# How Values work

Value is PCOT's fundamental type for working with uncertain numerical data.
Values are triplets of:

* a 32-bit floating point **nominal** value (i.e. a mean),
* a 32-bit floating point  **uncertainty** value (as standard deviation) around that mean,
* and a set of 16 **data quality** (DQ) bits.

These are usually scalar, but 1D vectors can also be created.

As a user of PCOT you may never encounter Values, but they are used internally
whenever any operations involving uncertainty are done. Here are the typical
situations where that occurs:

## Binary and unary operations on *Value* objects

This is the "base case".
Values have dunder methods for operations. These are usually quite simple, although some
(such as exponentiation) are nasty. They:

* perform the operation to get the new nominal value. This is usually done with a lambda function,
relying on Numpy's broadcasting to do the "right thing" with what it's given.
* call a function to calculate the new uncertainty value
* call a function to combine the two DQs
* pass the three results into Value's constructor to get a new value

Examples - the multiplication operator:
```python
    def __mul__(self, other):
        return Value(self.n * other.n, mul_unc(self.n, self.u, other.n, other.u),
                     combineDQs(self, other))
```
The AND operator:
```
    def __and__(self, other):
        """The & operator actually finds the minimum (Zadeh fuzzy op)"""
        n = np.where(self.n > other.n, other.n, self.n)
        u = np.where(self.n > other.n, other.u, self.u)
        d = np.where(self.n > other.n, other.dq, self.dq)
        return Value(n, u, d)
```


## Binary and unary operations on *Datum* objects

This is for binops - unary operations are much the same, but a lot simpler (although
imageUnop currently takes the underlying numpy array).

1. Datum dunder function runs - this is usually very simple. For example, for addition it's just
    * `return ops.binop(ops.Operator.ADD, self, other)`.
* Calls pcot.expressions.ops.binop with the appopriate ops.Operator code
* ops.binop runs
    * converting any raw numbers to Datum.NUMBER data with zero uncertainty.
    * Each possible triple (operator, leftdatum, rightdatum) of operator and Datum types
      will have a "binop semantics Datum wrapper" method registered for
      it by ops.initOps. For example, (multiplication, Datum.IMG, Datum.NUMBER) will
      call ops.imageNumberBinop with the lambda `lambda x,y: x*y` where the latter will take
      and return Value.
    * ops.binop calls the binop semantics method for the two Datum types
* For pairings of numbers and/or images, The binop semantics Datum wrapper converts any image data into a Value after performing
subimage extraction, then calls the provided lambda. This calls the appropriate
dunder method on the two Values. In fact, we could replace `lambda x,y: x*y` with
`Value.__mul__` etc., but it's much clearer this way.
    * see above for details of this.
* In imageNumberBinop (or equivalent) the returned array Value will be stitched back into the
left-hand image using `ImageCube.modifyWithSub`, and that new image will be returned wrapped
in a Datum. If the semantic wrapper was numberBinop, so that a number is
returned, we just wrap that in a Datum.

For other types - not Datum.NUMBER or Datum.IMG - other semantics methods will have been written. For example,
the ROI types have binary operators which construct ROIBinop objects using dunder methods:
```
    def regROIBinopSemantics(op, fn):
        """Used to register binops for ROIs, which support a subset of ops."""
        registerBinopSemantics(op, Datum.ROI, Datum.ROI, lambda dx, dy: ROIBinop(dx, dy, fn))

    regROIBinopSemantics(Operator.ADD, lambda x, y: x + y)
    regROIBinopSemantics(Operator.SUB, lambda x, y: x - y)
    regROIBinopSemantics(Operator.MUL, lambda x, y: x * y)
    regROIBinopSemantics(Operator.DIV, lambda x, y: x / y)
    regROIBinopSemantics(Operator.POW, lambda x, y: x ** y)
```


## Binary and unary operations in an *expr* node

* pcot.expressions.parse.InstOp runs, popping two Datum objects and calling a callback function
stored in binopRegistry.
This callback will have been registered by Parser.registerBinop, and is simply a lambda
calling pcot.expressions.ops.binop with an Operator code for the operator, e.g.
    * `p.registerBinop('*', 20, lambda a, b: binop(Operator.MUL, a, b))` (20 is the precedence)
* The callback will call ops.binop, which is step 3 in the preceding
section.

Again, unary operations are very similar but rather simpler.

## functions of *Value* objects

Value generally has a method for each supported function. For example, the `tan` method
will perform the trigonometric `tan` with uncertainty, returning a new Value. This is rarely
called directly - instead, we generally work with Datum objects.

## datumfuncs: functions of *Datum* objects

These are registered with the `@datumfunc` operator (see [the plugins documentation](plugins.md))
which can be found in pcot.expressions.register.
This registers two separate wrappers: the expression wrapper, used when the function is called
from an *expr* node; and the Python function wrapper, called when the function is called
from inside Python.

They can take any number of arguments, but they must be either Datum objects or numeric.

### Datumfuncs called from Python

The `@datumfunc` decorator will have wrapped the function in the Python decorator, so that
subsequent calls from Python will go through the wrapper. This wrapper will

* set default values for missing arguments (which must be string or numeric)
* convert numeric and string arguments to Datum objects
* call the original function and return the result (which must be Datum)

### Datumfuncs called from *expr* nodes

The `@datumfunc` decorator also wraps the function in another wrapper - the exprwrapper - and
registers the wrapped function with the expression parser. The wrapper itself is simpler than
the Python wrapper because it can make use of facilities in the parser to convert values and
check for errors. When data reaches the exprwrapper, we already know that the arguments are
all Datum objects.

### Datumfuncs of single numeric/scalar arguments

Functions of a single numeric or image Datum are sometimes written using an "inner wrapper", which will
turn imagecubes and numbers into Value objects in a similar way to how the semantic binop
wrappers work for operations. It will also wrap the resulting Value in a Datum.
An example is `pcot.datumfuncs.func_wrapper`. Here is the datumfunc `sin` in full:
```python
@datumfunc
def sin(a):
    """
    Calculate sine of an angle in radians
    @param a:img,number:the angle (or image in which each pixel is a single angle)
    """
    return func_wrapper(lambda xx: xx.sin(), a)
```
We don't need worry about whether the argument is an image or a scalar, because the func_wrapper
will deal with it. However, func_wrapper can only deal with images and scalars.

### The stats wrapper

Another datumfunc inner wrapper which can be used is stats_wrapper. This wraps a function
which takes a (nominal,uncertainty,dq) tuple and returns another tuple of the same type.
It does the following:

* If provided with a numeric value, calls the wrapped function and creates a Value from the
returned data.
* If provided with an ImageCube, gets the subimage, splits it into bands, and calls the
wrapped function on the non-BAD values in each band. The results for each band - assumed to be
scalar - are converted into a vector Value with one value for each band.

This lets us write the `mean` like this:
```
@datumfunc
def mean(val):
    return stats_wrapper(val,
        lambda n, u, d: (np.mean(n), pooled_sd(n, u), pcot.dq.NONE))
```
and it will work on scalar Values, vector Values and images - in the latter case, producing a vector
Value.
