#!/usr/bin/env python3

"""This performs a large number of tests on different kinds of operations
to check that the results returned for uncertainties are the same
as those produced by the "uncertainties" package.

There are four sets of tests, one for each combination of scalar and
array in a binary operation. The operations tested are addition, subtraction,
multiplication, division and exponentiation.

For scalar/scalar tests, the intervals tested are [-10, 10;1) for input
values and [0,3;0.2) for input uncertainties (figures after the semicolon
are the steps).

For other tests, the values are [-3,3;1) and uncertainties are [0,2;0.2).

In the case of arrays, the array shape used is 2x3x2 and the array is filled with
the value or uncertainty under test. For values, cell (0,1,1) is doubled, so a
value of 1 reads as an array

array([[[1, 1],
        [1, 2],
        [1, 1]],

       [[1, 1],
        [1, 1],
        [1, 1]]])

while for uncertainties, (1,1,1) is tripled so a uncertainty of 0.2 becomes the array

array([[[0.2, 0.2],
        [0.2, 0.2],
        [0.2, 0.2]],

       [[0.2, 0.2],
        [0.2, 0.6],
        [0.2, 0.2]]])

This ensures we're not just testing constant arrays.

Note that some operations require special cases:

    division: zeroes are removed from the denominator (or replaced with innocuous values)
    exponentiation: odd things are done if the base is zero (zero bases aren't handled
    nicely).

The test itself iterates through all the combinations of values and uncertainties on
both sides, and prints whether any errors occur of >0.01 in size."""

    

import numpy as np
from math import sqrt
from uncertainties import ufloat,unumpy
from uncertainties.unumpy import uarray
import sys


sys.path.insert(0,"../src/pcot")
from number import *
np.seterr(all='raise')

def test_scalar_op(name,f,g):
    """Test a pair of binary functions to make sure they behave the same.
    Each function takes two scalar values, a and b, expressed as two pairs
    of (nominalvalue,uncertainty): a, ua, b, ub. The values are not packed into
    tuples. The return value is the uncertainty only."""

    uncertainties = np.arange(0,3,0.2)
    print(f"scalar {name}")
    ct=0
    bad=0
    for a in range(1,10):
        for b in range(1,10):
            for ua in uncertainties:
                for ub in uncertainties:
                    x = f(float(a),ua,float(b),ub)
                    y = g(float(a),ua,float(b),ub)
                    if abs(x-y)>0.01:
                        print(f"{a}/{ua},{b}/{ub} =   {x},{y}")
                        bad=bad+1
                    else:
                        ct=ct+1
    if bad>0:
        print(f"  {ct} ok, {bad} not ok")
    else:
        print(f"  {ct} ok")

#
# Use the above functions to test both our code and the code in the uncertainties package
# against each other.
#

def powfunc(a,ua,b,ub):
    # avoid the exceptions raised in uncertainties package
    if a==0 and b<0:
        return 0        # 0^n where n<0 gives 0 uncertainty
    else:
        return (ufloat(a,ua)**ufloat(b,ub)).std_dev

def test_scalar_ops():
    test_scalar_op("pow",
        lambda a,ua,b,ub: pow_unc(a,ua,b,ub),
        lambda a,ua,b,ub: powfunc(a,ua,b,ub)
    )
    
    test_scalar_op("mul",
        lambda a,ua,b,ub: mul_unc(a,ua,b,ub),
        lambda a,ua,b,ub: (ufloat(a,ua)*ufloat(b,ub)).std_dev
    )

    test_scalar_op("div",
        # divide by zero gives zero uncertainty.
        lambda a,ua,b,ub: 0 if b == 0 else div_unc(a,ua,b,ub),
        lambda a,ua,b,ub: 0 if b == 0 else (ufloat(a,ua)/ufloat(b,ub)).std_dev
    )
    
    test_scalar_op("add",
        lambda a,ua,b,ub: add_sub_unc(ua,ub),
        lambda a,ua,b,ub: (ufloat(a,ua)+ufloat(b,ub)).std_dev
    )
        
    test_scalar_op("sub",
        lambda a,ua,b,ub: add_sub_unc(ua,ub),
        lambda a,ua,b,ub: (ufloat(a,ua)-ufloat(b,ub)).std_dev
    )
    


