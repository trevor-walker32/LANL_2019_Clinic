#! /usr/bin/env python3

import os
import numpy as np
import matplotlib.pyplot as plt
from scipy import signal

from digfile import DigFile


class Spectrogram:
    """
    A Spectrogram takes a DigFile and a time range, as
    well as plenty of options, and generates a spectrogram
    using scipy.signal.spectrogram.

    Required arguments to the constructor:
        digfile: either an instance of DigFile or the filename of a .dig file
        t_start: time of the first point to use in the spectrogram
        ending:  either the time of the last point or a positive integer
                 representing the number of points to use

    Optional arguments and their default values:
        wavelength: (1550.0e-9) the wavelength in meters
        points_per_spectrum: (8192) the number of values used to generate
            each spectrum. Should be a power of 2.
        overlap_shift_factor: (1/8) the fraction of points_per_spectrum
            that defines the offset of successive spectra. An
            overlap_shift_factor of 1 means that each sample is used
            in only one spectrum. The default value means that successive
            spectra share 7/8 of their source samples.
        window_function: (None) the window function used by signal.spectrogram.
            The default value implies a ('tukey', 0.25) window.
        form: ('db') whether to use power values ('power'), decibels ('db'),
            or log(power) ('log') in reporting spectral intensities.
        convert_to_voltage: (True) scale the integer values stored in the
            .dig file to voltage before computing the spectrogram. If False,
            the raw integral values are used.
        detrend: ("linear") the background subtraction method.

    Computed fields:
        t: array of times at which the spectra are computed
        f: array of frequencies present in each spectrum
        v: array of velocities corresponding to each spectrum
        intensity: two-dimensional array of (scaled) intensities, which
            is the spectrogram. The first index corresponds to
            frequency/velocity, the second to time.
    """

    def __init__(self,
                 digfile,
                 t_start,
                 ending,
                 wavelength=1550.0e-9,
                 points_per_spectrum=8192,
                 overlap_shift_factor=1 / 8,
                 window_function=None,  # 'hanning',
                 form='db',
                 convert_to_voltage=True,
                 detrend="linear",
                 **kwargs
                 ):
        """
        TODO: We are currently not handling kwargs
        """
        if isinstance(digfile, DigFile):
            self.data = digfile
        elif isinstance(digfile, str):
            self.data = DigFile(digfile)
        else:
            raise TypeError("Unknown file type")
        self.t_start = t_start if t_start != None else self.data.t0
        p_start, p_end = self.data._points(self.t_start, ending)
        self.t_end = self.t_start + self.data.dt * (p_end - p_start + 1)

        self.wavelength = wavelength
        self.points_per_spectrum = points_per_spectrum
        self.shift = int(points_per_spectrum * overlap_shift_factor)
        self.window_function = window_function
        self.form = form
        self.use_voltage = convert_to_voltage
        self.detrend = detrend
        # deal with kwargs

        self._compute(ending)

    def __str__(self):
        return ", ".join(
            [str(x) for x in
             [self.data.filename,
              f"{self.points_per_spectrum} / {self.shift}",
              self.form
              ]
             ])

    def _compute(self, ending):
        """
        Compute a spectrogram. This needs work! There need to be
        lots more options that we either want to supply with
        default values or decode kwargs. But it should be a start.
        """
        if self.use_voltage:
            vals = self.data.values(self.t_start, ending)
        else:
            vals = self.data.raw_values(self.t_start, ending)

        # if normalize:
        #    vals = self.normalize(
        #        vals, chunksize=fftSize, remove_dc=remove_dc)
        freqs, times, spec = signal.spectrogram(
            vals,
            1.0 / self.data.dt,  # the sample frequency
            window=self.window_function if self.window_function else (
                'tukey', 0.25),
            nperseg=self.points_per_spectrum,
            noverlap=self.shift,
            detrend=self.detrend,  # could be constant,
            scaling="spectrum"
        )
        times += self.t_start
        # Attempt to deduce baselines
        # baselines = np.sum(spec, axis=1)

        # Convert to a logarithmic representation and use floor to attempt
        # to suppress some noise.
        spec *= 2.0 / (self.points_per_spectrum * self.data.dt)
        if self.form == 'db':
            spec = 20 * np.log10(spec)
        elif self.form == 'log':
            spec = np.log10(spec)
        # scale the frequency axis to velocity
        self.velocity = freqs * 0.5 * self.wavelength  # velocities
        self.frequency = freqs
        self.time = times
        self.intensity = spec  # a two-dimensional array
        # the first index is frequency, the second time

    @property
    def max(self):
        """The maximum intensity value"""
        return self.intensity.max()

    @property
    def v_max(self):
        return self.wavelength * 0.25 / self.data.dt

    def plot(self, axes=None, **kwargs):
        # max_vel=6000, vmin=-200, vmax=100):
        if axes == None:
            axes = plt.gca()
        if 'max_vel' in kwargs:
            axes.set_ylim(top=kwargs['max_vel'])
            del kwargs['max_vel']

        pcm = axes.pcolormesh(
            self.time * 1e6,
            self.velocity,
            self.intensity,
            **kwargs)

        plt.gcf().colorbar(pcm, ax=axes)
        axes.set_ylabel('Velocity (m/s)')
        axes.set_xlabel('Time ($\mu$s)')
        title = self.data.filename.split('/')[-1]
        axes.set_title(title.replace("_", "\\_"))
        return pcm

        # bestVelocity = self.extract_velocities(sgram)

        # fig = plt.figure()
        # plt.plot(sgram['t'], bestVelocity, color="red")


