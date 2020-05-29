#
# Copyright 2018, 2020 Antoine Sanner
#           2016, 2019 Lars Pastewka
#           2016 Till Junge
# 
# ### MIT license
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#

"""
Defines the interface for PyCo systems
"""

import abc

import numpy as np
import scipy

from PyCo import Adhesion, ContactMechanics, SurfaceTopography
from PyCo.Tools import compare_containers
from PyCo.ContactMechanics.Systems import IncompatibleFormulationError, IncompatibleResolutionError, SystemBase

class SmoothContactSystem(SystemBase):
    """
    For smooth contact mechanics (i.e. the ones for which optimization is only
    kinda-hell
    """
    def __init__(self, substrate, interaction, surface):
        """ Represents a contact problem
        Keyword Arguments:
        substrate   -- An instance of HalfSpace. Defines the solid mechanics in
                       the substrate
        interaction -- An instance of Interaction. Defines the contact
                       formulation. If this computes interaction energies,
                       forces etc, these are supposed to be expressed per unit
                       area in whatever units you use. The conversion is
                       performed by the system
        surface     -- An instance of SurfaceTopography, defines the profile.
        """
        super().__init__(substrate, interaction, surface)
        if not compare_containers(surface.nb_grid_pts, substrate.nb_grid_pts):
            raise IncompatibleResolutionError(
                ("the substrate ({}) and the surface ({}) have incompatible "
                 "nb_grid_ptss.").format(
                     substrate.nb_grid_pts, surface.nb_grid_pts))  # nopep8
        self.dim = len(self.substrate.nb_grid_pts)
        self.energy = None
        self.force = None

    @property
    def nb_grid_pts(self):
        # pylint: disable=missing-docstring
        return self.surface.nb_grid_pts

    @staticmethod
    def handles(substrate_type, interaction_type, surface_type, comm):
        is_ok = True
        # any periodic type of substrate formulation should do
        is_ok &= issubclass(substrate_type,
                            ContactMechanics.Substrate)

        # only soft interactions allowed
        is_ok &= issubclass(interaction_type,
                            Adhesion.SoftWall)

        # any surface should do
        is_ok &= issubclass(surface_type,
                            SurfaceTopography.UniformTopographyInterface)
        return is_ok

    def compute_repulsive_force(self):
        "computes and returns the sum of all repulsive forces"
        return self.pnp.sum(np.where(
            self.interaction.force > 0, self.interaction.force, 0
            ))

    def compute_attractive_force(self):
        "computes and returns the sum of all attractive forces"
        return self.pnp.sum(np.where(
            self.interaction.force < 0, self.interaction.force, 0
            ))

    def compute_normal_force(self):
        "computes and returns the sum of all forces"
        return self.pnp.sum(self.interaction.force)

    def compute_repulsive_contact_area(self):
        "computes and returns the area where contact pressure is repulsive"
        return self.compute_nb_repulsive_pts()*self.area_per_pt

    def compute_attractive_contact_area(self):
        "computes and returns the are where contact pressure is attractive"
        return self.compute_nb_attractive_pts()*self.area_per_pt

    def compute_nb_contact_pts(self):
        """
        compute and return the number of contact points. Note that this is of
        no physical interest, as it is a purely numerical artefact
        """
        return self.pnp.sum(np.where(self.interaction.force != 0., 1., 0.))

    def compute_nb_repulsive_pts(self):
        """
        compute and return the number of contact points under repulsive
        pressure. Note that this is of no physical interest, as it is a
        purely numerical artefact
        """
        return self.pnp.sum(np.where(self.interaction.force > 0., 1., 0.))

    def compute_nb_attractive_pts(self):
        """
        compute and return the number of contact points under attractive
        pressure. Note that this is of no physical interest, as it is a
        purely numerical artefact
        """
        return self.pnp.sum(np.where(self.interaction.force < 0., 1., 0.))

    def compute_repulsive_coordinates(self):
        """
        returns an array of all coordinates, where contact pressure is
        repulsive. Useful for evaluating the number of contact islands etc.
        """
        return np.argwhere(self.interaction.force > 0.)

    def compute_attractive_coordinates(self):
        """
        returns an array of all coordinates, where contact pressure is
        attractive. Useful for evaluating the number of contact islands etc.
        """
        return np.argwhere(self.interaction.force < 0.)

    def compute_mean_gap(self):
        """
        mean of the gap in the the physical domain (means excluding padding
        region for the FreeFFTElasticHalfspace)
        """
        return self.pnp.sum(self.gap) / np.prod(self.nb_grid_pts)

    def logger_input(self):
        """

        Returns
        -------
        headers: list of strings
        values: list
        """
        tot_nb_grid_pts = np.prod(self.nb_grid_pts)
        rel_rep_area = self.compute_nb_repulsive_pts() / tot_nb_grid_pts
        rel_att_area = self.compute_nb_attractive_pts() / tot_nb_grid_pts

        return (['energy', 'mean gap', 'frac. rep. area',
                       'frac. att. area',
                       'frac. int. area', 'substrate force', 'interaction force'],
              [self.energy,
               self.compute_mean_gap(),
               rel_rep_area,
               rel_att_area,
               rel_rep_area + rel_att_area,
               -self.pnp.sum(self.substrate.force),
               self.pnp.sum(self.interaction.force)])

    def  evaluate(self, disp, offset, pot=True, forces=False, logger=None):
        """
        Compute the energies and forces in the system for a given displacement
        field
        """
        # attention: the substrate may have a higher nb_grid_pts than the gap
        # and the interaction (e.g. FreeElasticHalfSpace)
        self.gap = self.compute_gap(disp, offset)
        self.interaction.compute(self.gap, pot=pot, forces=forces, curb=False,
                                 area_scale=self.area_per_pt)

        self.substrate.compute(disp, pot, forces)
        self.energy = (self.interaction.energy+
                       self.substrate.energy
                       if pot else None)
        if forces:
            self.force = self.substrate.force.copy()
            if self.dim == 1:
                self.force[self.comp_slice] += \
                  self.interaction.force#[self.comp_slice]  # nopep8
            else:
                self.force[self.comp_slice] += \
                  self.interaction.force#[self.comp_slice]  # nopep8
        else:
            self.force = None
        if logger is not None:
            logger.st(*self.logger_input())
        return (self.energy, self.force)

    def objective(self, offset, disp0=None, gradient=False, disp_scale=1.,
                  logger=None):
        """
        This helper method exposes a scipy.optimize-friendly interface to the
        evaluate() method. Use this for optimization purposes, it makes sure
        that the shape of disp is maintained and lets you set the offset and
        'forces' flag without using scipy's cumbersome argument passing
        interface. Returns a function of only disp
        Keyword Arguments:
        offset     -- determines indentation depth
        disp0      -- unused variable, present only for interface compatibility
                      with inheriting classes
        gradient   -- (default False) whether the gradient is supposed to be
                      used
        disp_scale -- (default 1.) allows to specify a scaling of the
                      dislacement before evaluation.
        logger     -- (default None) log information at every iteration.
        """
        dummy = disp0
        res = self.substrate.nb_subdomain_grid_pts
        if gradient:
            def fun(disp):
                # pylint: disable=missing-docstring
                try:
                    self.evaluate(
                        disp_scale * disp.reshape(res), offset, forces=True,
                        logger=logger)
                except ValueError as err:
                    raise ValueError(
                        "{}: disp.shape: {}, res: {}".format(
                            err, disp.shape, res))
                return (self.energy, -self.force.reshape(-1)*disp_scale)
        else:
            def fun(disp):
                # pylint: disable=missing-docstring
                return self.evaluate(
                    disp_scale * disp.reshape(res), offset, forces=False,
                    logger=logger)[0]

        return fun

    def callback(self, force=False):
        """
        Simple callback function that can be handed over to scipy's minimize to
        get updates during minimisation
        Parameters:
        force -- (default False) whether to include the norm of the force
                 vector in the update message
        """
        counter = 0
        if force:
            def fun(dummy):
                "includes the force norm in its output"
                nonlocal counter
                counter += 1
                print("at it {}, e = {}, |f| = {}".format(
                    counter, self.energy,
                    np.linalg.norm(np.ravel(self.force))))
        else:
            def fun(dummy):
                "prints messages without force information"
                nonlocal counter
                counter += 1
                print("at it {}, e = {}".format(
                    counter, self.energy))
        return fun

