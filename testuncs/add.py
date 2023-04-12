#!/usr/bin/env python3
from math import sqrt
from uncertainties import ufloat
import numpy as np

def standard(a,ua,b,ub):
    """standard's thing"""
    return sqrt(ub**2 + ua**2)
    
def uncpackage(a,ua,b,ub):
    """This should be correct!"""
    a = ufloat(a,ua)
    b = ufloat(b,ub)
    return (a+b).std_dev

xx = np.arange(0,10,0.1)
print(xx)

for a in range(-10,10):
    for b in range(-10,10):
        print(a,b)
        for ua in xx:
            for ub in xx:
                x = standard(a,ua,b,ub)
                z = uncpackage(a,ua,b,ub)
                if abs(x-z)>0.01:
                    print(f"{a}/{ua},{b}/{ub} =   {x},{z}")