if False:
    def scan_data(self):
        """
        Load the entire file and determine the range of raw integer values
        """
        raw = self.raw_values(self.t0, self.num_samples)
        self.raw = dict(min=np.min(raw), max=np.max(raw), mean=np.mean(raw))
        self.raw['range'] = self.raw['max'] - self.raw['min']

    def __str__(self):
        return "\n".join([
            self.filename,
            f"{self.bits} bits" + f" {self.notes['byte_order']} first" if 'byte_order' in self.notes else "",
            f"{self.t0*1e6} µs to {(self.t0 + self.dt*self.num_samples)*1e6} µs in steps of {self.dt*1e12} ps"
        ])

    def normalize(self, array, chunksize=4096, remove_dc=True):
        """
        Given an array of periodically sampled points, normalize to a
        peak amplitude of 1, possibly after removing dc in segments of
        chunksize.
        """
        if remove_dc:
            num_chunks, num_leftovers = divmod(len(array), chunksize)
            if num_leftovers:
                leftovers = array[-num_leftovers:]
                chunks = array[:num_chunks *
                               chunksize].reshape((num_chunks, chunksize))
                avg = np.mean(leftovers)
                leftovers -= avg
            else:
                chunks = array.reshape((num_chunks, chunksize))
            # compute the average of each chunk
            averages = np.mean(chunks, axis=1)
            # shift each chunk to have zero mean
            for n in range(num_chunks):
                chunks[n, :] -= averages[n]
            flattened = chunks.reshape(num_chunks * chunksize)
            if num_leftovers:
                flattened = np.concatenate((flattened, leftovers))
        else:
            flattened = array

        # Now normalize, making the largest magnitude 1
        peak = np.max(np.abs(array))
        return flattened / peak

    def spectrum(self, t, nSamples, remove_dc=True):
        """
        Compute a spectrum from nSamples centered at time t
        """
        from spectrum import Spectrum
        tStart = t - nSamples // 2 * self.dt
        if tStart < self.t0:
            tStart = self.t0
        raw = self.values(tStart, nSamples)
        return Spectrum(raw, self.dt, remove_dc)

    def extract_velocities(self, sgram):
        """
            Use scipy's peak finding algorithm to calculate the 
            velocity at that time slice.

            The sgram will come in as a dictionary

            't': times,
            'v': velocities,
            'spectrogram': spec,
            'fftSize': fftSize,
            'floor': floor            


            spec will be indexed in velocity and then time 


            Output:
                return a list of the velocities of maximum intensity in
                each time slice.    
        """

        t = sgram['t']
        v = sgram['v']
        spectrogram = sgram['spectrogram']
        fftSize = sgram['fftSize']
        floor = sgram['floor']

        # spectrogram needs to be rotated so that it can be indexed with t first.

        timeThenVelocitySpectrogram = np.transpose(spectrogram)

        output = np.zeros(len(t))

        print(v[2048])

        if len(t) != timeThenVelocitySpectrogram.shape[0]:
            raise ValueError("Our assumption was invalid.")

        for time_index in range(timeThenVelocitySpectrogram.shape[0]):
            currentVelocityIndex = np.argmax(
                timeThenVelocitySpectrogram[time_index])

            print("The current best velocity index is", currentVelocityIndex)
            print(type(currentVelocityIndex))

            output[time_index] = v[currentVelocityIndex]

        return output


if __name__ == '__main__':
    sp = Spectrogram('sample.dig', 0, 10e-6)
    print(sp)

