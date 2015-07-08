#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
@file   SurfaceGeneration.py

@author Till Junge <till.junge@kit.edu>

@date   18 Jun 2015

@brief  Helper functions for the generation of random fractal surfaces

@section LICENCE

 Copyright (C) 2015 Till Junge

PyPyContact is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License as
published by the Free Software Foundation, either version 3, or (at
your option) any later version.

PyPyContact is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
General Public License for more details.

You should have received a copy of the GNU General Public License
along with GNU Emacs; see the file COPYING. If not, write to the
Free Software Foundation, Inc., 59 Temple Place - Suite 330,
Boston, MA 02111-1307, USA.
"""

import numpy as np
import scipy.stats as stats
from ..Surface import NumpySurface
from . import compute_wavevectors, ifftn

class RandomSurfaceExact(object):
    Error = Exception
    def __init__(self, resolution, size, hurst, h_rms,
                 seed=None, lambda_max=None):
        """
        Generates a surface with an exact power spectrum (deterministic
        amplitude)
        Keyword Arguments:
        resolution -- Tuple containing number of points in spatial directions.
                      The length of the tuple determines the spatial dimension
                      of the problem (for the time being, only 1D or square 2D)
        size       -- domain size. For multidimensional problems,
                      a tuple can be provided to specify the lenths per
                      dimension. If the tuple has less entries than dimensions,
                      the last value in repeated.
        hurst      -- Hurst exponent
        h_rms      -- root mean square asperity height
        seed       -- (default hash(None)) for repeatability, the random number
                      generator is seeded previous to outputting the generated
                      surface
        lambda_max -- (default None) max wavelength to consider when scaling
                      power spectral density
        """
        if seed is not None:
            np.random.seed(hash(seed))
        if not hasattr(resolution, "__iter__"):
            resolution = (resolution, )
        if not hasattr(size, "__iter__"):
            size = (size, )

        self.dim = len(resolution)
        if self.dim not in (1, 2):
            raise self.Error(
                ("Dimension of this problem is {}. Only 1 and 2-dimensional "
                 "problems are supported").format(self.dim))
        self.resolution = resolution
        tmpsize = list()
        for i in range(self.dim):
            tmpsize.append(size[min(i, len(size)-1)])
        self.size = tuple(tmpsize)

        if self.dim == 2 and self.resolution[0] != self.resolution[1]:
            raise self.Error(
                ("Two-dimensional domains need to be square for the time being"
                 ". You specified a resolution of {}").format(self.resolution))
        if self.dim == 2 and self.size[0] != self.size[1]:
            raise self.Error(
                ("Two-dimensional domains need to be square for the time being"
                 ". You specified a size of {}").format(self.size))
        self.hurst = hurst

        self.h_rms = h_rms
        if lambda_max is not None:
            self.q_min = 2*np.pi/lambda_max
        else:
            self.q_min = 2*np.pi/self.size[0]


        self.prefactor = self.compute_prefactor()

        self.q = compute_wavevectors(self.resolution, self.size, self.dim)
        self.coeffs = self.generate_phases()
        self.generate_amplitudes()
        self.distribution = self.amplitude_distribution()
    def get_negative_frequency_iterator(self):
        def it():
            for i in range(self.resolution[0]):
                for j in range(self.resolution[1]//2+1):
                    yield (i,j), (-i,-j)
        return it()

    def amplitude_distribution(self):
        """
        returns a multiplicative factor to apply to the fourier coeffs before
        computing the inverse transform (trivial in this case, since there's no
        stochastic distro in this case)
        """
        return 1.

    def compute_prefactor(self):
        """
        computes the proportionality factor that determines the root mean
        square height assuming that the largest wave length is the full
        domain. This is described for the square of the factor on p R7
        """
        q_max = np.pi*self.resolution[0]/self.size[0]
        area = np.prod(self.size)
        return 2*self.h_rms/np.sqrt(self.q_min**(-2*self.hurst)-q_max**(-2*self.hurst))*np.sqrt(self.hurst*np.pi*area)


    def generate_phases(self):
        """
        generates appropriate random phases (φ(-q) = -φ(q))
        """
        rand_phase = np.random.rand(*self.resolution)*2*np.pi
        coeffs = np.exp(1j*rand_phase)
        for pos_it, neg_it in self.get_negative_frequency_iterator():
            if pos_it != (0, 0):
                coeffs[neg_it] = coeffs[pos_it].conj()
        if (self.resolution[0]%2 == 0):
            r2= self.resolution[0]/2
            coeffs[r2, 0] = coeffs[r2, r2] = coeffs[0, r2] = 1
        return coeffs

    def generate_amplitudes(self):
        q2 = self.q[0].reshape(-1, 1)**2 + self.q[1]**2
        q2[0, 0] = 1 # to avoid div by zeros, needs to be fixed after
        # self.coeffs *= (q2)**(-(1+self.hurst)/2)*2*self.h_rms*self.q_min**self.hurst*np.sqrt(self.hurst*np.pi)/self.size[0]
        self.coeffs *= (q2)**(-(1+self.hurst)/2)*self.prefactor
        self.coeffs[0, 0] = 0 # et voilà
        ## print("amplitudes:")
        ## print(abs(self.coeffs))
        ## print("|q|")
        ## print(np.sqrt(q2))
        ## print()

    def get_surface(self, lambda_max=None, lambda_min=None, roll_off = 1):
        """
        Computes and returs a NumpySurface object with the specified properties.
        This follows appendices A and B of Persson et al. (2005)

        Persson et al., On the nature of surface roughness with application to
        contact mechanics, sealing, rubber friction and adhesion, J. Phys.:
        Condens. Matter 17 (2005) R1-R62, http://arxiv.org/abs/cond-mat/0502419

        Keyword Arguments:
        lambda_max -- (default None) specifies a cutoff value for the longest
                      wavelength. By default, this is the domain size in the
                      smallest dimension
        lambda_min -- (default None) specifies a cutoff value for the shortest
                      wavelength. by default this is determined by Shannon's
                      Theorem.
        """
        active_coeffs = self.coeffs.copy()
        q_square = self.q[0].reshape(-1, 1)**2 + self.q[1]**2
        if lambda_max is not None:
            q2_min = (2*np.pi/lambda_max)**2
            ampli_max = (self.prefactor*2*np.pi/self.size[0] *
                         q2_min**((-1-self.hurst)/2))
            sl = q_square < q2_min
            ampli = abs(active_coeffs[sl])
            ampli[0] = 1
            active_coeffs[sl] *= roll_off*ampli_max/ampli
        if lambda_min is not None:
            q2_max = (2*np.pi/lambda_min)**2
            active_coeffs[q_square > q2_max] = 0
        active_coeffs *= self.distribution
        area = np.prod(self.size)
        profile = ifftn(active_coeffs, area)
        self.active_coeffs = active_coeffs
        return NumpySurface(profile, self.size)

class RandomSurfaceGaussian(RandomSurfaceExact):
    def __init__(self, resolution, size, hurst, h_rms, seed=None,
                 lambda_max=None):
        """
        Generates a surface with an Gaussian amplitude distribution
        Keyword Arguments:
        resolution -- Tuple containing number of points in spatial directions.
                      The length of the tuple determines the spatial dimension
                      of the problem (for the time being, only 1D or square 2D)
        size       -- domain size. For multidimensional problems,
                      a tuple can be provided to specify the lenths per
                      dimension. If the tuple has less entries than dimensions,
                      the last value in repeated.
        hurst      -- Hurst exponent
        h_rms      -- root mean square asperity height
        seed       -- (default hash(None)) for repeatability, the random number
                      generator is seeded previous to outputting the generated
                      surface
        """
        super().__init__(resolution, size, hurst, h_rms, seed, lambda_max)

    def amplitude_distribution(self):
        """
        updates the amplitudes to be a Gaussian distribution around B(q) from
        Appendix B.
        """
        distr =  stats.norm.rvs(size=self.coeffs.shape)
        for pos_it, neg_it in self.get_negative_frequency_iterator():
                distr[neg_it] = distr[pos_it]
        return distr