#
# Now a function to test array/array ops
#

shape = (2,3,2)

def genarray(val,unc):
    a = np.full(shape,val,dtype=np.float32)
    a[0,1,1] *= 2
    ua = np.full(shape,unc,dtype=np.float32)
    ua[1,1,1] *= 3
    return a,ua
    


def test_array_array_op(name,f,g):
    uncertainties = np.arange(0,2,0.2)
    print(f"array/array {name}")
    ct=0
    bad=0
    for a in range(-3,3):
        for b in range(-3,3):
            for ua in uncertainties:            
                for ub in uncertainties:
                    #print(a,b,ua,ub)
                    op1,op1u = genarray(a,ua)
                    op2,op2u = genarray(b,ub)
                    x = f(op1,op1u,op2,op2u)
                    y = g(op1,op1u,op2,op2u)
                    # print(f"{a}/{ua},{b}/{ub}")
                    if np.any(np.abs(x-y)>0.001):
                        md = np.max(np.abs(x-y))
                        print(f"{a}/{ua},{b}/{ub} max error {md}")
                        print("mine",x)
                        print("uncpackage",y)
                        bad=bad+1
                    else:
                        ct=ct+1
    if bad>0:
        print(f"  {ct} ok, {bad} not ok")
    else:
        print(f"  {ct} ok")

# Return a version of A in which those places where A=0 and B<0 are set to 1.
# This is to remove cases which fail in the uncertainties package with exponentiation
def cln(a,b):
#    print(f"{np.isscalar(a)},{np.isscalar(b)}")
    if np.isscalar(a) and np.isscalar(b):
        if a==0 and b<0:
            return 100
        else:
            return a
    else:
        # one of them is an array at least. Turn any scalar
        # into an array
        if np.isscalar(a):
            if a!=0:
                return a    # unless A isn't zero, in which case we're fine
            a = np.full_like(b,a)
        elif np.isscalar(b):
            b = np.full_like(a,b)
            
        # b is an array. Find the parts where a==0 and b<0 and set a to 100.
        p = np.logical_and(a==0,b<0)
        r = np.copy(a)
        r[p]=100
        return r

# remove zeroes from an array, used to clean out division by zero
def remove_zeros(a):
    if np.isscalar(a):
        return 10 if a==0 else a
    else:
        arr = np.copy(a)
        a[a==0]=10
        return a

def test_array_array_ops():
    test_array_array_op("pow",
        lambda a,ua,b,ub: pow_unc(cln(a,b),ua,b,ub),
        lambda a,ua,b,ub: unumpy.std_devs(uarray(cln(a,b),ua)**uarray(b,ub))
    )

    test_array_array_op("mul",
        lambda a,ua,b,ub: mul_unc(a,ua,b,ub),
        lambda a,ua,b,ub: unumpy.std_devs(uarray(a,ua)*uarray(b,ub))
    )

    test_array_array_op("add",
        lambda a,ua,b,ub: add_sub_unc(ua,ub),
        lambda a,ua,b,ub: unumpy.std_devs(uarray(a,ua)+uarray(b,ub))
    )
        
    test_array_array_op("sub",
        lambda a,ua,b,ub: add_sub_unc(ua,ub),
        lambda a,ua,b,ub: unumpy.std_devs(uarray(a,ua)-uarray(b,ub))
    )
    
    test_array_array_op("div",
        lambda a,ua,b,ub: div_unc(a,ua,remove_zeros(b),ub),
        lambda a,ua,b,ub: unumpy.std_devs(uarray(a,ua)/uarray(remove_zeros(b),ub))
    )



#
# Scalar/array
#

def test_scalar_array_op(name,f,g):
    uncertainties = np.arange(0,2,0.2)
    print(f"scalar/array {name}")
    ct=0
    bad=0
    for a in range(-3,3):
        for b in range(-3,3):
            for ua in uncertainties:            
                for ub in uncertainties:
