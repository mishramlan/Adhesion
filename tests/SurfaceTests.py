#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
@file   SurfaceTests.py

@author Till Junge <till.junge@kit.edu>

@date   27 Jan 2015

@brief  Tests surface classes

@section LICENCE

Copyright 2015-2017 Till Junge, Lars Pastewka

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

try:
    import unittest
    import numpy as np
    import numpy.matlib as mp
    from numpy.random import rand, random
    import tempfile, os
    from tempfile import TemporaryDirectory as tmp_dir
    import os

    from PyCo.Topography import (NumpyTxtSurface, NumpyAscSurface, UniformNumpyTopography, NonuniformNumpyTopography,
                                 DetrendedTopography, Sphere, ScaledTopography, rms_height, rms_slope, shift_and_tilt,
                                 read, read_asc, read_di, read_h5, read_hgt, read_ibw, read_mat, read_opd, read_x3p,
                                 read_xyz)
    from PyCo.Topography.FromFile import detect_format, get_unit_conversion_factor
    from PyCo.Topography.Generation import RandomSurfaceGaussian

except ImportError as err:
    import sys
    print(err)
    sys.exit(-1)


class NumpyTxtSurfaceTest(unittest.TestCase):
    def setUp(self):
        pass
    def test_saving_loading_and_sphere(self):
        l = 8+4*rand()  # domain size (edge lenght of square)
        R = 17+6*rand() # sphere radius
        res = 2        # resolution
        x_c = l*rand()  # coordinates of center
        y_c = l*rand()
        x = np.arange(res, dtype = float)*l/res-x_c
        y = np.arange(res, dtype = float)*l/res-y_c
        r2 = np.zeros((res, res))
        for i in range(res):
            for j in range(res):
                r2[i,j] = x[i]**2 + y[j]**2
        h = np.sqrt(R**2-r2)-R # profile of sphere

        S1 = UniformNumpyTopography(h)
        with tmp_dir() as dir:
            fname = os.path.join(dir,"surface")
            S1.save(dir+"/surface")

            S2 = NumpyTxtSurface(fname)
        S3 = Sphere(R, (res, res), (l, l), (x_c, y_c))
        self.assertTrue(np.array_equal(S1.array(), S2.array()))
        self.assertTrue(np.array_equal(S1.array(), S3.array()), )

class NumpyAscSurfaceTest(unittest.TestCase):
    def setUp(self):
        pass
    def test_example1(self):
        surf = NumpyAscSurface('tests/file_format_examples/example1.txt')
        self.assertEqual(surf.shape, (1024, 1024))
        self.assertAlmostEqual(surf.size[0], 2000)
        self.assertAlmostEqual(surf.size[1], 2000)
        self.assertAlmostEqual(surf.rms_height(), 17.22950485567042)
        self.assertAlmostEqual(rms_slope(surf), 0.45604053876290829)
        self.assertTrue(surf.is_uniform)
        self.assertEqual(surf.unit, 'nm')
    def test_example2(self):
        surf = read_asc('tests/file_format_examples/example2.txt')
        self.assertEqual(surf.shape, (650, 650))
        self.assertAlmostEqual(surf.size[0], 0.0002404103)
        self.assertAlmostEqual(surf.size[1], 0.0002404103)
        self.assertAlmostEqual(surf.rms_height(), 2.7722350402740072e-07)
        self.assertAlmostEqual(rms_slope(surf), 0.35157901772258338)
        self.assertTrue(surf.is_uniform)
        self.assertEqual(surf.unit, 'm')
    def test_example3(self):
        surf = read_asc('tests/file_format_examples/example3.txt')
        self.assertEqual(surf.shape, (256, 256))
        self.assertAlmostEqual(surf.size[0], 10e-6)
        self.assertAlmostEqual(surf.size[1], 10e-6)
        self.assertAlmostEqual(surf.rms_height(), 3.5222918750198742e-08)
        self.assertAlmostEqual(rms_slope(surf), 0.19231536279425226)
        self.assertTrue(surf.is_uniform)
        self.assertEqual(surf.unit, 'm')
    def test_example4(self):
        surf = read_asc('tests/file_format_examples/example4.txt')
        self.assertEqual(surf.shape, (305, 75))
        self.assertAlmostEqual(surf.size[0], 0.00011280791)
        self.assertAlmostEqual(surf.size[1], 2.773965e-05)
        self.assertAlmostEqual(surf.rms_height(), 1.1745891510991089e-07)
        self.assertAlmostEqual(surf.rms_height(kind='Rq'), 1.1745891510991089e-07)
        self.assertAlmostEqual(rms_slope(surf), 0.067915823359553706)
        self.assertTrue(surf.is_uniform)
        self.assertEqual(surf.unit, 'm')

