"""While this file is primarily a speed test it can also serve as a functionality "smoke test".

With TEST_UNCERTAINTIES_PACKAGE false, it tests scalar/array, array/scalar and array/array
times using random data (see below).

With that value true it does the same thing, but also times checks the results against 
the uncertainties package. This doesn't work on large arrays - uncertainties can't cope
with them.

The data is generated from a uniform distribution on the following intervals:
    data:  [1,4)
    uncertainty: [0.1,0.9)
"""    





import numpy as np
from math import sqrt
from uncertainties import ufloat,unumpy
from uncertainties.unumpy import uarray
import sys

sys.path.insert(0,"../src/pcot")
from number import *
from utils.deb import Timer

# turn this off to stop using the uncertainties package to test against - it
# doesn't work for large data.
TEST_UNCERTAINTIES_PACKAGE=True

if TEST_UNCERTAINTIES_PACKAGE:
    shape=(102,102,4)
else:
    shape=(1024,1024,11)
    


rng = np.random.default_rng()

def gendata(shape=None):
    return rng.uniform(1,4,shape)
    
def genunc(shape=None):
    return rng.uniform(0.1,0.9,shape)


def test_scalar_array_op_speed(name,f,g):
    a = gendata()
    ua = genunc()
    b = gendata(shape)
    ub = genunc(shape)
    
    x,y = 0,0
    with Timer(f"scalar/array mine {name}"):
        x = f(a,ua,b,ub)
        
    if TEST_UNCERTAINTIES_PACKAGE:
        with Timer("scalar/array unc"):
            y = g(a,ua,b,ub)
        
        e = np.max(np.abs(x-y))
        print(f"Max error for {name} = {e}")
    

def test_scalar_array_ops_speed():
    test_scalar_array_op_speed("add",
        lambda a,ua,b,ub: add_sub_unc(ua,ub),
        lambda a,ua,b,ub: unumpy.std_devs(uarray(a,ua)+uarray(b,ub))
    )
        
    test_scalar_array_op_speed("sub",
        lambda a,ua,b,ub: add_sub_unc(ua,ub),
        lambda a,ua,b,ub: unumpy.std_devs(uarray(a,ua)-uarray(b,ub))
    )
    
    test_scalar_array_op_speed("mul",
        lambda a,ua,b,ub: mul_unc(a,ua,b,ub),
        lambda a,ua,b,ub: unumpy.std_devs(uarray(a,ua)*uarray(b,ub))
    )

    test_scalar_array_op_speed("div",
        lambda a,ua,b,ub: div_unc(a,ua,b,ub),
        lambda a,ua,b,ub: unumpy.std_devs(uarray(a,ua)/uarray(b,ub))
    )
    test_scalar_array_op_speed("pow",
        lambda a,ua,b,ub: pow_unc(a,ua,b,ub),
        lambda a,ua,b,ub: unumpy.std_devs(uarray(a,ua)**uarray(b,ub))
    )




def test_array_scalar_op_speed(name,f,g):
    a = gendata(shape)
    ua = genunc(shape)
    b = gendata()
    ub = genunc()
    
    x,y = 0,0
    with Timer(f"array/scalar mine {name}"):
        x = f(a,ua,b,ub)
        
    if TEST_UNCERTAINTIES_PACKAGE:
        with Timer("array/scalar unc"):
            y = g(a,ua,b,ub)
        
        e = np.max(np.abs(x-y))
        print(f"Max error for {name} = {e}")
    

def test_array_scalar_ops_speed():
    test_array_scalar_op_speed("add",
        lambda a,ua,b,ub: add_sub_unc(ua,ub),
        lambda a,ua,b,ub: unumpy.std_devs(uarray(a,ua)+uarray(b,ub))
    )
        
    test_array_scalar_op_speed("sub",
        lambda a,ua,b,ub: add_sub_unc(ua,ub),
        lambda a,ua,b,ub: unumpy.std_devs(uarray(a,ua)-uarray(b,ub))
    )
    
    test_array_scalar_op_speed("mul",
        lambda a,ua,b,ub: mul_unc(a,ua,b,ub),
        lambda a,ua,b,ub: unumpy.std_devs(uarray(a,ua)*uarray(b,ub))
    )

    test_array_scalar_op_speed("div",
        lambda a,ua,b,ub: div_unc(a,ua,b,ub),
        lambda a,ua,b,ub: unumpy.std_devs(uarray(a,ua)/uarray(b,ub))
    )
    test_array_scalar_op_speed("pow",
        lambda a,ua,b,ub: pow_unc(a,ua,b,ub),
        lambda a,ua,b,ub: unumpy.std_devs(uarray(a,ua)**uarray(b,ub))
    )



def test_array_array_op_speed(name,f,g):
    a = gendata(shape)
    ua = genunc(shape)
    b = gendata(shape)
    ub = genunc(shape)
    
    x,y = 0,0
    with Timer(f"array/array mine {name}"):
        x = f(a,ua,b,ub)
        
    if TEST_UNCERTAINTIES_PACKAGE:
        with Timer("array/array unc"):
            y = g(a,ua,b,ub)
        
        e = np.max(np.abs(x-y))
        print(f"Max error for {name} = {e}")

    

def test_array_array_ops_speed():
    test_array_array_op_speed("add",
        lambda a,ua,b,ub: add_sub_unc(ua,ub),
        lambda a,ua,b,ub: unumpy.std_devs(uarray(a,ua)+uarray(b,ub))
    )
        
    test_array_array_op_speed("sub",
        lambda a,ua,b,ub: add_sub_unc(ua,ub),
        lambda a,ua,b,ub: unumpy.std_devs(uarray(a,ua)-uarray(b,ub))
    )
    
    test_array_array_op_speed("mul",
        lambda a,ua,b,ub: mul_unc(a,ua,b,ub),
        lambda a,ua,b,ub: unumpy.std_devs(uarray(a,ua)*uarray(b,ub))
    )

    test_array_array_op_speed("div",
        lambda a,ua,b,ub: div_unc(a,ua,b,ub),
        lambda a,ua,b,ub: unumpy.std_devs(uarray(a,ua)/uarray(b,ub))
    )
    test_array_array_op_speed("pow",
        lambda a,ua,b,ub: pow_unc(a,ua,b,ub),
        lambda a,ua,b,ub: unumpy.std_devs(uarray(a,ua)**uarray(b,ub))
    )

test_array_scalar_ops_speed()
test_scalar_array_ops_speed()
test_array_array_ops_speed()



