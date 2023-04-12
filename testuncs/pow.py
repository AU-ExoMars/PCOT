#!/usr/bin/env python3
from math import sqrt,log
from uncertainties import ufloat
import numpy as np

def mine(a,ua,b,ub):
    a=abs(a)
    if a==0:
        if b<0:
            return 100
        elif b==1:
            return ua
        else:
            return 0
        
    x = a**(2*b-2)
    y = (a * ub * log(a))**2 + (b*ua)**2
    return sqrt(x*y)
    
    
def uncpackage(a,ua,b,ub):
    """This should be correct!"""
    if a==0 and b<0:
        return 100
    a = ufloat(a,ua)
    b = ufloat(b,ub)
    return (a**b).std_dev

xx = np.arange(0,10)
print(xx)

for a in range(-10,10):
    for b in [x for x in range(-10,10) if x!=0]:
        for ua in xx:
            for ub in xx:
                x = mine(a,ua,b,ub)
                z = uncpackage(a,ua,b,ub)
                if abs(x-z)>0.01:
                    print(f"{a}/{ua},{b}/{ub} =   mine={x:.2f},uncpack={z:.2f}")