class DetrendedSurfaceTest(unittest.TestCase):
    def setUp(self):
        pass
    def test_smooth_flat(self):
        a = 1.2
        b = 2.5
        d = .2
        arr = np.arange(5)*a+d
        arr = arr + np.arange(6).reshape((-1, 1))*b
        surf = DetrendedTopography(UniformNumpyTopography(arr), detrend_mode='slope')
        self.assertTrue(surf.is_uniform)
        self.assertAlmostEqual(surf[...].mean(), 0)
        self.assertAlmostEqual(rms_slope(surf), 0)
        surf = DetrendedTopography(UniformNumpyTopography(arr), detrend_mode='height')
        self.assertTrue(surf.is_uniform)
        self.assertAlmostEqual(surf[...].mean(), 0)
        self.assertAlmostEqual(rms_slope(surf), 0)
        self.assertTrue(rms_height(surf) < rms_height(arr))
        surf2 = DetrendedTopography(UniformNumpyTopography(arr, size=(1, 1)), detrend_mode='height')
        self.assertTrue(surf2.is_uniform)
        self.assertAlmostEqual(rms_slope(surf2), 0)
        self.assertTrue(rms_height(surf2) < rms_height(arr))
        self.assertAlmostEqual(rms_height(surf), rms_height(surf2))
        x, y, z = surf2.points()
        self.assertAlmostEqual(np.mean(np.diff(x[:, 0])), surf2.size[0]/surf2.resolution[0])
        self.assertAlmostEqual(np.mean(np.diff(y[0, :])), surf2.size[1]/surf2.resolution[1])
    def test_smooth_curved(self):
        a = 1.2
        b = 2.5
        c = 0.1
        d = 0.2
        e = 0.3
        f = 5.5
        x = np.arange(5).reshape((1, -1))
        y = np.arange(6).reshape((-1, 1))
        arr = f+x*a+y*b+x*x*c+y*y*d+x*y*e
        surf = DetrendedTopography(UniformNumpyTopography(arr, size=(3., 2.5)), detrend_mode='curvature')
        self.assertTrue(surf.is_uniform)
        self.assertAlmostEqual(surf.coeffs[0], -2*b)
        self.assertAlmostEqual(surf.coeffs[1], -2*a)
        self.assertAlmostEqual(surf.coeffs[2], -4*d)
        self.assertAlmostEqual(surf.coeffs[3], -4*c)
        self.assertAlmostEqual(surf.coeffs[4], -4*e)
        self.assertAlmostEqual(surf.coeffs[5], -f)
        self.assertAlmostEqual(surf.rms_height(), 0.0)
        self.assertAlmostEqual(surf.rms_slope(), 0.0)
    def test_randomly_rough(self):
        surface = RandomSurfaceGaussian((512, 512), (1., 1.), 0.8, rms_height=1).get_surface()
        self.assertTrue(surface.is_uniform)
        cut = UniformNumpyTopography(surface[:64, :64], size=(64., 64.))
        self.assertTrue(cut.is_uniform)
        untilt1 = DetrendedTopography(cut, detrend_mode='height')
        untilt2 = DetrendedTopography(cut, detrend_mode='slope')
        self.assertTrue(untilt1.is_uniform)
        self.assertTrue(untilt2.is_uniform)
        self.assertTrue(untilt1.rms_height() < untilt2.rms_height())
        self.assertTrue(untilt1.rms_slope() > untilt2.rms_slope())
    def test_nonuniform(self):
        surf = read_xyz('tests/file_format_examples/example.asc')
        self.assertFalse(surf.is_uniform)
        surf = DetrendedTopography(surf, detrend_mode='height')
        self.assertFalse(surf.is_uniform)
    def test_uniform_linear(self):
        x = np.linspace(0, 10, 11)**2
        y = 1.8*x+1.2
        surf = DetrendedTopography(NonuniformNumpyTopography(x, y), detrend_mode='height')
        self.assertAlmostEqual(surf.mean(), 0.0)
        self.assertAlmostEqual(surf.rms_slope(), 0.0)

