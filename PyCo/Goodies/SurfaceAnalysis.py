#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
@file   SurfaceAnalysis.py

@author Till Junge <till.junge@kit.edu>

@date   25 Jun 2015

@brief  Provides a tools for the analysis of surface power spectra

@section LICENCE

 Copyright (C) 2015 Till Junge

PyCo is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License as
published by the Free Software Foundation, either version 3, or (at
your option) any later version.

PyCo is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
General Public License for more details.

You should have received a copy of the GNU General Public License
along with GNU Emacs; see the file COPYING. If not, write to the
Free Software Foundation, Inc., 59 Temple Place - Suite 330,
Boston, MA 02111-1307, USA.
"""

from __future__ import absolute_import, division, print_function
from math import pi

import numpy as np
import scipy
from scipy.signal import get_window
import matplotlib.pyplot as plt

from ..Tools.common import compute_wavevectors, fftn, get_q_from_lambda
from ..Surface import NumpySurface


class CharacterisePeriodicSurface(object):
    """
    Simple inverse FFT analysis without window. Do not use for measured surfs
    """
    eval_at_init = True

    def __init__(self, surface, one_dimensional=False):
        """
        Keyword Arguments:
        surface -- Instance of PyCo.Surface or subclass with specified
                   size
        one_dimensional -- (default False). if True, evaluation of 1D (line-
                           scan) power spectrum is emulated
        """
        # pylint: disable=invalid-name
        self.surface = surface
        if self.surface.size is None:
            raise Exception("Surface size has to be known (and specified)!")
        if self.surface.dim != 2:
            raise Exception("Only 2D surfaces, for the time being")
        if self.surface.size[0] != self.surface.size[1]:
            raise Exception("Only square surfaces, for the time being")
        if self.surface.resolution[0] != self.surface.resolution[1]:
            raise Exception("Only square surfaces, for the time being")

        self.window = 1
        if self.eval_at_init:
            if one_dimensional:
                self.C, self.q = self.eval_1D()
            else:
                self.C, self.q = self.eval()
            self.size = self.C.size

    def eval(self):
        """
        Generates the phases and amplitudes, readies the metasurface to
        generate Surface objects
        """
        res, size = self.surface.resolution, self.surface.size
        # equivalent lattice constant**2
        area = np.prod(size)
        h_a = fftn(self.surface.profile()*self.window, area)
        C_q = 1/area*(np.conj(h_a)*h_a).real

        q_vecs = compute_wavevectors(res, size, self.surface.dim)
        q_norm = np.sqrt((q_vecs[0]**2).reshape((-1, 1))+q_vecs[1]**2)
        order = np.argsort(q_norm, axis=None)
        # The first entry (for |q| = 0) is rejected, since it's 0 by construct
        return C_q.flatten()[order][1:], q_norm.flatten()[order][1:]

    def eval_1D(self):  # pylint: disable=invalid-name
        """
        Generates the phases and amplitudes, readies the metasurface to
        generate Surface objects
        """
        res, size = self.surface.resolution, self.surface.size
        # equivalent lattice constant**2

        tmp = np.fft.fft(self.surface.profile()*self.window, axis=0)
        D_q_x = np.conj(tmp)*tmp
        D_q = np.mean(D_q_x, axis=1).real

        q_x = abs(compute_wavevectors(res, size, self.surface.dim)[0])
        print("q_x = {}".format(q_x))
        order = np.argsort(q_x, axis=None)
        print("order = {}".format(order))
        # The first entry (for |q| = 0) is rejected, since it's 0 by construct
        return D_q.flatten()[order][1:], q_x.flatten()[order][1:]

    def estimate_hurst(self, lambda_min=0, lambda_max=float('inf'),
                       full_output=False):
        """
        Naive way of estimating hurst exponent. biased towards short wave
        lengths, here only for legacy purposes
        """
        q_min, q_max = get_q_from_lambda(lambda_min, lambda_max)
        q_max = min(q_max, self.q_shannon)
        sl = np.logical_and(self.q < q_max, self.q > q_min)
        weights = np.sqrt(1/self.q[sl]/((1/self.q[sl]).sum()))
        # Note the weird definition of the weights here. this is due to
        # numpy's polyfit interface. Since I suspect that numpy will change
        # this, i avoid using polyfit
        # exponent, offset = np.polyfit(np.log(self.q[sl]),
        #                               np.log(self.C[sl]),
        #                               1,
        #                               w=np.sqrt(1/self.q[sl]))

        # and do it 'by hand'
        # pylint: disable=invalid-name
        A = np.matrix(np.vstack((np.log(self.q[sl])*weights, weights))).T
        exponent, offset = np.linalg.lstsq(A, np.log(self.C[sl])*weights)[0]
        C0 = np.exp(offset)
        Hurst = -(exponent+2)/2
        if full_output:
            return Hurst, C0
        else:
            return Hurst

    def estimate_hurst_bad(self, H_guess=1., C0_guess=None,
                           lambda_min=0, lambda_max=float('inf'),
                           full_output=False, tol=1e-9, factor=1):
        """ When estimating Hurst for  more-than-one-dimensional surfs, we need
        to scale. E.g, 2d
        C(q) = C_0*q^(-2-2H)
        H, C_0 = argmin sum_i[|C(q_i)-self.C|^2/q_i]
        """
        # pylint: disable=invalid-name
        q_min, q_max = get_q_from_lambda(lambda_min, lambda_max)
        q_max = max(q_max, self.q_shannon)
        sl = np.logical_and(self.q < q_max, self.q > q_min)
        # normalising_factor
        k_norm = factor/self.C[sl].sum()

        def objective(X):
            " fun to minimize"
            H, C0 = X
            return k_norm * ((self.C[sl] - C0*self.q[sl]**(-2-H*2))**2 /
                             self.q[sl]**(self.surface.dim-1)).sum()

        # def jacobian(X):
        #     " jac of objective"
        #     H, C0 = X
        #     sim = self.q[sl]**(-2-H*2)
        #     bracket = (self.C[sl] - C0*sim)
        #     denom = self.q[sl]**(self.surface.dim-1)
        #     return np.array([(4*C0 * sim * bracket * np.log(self.q[sl]) /
        #                       denom).sum(),
        #                      (-2*sim*bracket/denom).sum()])*k_norm
        H0 = H_guess
        if C0_guess is None:
            C0 = (self.C[sl]/self.q[sl]**(-2-H0*2)).mean()
        else:
            C0 = C0_guess
        res = scipy.optimize.minimize(objective, [H0, C0], tol=tol)
        #                             , jac=jacobian)
        if not res.success:
            raise Exception(
                ("Estimation of Hurst exponent did not succeed. Optimisation "
                 "result is :\n{}").format(res))
        Hurst, prefactor = res.x
        if full_output:
            return Hurst, prefactor, res
        else:
            return Hurst

    def estimate_hurst_from_mean(self, lambda_min=0, lambda_max=float('inf'),
                                 full_output=False):
        """
        Naive way of estimating hurst exponent. biased towards short wave
        lengths, here only for legacy purposes
        """
        # pylint: disable=invalid-name
        lambda_min = max(lambda_min, self.lambda_shannon)

        C_m, dummy, q_m = self.grouped_stats(100)
        q_min, q_max = get_q_from_lambda(lambda_min, lambda_max)
        sl = np.logical_and(q_m < q_max, q_m > q_min)
        A = np.ones((sl.sum(), 2))
        A[:, 0] = np.log(q_m[sl])
        exponent, offset = np.linalg.lstsq(A, np.log(C_m[sl]))[0]
        C0 = np.exp(offset)
        Hurst = -(exponent+2)/2
        if full_output:
            return Hurst, C0
        else:
            return Hurst

    def estimate_hurst_alt(self, H_bracket=(0., 2.),
                           lambda_min=0, lambda_max=float('inf'),
                           full_output=False, tol=1e-9):
        """ When estimating Hurst for  more-than-one-dimensional surfs, we need
        to scale. E.g, 2d
        C(q) = C_0*q^(-2-2H)
        H, C_0 = argmin sum_i[|C(q_i)-self.C|^2/q_i]
        """
        # pylint: disable=invalid-name
        q_min, q_max = get_q_from_lambda(lambda_min, lambda_max)
        sl = np.logical_and(self.q < q_max, self.q > q_min)

        q = self.q[sl]
        C = self.C[sl]
        factor = 1.  # /(C**2/q).sum()

        # The unique root of the gradient of the objective in C0 can be
        # explicitly expressed
        def C0_of_H(H):  # pylint: disable=missing-docstring
            return ((q**(-3-2*H) * C).sum() /
                    (q**(-5-4*H)).sum())

        # this is the gradient of the objective in H
        def grad_in_H(H):  # pylint: disable=missing-docstring
            C0 = C0_of_H(H)
            return ((4*q**(-4*H) *
                     (C*q**(2*H+2) -
                      C0)*np.log(q)*C0/q**5).sum())*factor

        def obj(H):  # pylint: disable=missing-docstring
            C0 = C0_of_H(H)
            return (((C-C0*q**(-2-2*H))**2/q).sum())*factor

        h_s = np.linspace(H_bracket[0], H_bracket[1], 51)
        o_s = np.zeros_like(h_s)
        g_s = np.zeros_like(h_s)
        for i, h in enumerate(h_s):
            o_s[i] = obj(h)
            g_s[i] = grad_in_H(h)

        res = scipy.optimize.fminbound(
            obj, 0, 2, xtol=tol, full_output=True)  # y, jac=grad_in_H)
        H_opt, dummy_obj_opt, err, dummy_nfeq = res
        if not err == 0:
            raise Exception(
                ("Estimation of Hurst exponent did not succeed. Optimisation "
                 "result is :\n{}").format(res))
        Hurst = H_opt

        fig = plt.figure()
        ax = fig.add_subplot(211)
        ax.grid(True)
        ax.set_xlim(H_bracket)
        ax.plot(h_s, o_s)
        ax.scatter(Hurst, obj(Hurst), marker='x')
        ax = fig.add_subplot(212)
        ax.plot(h_s, g_s)
        ax.grid(True)
        ax.set_xlim(H_bracket)
        ax.scatter(Hurst, grad_in_H(Hurst), marker='x')

        if full_output:
            prefactor = C0_of_H(Hurst)
            return Hurst, prefactor, res
        else:
            return Hurst

    def compute_rms_height(self):  # pylint: disable=missing-docstring
        return self.surface.compute_rms_height()

    def compute_rms_slope(self):  # pylint: disable=missing-docstring
        return self.surface.compute_rms_slope()

    def compute_rms_height_q_space(self):  # pylint: disable=missing-docstring
        tmp_surf = NumpySurface(self.surface.profile*self.window,
                                size=self.surface.size)
        return tmp_surf.compute_rms_height_q_space()

    def compute_rms_slope_q_space(self):  # pylint: disable=missing-docstring
        tmp_surf = NumpySurface(self.surface.profile()*self.window,
                                size=self.surface.size)
        return tmp_surf.compute_rms_slope_q_space()

    def grouped_stats(self, nb_groups, percentiles=(5, 95), filter_nan=True):
        """
        Make nb_groups groups of the ordered C-q dataset and compute their
        means standard errors for plots with errorbars
        Keyword Arguments:
        nb_groups --
        """
        boundaries = np.logspace(np.log10(self.q[0]),
                                 np.log10(self.q[-1]), nb_groups+1)
        C_g = np.zeros(nb_groups)
        C_g_std = np.zeros((len(percentiles), nb_groups))
        q_g = np.zeros(nb_groups)

        for i in range(nb_groups):
            bottom = boundaries[i]
            top = boundaries[i+1]
            sl = np.logical_and(bottom <= self.q, self.q <= top)
            if sl.sum():
                C_sample = self.C[sl]  # pylint: disable=invalid-name
                q_sample = self.q[sl]

                C_g[i] = C_sample.mean()
                C_g_std[:, i] = abs(
                    np.percentile(C_sample, percentiles)-C_g[i])
                q_g[i] = q_sample.mean()
            else:
                C_g[i] = float('nan')
                C_g_std[:, i] = float('nan')
                q_g[i] = float('nan')

            bottom = top

        if filter_nan:
            sl = np.isfinite(q_g)
            return C_g[sl], C_g_std[:, sl], q_g[sl]
        return C_g, C_g_std, q_g

    @property
    def lambda_shannon(self):
        " wavelength of shannon limit"
        return 2*self.surface.size[0]/self.surface.resolution[0]

    @property
    def q_shannon(self):
        " angular freq of shannon limit"
        return 2*np.pi/self.lambda_shannon

    def simple_spectrum_plot(self, title=None, q_minmax=(0, float('inf')),
                             y_min=None, n_bins=100, ax=None, color='b'):
        " Convenience function to plot power spectra with informative labels"
        line_width = 3
        q_sh = self.q_shannon

        def corrector(q):  # pylint: disable=invalid-name,missing-docstring
            if q == 0:
                return float('inf')
            elif q == float('inf'):
                q = q_sh
            return 2*np.pi/q
        lam_max, lam_min = (corrector(q) for q in q_minmax)
        try:
            q_minmax = tuple((2*np.pi/l for l in (lam_max, lam_min)))
        except TypeError as err:
            raise TypeError(
                "{}: lam_max = {}, lam_min = {}, q_minmax = {}".format(
                    err, lam_max, lam_min, q_minmax))
        Hurst, C0 = self.estimate_hurst_from_mean(lambda_min=lam_min,
                                                  lambda_max=lam_max,
                                                  full_output=True)
        if ax is None:
            fig = plt.figure()
            ax = fig.add_subplot(111)
            ax.grid(True)
        else:
            fig = None
        mean, err, q_g = self.grouped_stats(n_bins)
        fit_q = q_g[np.logical_and(q_g < q_minmax[1], q_g > q_minmax[0])]
        ax.errorbar(q_g, mean, yerr=err, color=color)
        ax.set_title(title)
        ax.loglog(fit_q, C0*fit_q**(-2-2*Hurst), color='r', lw=line_width,
                  label=(r"$H = {:.3f}$, $C_0 = {:.3e}$".format(Hurst, C0) +
                         r""))
        ax.set_xlabel(r"$\left|q\right|$ in [rad/m]")
        ax.set_ylabel(r"$C(\left|q\right|)$ in [$\mathrm{m}^4$]")
        ax.set_yscale('log')
        ax.set_xscale('log')
        ylims = ax.get_ylim()
        ax.plot((q_sh, q_sh), ylims, color='k',
                label=r'$\lambda_\mathrm{Shannon}$')
        if y_min is not None:
            ax.set_ylim(bottom=y_min)
        if fig is not None:
            ax.legend(loc='best')
            fig.subplots_adjust(left=.19, bottom=.16, top=.85)
        return fig, ax


class CharacteriseSurface(CharacterisePeriodicSurface):
    """
    inverse FFT analysis with window. For analysis of measured surfaces
    """
    eval_at_init = False

    def __init__(self, surface, window_type='hanning', window_params=None):
        """
        Keyword Arguments:
        surface       -- Instance of PyCo.Surface or subclass with
                         specified size
        window_type   -- (default 'hanning') numpy windowing function name
        window_params -- (default dict())
        """
        super().__init__(surface)
        if window_params is None:
            window_params = dict()
        self.window = self.get_window(window_type, window_params)
        self.C, self.q = self.eval()
        self.size = self.C.size

    def get_window(self, window_type, window_params):
        " return an evaluated window as an np.array"
        if window_type == 'hanning':
            window = 2*np.hanning(self.surface.resolution[0])
        elif window_type == 'kaiser':
            window = np.kaiser(self.surface.resolution[0], **window_params)
        else:
            raise Exception("Window type '{}' not known.".format(window_type))
        window = window.reshape((-1, 1))*window
        return window


def radial_average(C_xy, rmax, nbins, size=None):
    """
    Compute radial average of quantities reported on a 2D grid.

    Parameters
    ----------
    C_xy : array_like
        2D-array of values to be averaged.
    rmax : float
        Maximum radius.
    nbins : int
        Number of bins for averaging.
    size : (float, float), optional
        Physical size of the 2D grid. (Default: Size is equal to number of grid
        points.)

    Returns
    -------
    r : array
        Array of radial grid points.
    n : array
        Number of data points per radial grid.
    C_r : array
        Averaged values.
    """
    # pylint: disable=invalid-name
    nx, ny = C_xy.shape
    sx = sy = 1.
    x = np.arange(nx)
    x = np.where(x > nx//2, nx-x, x)
    y = np.arange(ny)
    y = np.where(y > ny//2, ny-y, y)

    rmin = 0.0

    if size is not None:
        sx, sy = size
        x = 2*pi*x/sx
        y = 2*pi*y/sy
        rmin = min(2*pi/sx, 2*pi/sy)
    dr_xy = np.sqrt((x**2).reshape(-1, 1) + (y**2).reshape(1, -1))

    # Quadratic -> similar statistics for each data point
    # dr_r        = np.sqrt( np.linspace(0, rmax**2, nbins) )

    # Power law -> equally spaced on a log-log plot
    dr_r = rmax**np.linspace(np.log(rmin)/np.log(rmax), 1.0, nbins)

    dr_max = np.max(dr_xy)
    # Keep dr_max sorted
    if dr_max > dr_r[-1]:
        dr_r = np.append(dr_r, [dr_max+0.1])
    else:
        dr_r = np.append(dr_r, [dr_r[-1]+0.1])

    # Linear interpolation
    dr_xy = np.ravel(dr_xy)
    C_xy = np.ravel(C_xy)
    i_xy = np.searchsorted(dr_r, dr_xy)

    n_r = np.bincount(i_xy, minlength=len(dr_r))
    C_r = np.bincount(i_xy, weights=C_xy, minlength=len(dr_r))

    C_r /= np.where(n_r == 0, np.ones_like(n_r), n_r)

    return np.append([0.0], dr_r), n_r, C_r


def power_spectrum_1D(surface_xy,  # pylint: disable=invalid-name
                      size=None, window=None, fold=True):
    """
    Compute power spectrum from 1D FFT.

    Parameters
    ----------
    surface_xy : array_like
        2D-array of surface topography
    size : (float, float), optional
        Physical size of the 2D grid. (Default: Size is equal to number of grid
        points.)
    window : str, optional
        Window for eliminating edge effect. See scipy.signal.get_window.
        (Default: None)

    Returns
    -------
    q : array_like
        Reciprocal space vectors.
    C_all : array_like
        Power spectrum. (Units: length**3)
    """
    # pylint: disable=invalid-name
    nx, dummy_ny = surface_xy.shape
    if size is not None:
        sx, dummy_sy = size
    else:
        try:
            sx, dummy_sy = surface_xy.size
        except surface_xy.Error:
            sx, dummy_sy = surface_xy.shape

    # Construct and apply window
    if window is not None:
        win = get_window(window, nx)
        # Normalize window
        win /= win.mean()
        surface_xy = win.reshape(-1, 1)*surface_xy[:, :]

    # Pixel size
    len0 = sx/nx

    # Compute FFT and normalize
    surface_qy = len0*np.fft.fft(surface_xy[:, :], axis=0)
    dq = 2*pi/sx
    q = dq*np.arange(nx//2)

    # This is the raw power spectral density
    C_raw = (abs(surface_qy)**2)/sx

    # Fold +q and -q branches. Note: Entry q=0 appears just once, hence exclude
    # from average!
    if fold:
        C_all = C_raw[:nx//2, :]
        C_all[1:nx//2, :] += C_raw[nx-1:(nx+1)//2:-1, :]
        C_all /= 2
    
        return q, C_all.mean(axis=1)
    else:
        return np.roll(np.append(np.append(q, [2*pi*(nx//2)/sx]), -q[:0:-1]), nx//2), \
               np.roll(C_raw.mean(axis=1), nx//2)


def power_spectrum_2D(surface_xy, nbins=100,  # pylint: disable=invalid-name
                      size=None, window=None, exponent=1/2):
    """
    Compute power spectrum from 2D FFT and radial average.

    Parameters
    ----------
    surface_xy : array_like
        2D-array of surface topography
    nbins : int
        Number of bins for radial average.
    size : (float, float), optional
        Physical size of the 2D grid. (Default: Size is equal to number of grid
        points.)
    window : str, optional
        Window for eliminating edge effect. See scipy.signal.get_window.
        (Default: None)
    exponent : float, optional
        Exponent :math:`\alpha` for constructing 2D window :math:`w_{2D}` from
        1D window :math:`w_{1D}`.

        .. math:: w_{2D}(x,y) = (w_{1D}(x) w_{1D}(y))^\alpha

    Returns
    -------
    q : array_like
        Reciprocal space vectors.
    C_all : array_like
        Power spectrum. (Units: length**4)
    """
    nx, ny = surface_xy.shape
    if size is not None:
        sx, sy = size
    else:
        try:
            sx, sy = surface_xy.size
        except surface_xy.Error:
            sx, sy = surface_xy.shape

    # Construct and apply window
    if window is not None:
        win = np.outer(get_window(window, nx),
                       get_window(window, ny))**exponent
        # Normalize window
        win /= win.mean()
        surface_xy = win*surface_xy[:, :]

    # Pixel size
    area0 = (sx/nx)*(sy/ny)

    # Compute FFT and normalize
    surface_qk = area0*np.fft.fft2(surface_xy[:, :])
    C_qk = abs(surface_qk)**2/(sx*sy)  # pylint: disable=invalid-name

    if nbins is None:
        return C_qk

    # Radial average
    qedges, dummy_n, C_val = radial_average(  # pylint: disable=invalid-name
        C_qk, 2*pi*nx/(2*sx), nbins, size=(sx, sy))

    q_val = (qedges[:-1] + qedges[1:])/2
    return q_val, C_val