#                    print(a,b,ua,ub)
                    op1 = float(a)
                    op1u = float(ua)
                    op2,op2u = genarray(b,ub)
                    
                    x = f(op1,op1u,op2,op2u)
                    y = g(op1,op1u,op2,op2u)
                    if np.any(np.abs(x-y)>0.01):
                        md = np.max(np.abs(x-y))
                        print(f"{a}/{ua},{b}/{ub} - max error {md}")
                        print("mine",x)
                        print("uncpackage",y)
                        bad=bad+1
                    else:
                        ct=ct+1
    if bad>0:
        print(f"  {ct} ok, {bad} not ok")
    else:
        print(f"  {ct} ok")

def test_scalar_array_ops():
    test_scalar_array_op("add",
        lambda a,ua,b,ub: add_sub_unc(ua,ub),
        lambda a,ua,b,ub: unumpy.std_devs(uarray(a,ua)+uarray(b,ub))
    )
        
    test_scalar_array_op("sub",
        lambda a,ua,b,ub: add_sub_unc(ua,ub),
        lambda a,ua,b,ub: unumpy.std_devs(uarray(a,ua)-uarray(b,ub))
    )
    
    test_scalar_array_op("mul",
        lambda a,ua,b,ub: mul_unc(a,ua,b,ub),
        lambda a,ua,b,ub: unumpy.std_devs(uarray(a,ua)*uarray(b,ub))
    )

    test_scalar_array_op("div",
        lambda a,ua,b,ub: div_unc(a,ua,remove_zeros(b),ub),
        lambda a,ua,b,ub: unumpy.std_devs(uarray(a,ua)/uarray(remove_zeros(b),ub))
    )
    test_scalar_array_op("pow",
        lambda a,ua,b,ub: pow_unc(cln(a,b),ua,b,ub),
        lambda a,ua,b,ub: unumpy.std_devs(uarray(cln(a,b),ua)**uarray(b,ub))
    )


#
# Array/scalar
#

def test_array_scalar_op(name,f,g):
    uncertainties = np.arange(0,2,0.2)
    print(f"array/scalar {name}")
    ct=0
    bad=0
    for a in range(-3,3):
        for b in range(-3,3):
            for ua in uncertainties:            
                for ub in uncertainties:
#                    print(a,b,ua,ub)
                    op1,op1u = genarray(b,ub)
                    op2 = float(a)
                    op2u = float(ua)
                    
                    x = f(op1,op1u,op2,op2u)
                    y = g(op1,op1u,op2,op2u)
                    if np.any(np.abs(x-y)>0.01):
                        md = np.max(np.abs(x-y))
                        print(f"{a}/{ua},{b}/{ub} - max error {md}")
                        print("mine",x)
                        print("uncpackage",y)
                        bad=bad+1
                    else:
                        ct=ct+1
    if bad>0:
        print(f"  {ct} ok, {bad} not ok")
    else:
        print(f"  {ct} ok")

def test_array_scalar_ops():
    test_array_scalar_op("add",
        lambda a,ua,b,ub: add_sub_unc(ua,ub),
        lambda a,ua,b,ub: unumpy.std_devs(uarray(a,ua)+uarray(b,ub))
    )
        
    test_array_scalar_op("sub",
        lambda a,ua,b,ub: add_sub_unc(ua,ub),
        lambda a,ua,b,ub: unumpy.std_devs(uarray(a,ua)-uarray(b,ub))
    )
    
    test_array_scalar_op("mul",
        lambda a,ua,b,ub: mul_unc(a,ua,b,ub),
        lambda a,ua,b,ub: unumpy.std_devs(uarray(a,ua)*uarray(b,ub))
    )

    test_array_scalar_op("div",
        lambda a,ua,b,ub: div_unc(a,ua,remove_zeros(b),ub),
        lambda a,ua,b,ub: unumpy.std_devs(uarray(a,ua)/uarray(remove_zeros(b),ub))
    )
    test_array_scalar_op("pow",
        lambda a,ua,b,ub: pow_unc(cln(a,b),ua,b,ub),
        lambda a,ua,b,ub: unumpy.std_devs(uarray(cln(a,b),ua)**uarray(b,ub))
    )


test_scalar_ops()
test_array_array_ops()
test_scalar_array_ops()
test_array_scalar_ops()