class DetectFormatTest(unittest.TestCase):
    def setUp(self):
        pass
    def test_detection(self):
        self.assertEqual(detect_format('tests/file_format_examples/example1.di'), 'di')
        self.assertEqual(detect_format('tests/file_format_examples/example2.di'), 'di')
        self.assertEqual(detect_format('tests/file_format_examples/example.ibw'), 'ibw')
        self.assertEqual(detect_format('tests/file_format_examples/example.opd'), 'opd')
        self.assertEqual(detect_format('tests/file_format_examples/example.x3p'), 'x3p')
        self.assertEqual(detect_format('tests/file_format_examples/example1.mat'), 'mat')
        self.assertEqual(detect_format('tests/file_format_examples/example.asc'), 'xyz')

class matSurfaceTest(unittest.TestCase):
    def setUp(self):
        pass
    def test_read(self):
        surface = read_mat('tests/file_format_examples/example1.mat')
        nx, ny = surface.shape
        self.assertEqual(nx, 2048)
        self.assertEqual(ny, 2048)
        self.assertAlmostEqual(surface.rms_height(), 1.234061e-07)
        self.assertTrue(surface.is_uniform)

class x3pSurfaceTest(unittest.TestCase):
    def setUp(self):
        pass
    def test_read(self):
        surface = read_x3p('tests/file_format_examples/example.x3p')
        nx, ny = surface.shape
        self.assertEqual(nx, 777)
        self.assertEqual(ny, 1035)
        sx, sy = surface.size
        self.assertAlmostEqual(sx, 0.00068724)
        self.assertAlmostEqual(sy, 0.00051593)
        surface = read_x3p('tests/file_format_examples/example2.x3p')
        nx, ny = surface.shape
        self.assertEqual(nx, 650)
        self.assertEqual(ny, 650)
        sx, sy = surface.size
        self.assertAlmostEqual(sx, 8.29767313942749e-05)
        self.assertAlmostEqual(sy, 0.0002044783737930349)
        self.assertTrue(surface.is_uniform)
    def test_points_for_uniform_topography(self):
        surface = read_x3p('tests/file_format_examples/example.x3p')
        x, y, z = surface.points()
        self.assertAlmostEqual(np.mean(np.diff(x[:, 0])), surface.size[0]/surface.resolution[0])
        self.assertAlmostEqual(np.mean(np.diff(y[0, :])), surface.size[1]/surface.resolution[1])

class opdSurfaceTest(unittest.TestCase):
    def setUp(self):
        pass
    def test_read(self):
        surface = read_opd('tests/file_format_examples/example.opd')
        nx, ny = surface.shape
        self.assertEqual(nx, 640)
        self.assertEqual(ny, 480)
        sx, sy = surface.size
        self.assertAlmostEqual(sx, 0.125909140)
        self.assertAlmostEqual(sy, 0.094431855)
        self.assertTrue(surface.is_uniform)

class diSurfaceTest(unittest.TestCase):
    def setUp(self):
        pass
    def test_read(self):
        # All units are nm
        for (fn, n, s, rmslist) in [
            ('example1.di', 512, 500.0, [9.9459868005603909, # Height
                                         114.01328027385664, # Height
                                         None, # Phase
                                         None]), # AmplitudeError
            ('example2.di', 512, 300.0, [24.721922008645919, # Height
                                         24.807150576054838, # Height
                                         0.13002312109876774]), # Deflection
            ('example3.di', 256, 10000.0, [226.42539668457405, # ZSensor
                                           None, # AmplitudeError
                                           None, # Phase
                                           264.00285276203158]), # Height
            ('example4.di', 512, 10000.0, [81.622909804184744, # ZSensor
                                           0.83011806260022758, # AmplitudeError
                                           None]) # Phase
            ]:
            surfaces = read_di('tests/file_format_examples/{}'.format(fn))
            if type(surfaces) is not list:
                surfaces = [surfaces]
            for surface, rms in zip(surfaces, rmslist):
                nx, ny = surface.shape
                self.assertEqual(nx, n)
                self.assertEqual(ny, n)
                sx, sy = surface.size
                if type(surface.unit) is tuple:
                    unit, dummy = surface.unit
                else:
                    unit = surface.unit
                self.assertAlmostEqual(sx*get_unit_conversion_factor(unit, 'nm'), s)
                self.assertAlmostEqual(sy*get_unit_conversion_factor(unit, 'nm'), s)
                if rms is not None:
                    self.assertAlmostEqual(surface.rms_height(), rms)
                    self.assertEqual(unit, 'nm')
                self.assertTrue(surface.is_uniform)

