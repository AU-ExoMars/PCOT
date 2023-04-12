#!/usr/bin/env python3
from math import sqrt
from uncertainties import ufloat
import numpy as np

def goodman(a,ua,b,ub):
    """Derived analytically using
    https://astro.subhashbose.com/tools/error-propagation-calculator
    Weirdly, ChatGPT also gives this after a bit of poking, but cites
    Kragten."""
    
    return sqrt(((a*ub)**2 + (b*ua)**2)/(b**4))
    
def uncpackage(a,ua,b,ub):
    """This should be correct!"""
    a = ufloat(a,ua)
    b = ufloat(b,ub)
    return (a/b).std_dev

xx = np.arange(0,10,0.1)
print(xx)

for a in range(-10,10):
    for b in [x for x in range(-10,10) if x!=0]:
        print(a,b)
        for ua in xx:
            for ub in xx:
                x = goodman(a,ua,b,ub)
                z = uncpackage(a,ua,b,ub)
                if abs(x-z)>0.01:
                    print(f"{a}/{ua},{b}/{ub} =   {x},{z}")
