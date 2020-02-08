# coding:utf-8

"""
::

   Author:  LANL Clinic 2019 --<lanl19@cs.hmc.edu>
   Purpose: Manage gaussian fits
   Created: 11/17/19
"""
import numpy as np
from scipy.optimize import curve_fit, OptimizeWarning
from ProcessingAlgorithms.Fitting.moving_average import moving_average


class Gaussian:
    """
    Object to perform a gaussian fit.
    The data y(x) to which we need to look for a gaussian
    fit. The keyword arguments can specify any or all
    of the gaussian parameters:

      - background
      - amplitude
      - center
      - width

    If the fit is successful, the field Gaussian.valid is
    set to True.
    """

    def __init__(self, x: np.ndarray, y: np.ndarray, **kwargs):
        """

        """
        assert len(x) == len(y)
        if len(x) < 4:
            self.valid = False
            self.error = "Insufficient points"
        else:
            self.x = x
            self.y = y
            # sort y and use the boundaries to estimate
            # the background and amplitude
            ysorted = sorted(y)
            # the gaussian could be a peak or a dip
            midpt = ysorted[len(y) // 2]
            peak = (ysorted[-1] - midpt) > (midpt - ysorted[0])
            amplitude = (ysorted[-1] - ysorted[len(y) // 8]
                         ) * (1 if peak else -1)
            background = ysorted[len(
                y) // 8] if peak else ysorted[(7 * len(y)) // 8]
            if background == 0:
                background = 0.01 * amplitude
            center = x[y.argmax()]
            self.p0 = [
                kwargs.get('amplitude', amplitude),
                kwargs.get('center', center),
                kwargs.get('width', 0),
                kwargs.get('background', background)
            ]
            self.params = []
            self.error = None
            if self.p0[2] == 0:
                self.estimate_width(y.argmax())
            self.valid = self.do_fit()

    @property
    def center(self):
        "The location of the peak of the gaussian"
        return self.params[1]

    @property
    def width(self):
        "The standard deviation of the gaussian"
        return self.params[2]

    @property
    def amplitude(self):
        "The amplitude of the gaussian"
        return self.params[0]

    @property
    def background(self):
        "The (constant) background level surrounding the gaussian"
        return self.params[3]

    def __str__(self):
        if self.valid:
            lines = []
            for name, val, err in \
                zip(('amplitude', 'center', 'width', 'bgnd'),
                    self.params, self.errors):
                lines.append(f"{name: >12} = {val:.4g} ± {err:.4g}")
            return "\n".join(lines)
        return "Invalid fit"

    def __call__(self, x):
        """Given an array of x values, return corresponding fitted values"""
        return self._gauss(x, *self.params)

    @staticmethod
    def _gauss(x, *p):
        """Gaussian fitting function used by curve_fit"""
        A, mu, sigma, background = p
        return background + A * \
            np.exp(-0.5 * ((x - mu) / sigma)**2)

    def do_fit(self):
        if len(self.x) < len(self.p0):
            return False
        try:
            self.params, covar = curve_fit(
                self._gauss, self.x, self.y, p0=self.p0
            )
        except (RuntimeError, RuntimeWarning, OptimizeWarning) as eeps:
            self.error = eeps
            return False

        if np.inf in covar or np.nan in covar:
            self.error = 'infinity or nan in cavariance matrix'
            return False
        self.errors = np.sqrt(np.diag(covar))
        # if width is negative, flip it
        self.params[2] = abs(self.params[2])
        # How do we know that it worked?
        return True

    def estimate_width(self, n: int):
        """
        Attempt to guess the width of the peak that
        allegedly occurs at index n
        """
        # Let's slightly smooth the data
        sm = moving_average(self.y, 3)
        avg = sm.mean()
        amp = sm[n] - avg
        target = avg + 0.3 * amp
        try:
            for j in range(10):
                if sm[n + j] < target:
                    break
        except:
            j -= 1
        try:
            for k in range(10):
                if sm[n - k] < target:
                    break
        except:
            k -= 1
        width = (self.x[n + j] - self.x[n - k]) * 0.6
        self.p0[2] = width if width > 0 else self.x[1] - self.x[0]


if __name__ == '__main__':
    from numpy.random import Generator, PCG64
    import matplotlib.pyplot as plt
    rg = Generator(PCG64())
    x = np.linspace(-3, 3, 61)
    xfine = np.linspace(-3, 3, 601)
    center = rg.standard_normal()
    width = 0.1 + abs(0.1 * rg.standard_normal())
    amp = rg.uniform(0.1, 100)
    background = rg.uniform(0, 50)
    noise = rg.uniform(0.05 * amp, 0.25 * amp)
    arg = (x - center) / width
    y = background + amp * np.exp(-0.5 * arg**2)
    y += rg.normal(0, noise, len(y))
    gus = Gaussian(x, y)
    print("Fit results:")
    print(gus)
    print('\nActual parameters:')
    print(f'amplitude = {amp:.3g}')
    print(f'center = {center:.3g}  ({abs((center-gus.params[1])/gus.errors[1]):.1f} σ)')
    print(f'width = {width:.3g}  ({abs((width-gus.params[2])/gus.errors[2]):.1f} σ)')
    print(f'background = {background:.3g}')
    plt.plot(x, y, 'ro', alpha=0.5)
    plt.plot(x, moving_average(y), 'go', alpha=0.25)
    plt.plot(xfine, gus(xfine), 'k-')
    plt.show()