class ibwSurfaceTest(unittest.TestCase):
    def setUp(self):
        pass
    def test_read(self):
        surface = read_ibw('tests/file_format_examples/example.ibw')
        nx, ny = surface.shape
        self.assertEqual(nx, 512)
        self.assertEqual(ny, 512)
        sx, sy = surface.size
        self.assertAlmostEqual(sx, 5.00978e-8)
        self.assertAlmostEqual(sy, 5.00978e-8)
        self.assertEqual(surface.unit, 'm')
        self.assertTrue(surface.is_uniform)

    def test_detect_format_then_read(self):
        f = open('tests/file_format_examples/example.ibw', 'rb')
        fmt = detect_format(f)
        self.assertTrue(fmt, 'ibw')
        surface = read(f, format=fmt)
        f.close()

class hgtSurfaceTest(unittest.TestCase):
    def setUp(self):
        pass
    def test_read(self):
        surface = read_hgt('tests/file_format_examples/N46E013.hgt')
        nx, ny = surface.shape
        self.assertEqual(nx, 3601)
        self.assertEqual(ny, 3601)
        self.assertTrue(surface.is_uniform)

class h5SurfaceTest(unittest.TestCase):
    def setUp(self):
        pass
    def test_detect_format_then_read(self):
        self.assertEqual(detect_format('tests/file_format_examples/surface.2048x2048.h5'), 'h5')
    def test_read(self):
        surface = read_h5('tests/file_format_examples/surface.2048x2048.h5')
        nx, ny = surface.shape
        self.assertEqual(nx, 2048)
        self.assertEqual(ny, 2048)
        self.assertTrue(surface.is_uniform)
        self.assertEqual(surface.dim, 2)

class xyzSurfaceTest(unittest.TestCase):
    def setUp(self):
        pass
    def test_detect_format_then_read(self):
        self.assertEqual(detect_format('tests/file_format_examples/example.asc'), 'xyz')
    def test_read(self):
        surface = read_xyz('tests/file_format_examples/example.asc')
        self.assertFalse(surface.is_uniform)
        x, y = surface.points()
        self.assertGreater(len(x), 0)
        self.assertEqual(len(x), len(y))
        self.assertFalse(surface.is_uniform)
        self.assertEqual(surface.dim, 1)

class PipelineTests(unittest.TestCase):
    def test_scaled_topography(self):
        surf = read_xyz('tests/file_format_examples/example.asc')
        for fac in [1.0, 2.0, np.pi]:
            surf2 = ScaledTopography(surf, fac)
            self.assertAlmostEqual(fac*surf.rms_height(kind='Rq'), surf2.rms_height(kind='Rq'))

class IOTest(unittest.TestCase):
    def setUp(self):
        self.binary_example_file_list = [
            'tests/file_format_examples/example1.di',
            'tests/file_format_examples/example.ibw',
            'tests/file_format_examples/example1.mat',
            'tests/file_format_examples/example.opd',
            'tests/file_format_examples/example.x3p',
            'tests/file_format_examples/example2.x3p',
        ]
        self.text_example_file_list = [
            'tests/file_format_examples/example.asc',
            'tests/file_format_examples/example1.txt',
            'tests/file_format_examples/example2.txt',
            'tests/file_format_examples/example3.txt',
            'tests/file_format_examples/example4.txt',
        ]

    def test_keep_file_open(self):
        for fn in self.text_example_file_list:
            with open(fn, 'r') as f:
                s = read(f)
                self.assertFalse(f.closed, msg=fn)
        for fn in self.binary_example_file_list:
            print(fn)
            with open(fn, 'rb') as f:
                s = read(f)
                self.assertFalse(f.closed, msg=fn)