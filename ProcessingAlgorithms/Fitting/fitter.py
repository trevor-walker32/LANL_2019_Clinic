# coding:utf-8

"""
::

   Author:  LANL Clinic 2019 --<lanl19@cs.hmc.edu>
   Purpose: Manage nonlinear least-squares fits
   Created: 3/11/20
"""
import numpy as np
from scipy.optimize import curve_fit  # , OptimizeWarning
import matplotlib.pyplot as plt


class Fitter:
    """
    Manage a fitting operation
    """

    def __init__(self, function, xvalues, yvalues, sigma, param_dictionary: dict):
        self.f = function
        self.x = xvalues
        self.y = yvalues
        self.notnan = np.logical_not(np.logical_or(
            np.isnan(self.y), np.isnan(sigma)))
        self.numpts = np.sum(self.notnan)
        self.sigma = sigma
        self.p0 = param_dictionary
        self.p, self.pcov = curve_fit(
            self.f, self.x[self.notnan], self.y[self.notnan],
            list(self.p0.values()), sigma[self.notnan],
            absolute_sigma=True)
        self.residuals = self.y - self.f(self.x, *self.p)
        self.normalized_residuals = self.residuals / self.sigma
        self.chisq = np.sum(np.power(self.normalized_residuals, 2))
        self.reduced_chisq = self.chisq / (self.numpts - len(self.p))
        self.errors = np.sqrt(np.diag(self.pcov))

    def format_value(self, x, err):
        """
        Format the display of the value x and the error to handle the right number of digits.
        """
        if x == 0:
            digits = 1 - np.floor(np.log10(err))
        else:
            digits = 1 + np.floor(np.log10(np.abs(x / err)))
        if np.isnan(digits):
            digits = 2
        fmt = "{0:." + f"{int(digits)}" + "}"
        val = fmt.format(x)
        return f"{val} ± {err:.2g}"

    def __str__(self):
        nans = len(self.notnan) - self.numpts
        nanmsg = "." if nans == 0 else f", with {nans} NaNs."
        report = [f"Fit to {self.f.__name__} using {self.numpts} points{nanmsg}", ]
        for par0, param, err in zip(self.p0.keys(), self.p, self.errors):
            report.append(f"{par0} = {self.format_value(param, err)}")
        report.append(f"χ2 = {self.chisq:.2g} = {self.reduced_chisq:.2f}/DoF")
        return "\n".join(report)

    def plot(self, **kwargs):

        self.fig, self.axes = plt.subplots(
            nrows=3, ncols=1,
            sharex=True, squeeze=True,
            gridspec_kw=dict(
                height_ratios=[0.2, 0.2, 0.6],
                left=0.075,
                right=0.975,
                wspace=0.05
            )
        )
        res, normres, main = self.axes
        main.plot(self.x, self.y, 'k.', alpha=0.5)
        xvals = np.linspace(self.x[0], self.x[-1], 200)
        yvals = self.f(xvals, *self.p)
        main.plot(xvals, yvals, 'r-', alpha=0.5)
        if 'xlabel' in kwargs:
            main.set_xlabel(kwargs['xlabel'])
        if 'ylabel' in kwargs:
            main.set_ylabel(kwargs['ylabel'])

        # Now the residual panel
        res.errorbar(self.x, self.residuals, yerr=self.sigma, fmt='.')
        res.set_ylabel('Res')

        # and the normalized residuals
        normres.plot(self.x, self.normalized_residuals, '.')
        normres.set_ylabel('Norm res')

        if 'title' in kwargs:
            res.set_title(kwargs['title'])