class BoundedSmoothContactSystem(SmoothContactSystem):
    @staticmethod
    def handles(*args, **kwargs): # FIXME work around, see issue #208
        return False

    def compute_nb_contact_pts(self):
        """
        compute and return the number of contact points.
        """
        return self.pnp.sum(np.where(self.gap == 0., 1., 0.))

    def logger_input(self):
        headers, vals = super().logger_input()
        headers.append("frac. cont. area")
        vals.append(self.compute_nb_contact_pts() / np.prod(self.nb_grid_pts))
        return headers, vals

    def compute_normal_force(self):
        "computes and returns the sum of all forces"

        # sum of the jacobian in the contact area (Lagrange multiplier)
        # and the ineraction forces.
        # can also be computed easily from the substrate forces, what we do here
        return self.pnp.sum( - self.substrate.force[self.substrate.topography_subdomain_slices])

    def compute_repulsive_force(self):
        """computes and returns the sum of all repulsive forces

        Assumptions: there
        """
        return self.pnp.sum(np.where( - self.substrate.force[self.substrate.topography_subdomain_slices] > 0,
                 - self.substrate.force[self.substrate.topography_subdomain_slices], 0.))

    def compute_attractive_force(self):
        "computes and returns the sum of all attractive forces"
        return self.pnp.sum(np.where( - self.substrate.force[self.substrate.topography_subdomain_slices] < 0,
                - self.substrate.force[self.substrate.topography_subdomain_slices], 0.))

    def compute_nb_repulsive_pts(self):
        """
        compute and return the number of contact points under repulsive
        pressure.

        """
        return self.pnp.sum(np.where(np.logical_and(self.gap == 0., - self.substrate.force[self.substrate.topography_subdomain_slices] > 0), 1., 0.))

    def compute_nb_attractive_pts(self):
        """
        compute and return the number of contact points under attractive
        pressure.
        """

        # Compute points where substrate force is negative or there is no contact
        pts = np.logical_or( - self.substrate.force[self.substrate.topography_subdomain_slices] < 0,
                                            self.gap > 0.)

        # exclude points where there is no contact and the interaction force is 0.
        pts[np.logical_and(self.gap > 0.,
            self.interaction.force == 0.)] = 0.

        return self.pnp.sum(pts)

    def compute_repulsive_coordinates(self):
        """
        returns an array of all coordinates, where contact pressure is
        repulsive. Useful for evaluating the number of contact islands etc.
        """
        return np.argwhere(np.logical_and(self.gap == 0., - self.substrate.force[self.substrate.topography_subdomain_slices] > 0))

    def compute_attractive_coordinates(self):
        """
        returns an array of all coordinates, where contact pressure is
        attractive. Useful for evaluating the number of contact islands etc.
        """

        # Compute points where substrate force is negative or there is no contact
        pts = np.logical_or( - self.substrate.force[self.substrate.topography_subdomain_slices] < 0,
                                            self.gap > 0.)

        # exclude points where there is no contact and the interaction force is 0.
        pts[np.logical_and(self.gap > 0.,
            self.interaction.force == 0.)] = 0.

        return np.argwhere(pts)