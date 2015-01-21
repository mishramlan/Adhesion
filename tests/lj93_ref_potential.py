#!/usr/bin/env python3

## taken as reference from pycontact (https://github.com/pastewka/pycontact)

import numpy as np
def V(x, epsilon, sigma, rc1):
    return np.where(x < rc1,
                      epsilon*(2./15*(sigma/x)**9 - (sigma/x)**3)
                    - epsilon*(2./15*(sigma/rc1)**9 - (sigma/rc1)**3),
                    np.zeros_like(x)
                    )

def dV(x, epsilon, sigma, rc1):
    return np.where(x < rc1,
                    - epsilon*(6./5*(sigma/x)**6 - 3)*(sigma/x)**3/x,
                    np.zeros_like(x)
                    )

def d2V(x, epsilon, sigma, rc1):
    return np.where(x < rc1,
                    12*epsilon*((sigma/x)**6 - 1)*(sigma/x)**3/(x*x),
                    np.zeros_like(x)
                    )
