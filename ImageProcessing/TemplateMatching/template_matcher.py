#!/usr/bin/env python3
# coding:utf-8
"""
::

  Author:  LANL Clinic 2019 --<lanl19@cs.hmc.edu>
  Purpose: Attempt to match templates in a user specified area.
  Created: 2/16/20
"""
import cv2  # The general computer vision library for python.
import numpy as np
from ProcessingAlgorithms.SignalExtraction.baselines import baselines_by_squash
from spectrogram import Spectrogram
import ImageProcessing.TemplateMatching.Templates.saveTemplateImages as templateHelper
import os
from ImageProcessing.TemplateMatching.Templates.templates import Templates
import scipy
if scipy.__version__ > "1.2.1":
    from imageio import imsave
else:
    from scipy.misc import imsave

from matplotlib import pyplot as plt
from matplotlib.patches import Rectangle
from sklearn_extra.cluster import KMedoids


class TemplateMatcher():
    """
    Tries to find the local maximum from scores returned by various
    OpenCV template matching algorithms, based on user input.

    **Inputs to the constructor**

    - spectrogram: an instance of Spectrogram
    - start_point: (t, v), the coordinates at which to begin the search
    - template: a two-dimensional array that is read into to OpenCV as
        a template image for matching.
    - span: (80) a 'radius' of pixels surrounding the starting point to 
        increase the searching space for the starting point.

    """

    def __init__(self, spectrogram, 
                       template, 
                       start_point=None, 
                       span=80, 
                       velo_scale=10, 
                       k=10,
                       methods=['cv2.TM_CCOEFF', 
                                'cv2.TM_CCOEFF_NORMED', 
                                'cv2.TM_CCORR', 
                                'cv2.TM_CCORR_NORMED', 
                                'cv2.TM_SQDIFF', 
                                'cv2.TM_SQDIFF_NORMED'],
                        useCorrectionFactor:bool = False
                        ):

        assert isinstance(spectrogram, Spectrogram)
        assert (len(template[0]) > 0)

        self.spectrogram = spectrogram
        self.template = template[0]

        self.span = int(span)
        self.velo_scale = int(velo_scale)
        self.template_time_offset_index = int(template[1])
        self.template_velo_offset_index = int(template[2])
        self.k = int(k)

        # To get the intensity matrix the way it was when we trained it.
        if useCorrectionFactor:
            epsilon = 1e-10
            self.matrixToMatch = 20 * np.log10(2*self.spectrogram.psd/(self.spectrogram.points_per_spectrum*self.spectrogram.data.dt) + epsilon)
        else:
            # This will increase the memory usage but it will make it so that we do not overwrite the data in spectrogram.intensity that might be needed later.
            self.matrixToMatch = np.copy(self.spectrogram.intensity) 

        self.zero_time_index = spectrogram._time_to_index(0)
        self.zero_velo_index = spectrogram._velocity_to_index(0)

        if start_point is None:
            self.click = (self.zero_time_index, self.zero_velo_index)
        else:
            assert isinstance(start_point, tuple)
            self.click = start_point

        self.matching_methods = methods
        self.num_methods = len(methods)

        self.setup()

    def setup(self):

        velo_scale = self.velo_scale
        time_index, velocity_index = self.click

        if time_index < 0:
            time_index = 0
        if velocity_index < 0:
            velocity_index = 0

        max_time_index = self.spectrogram.intensity.shape[1] - 1
        ending_time_index = time_index + self.span * 10

        assert (ending_time_index < max_time_index)
        start_time = self.spectrogram.time[time_index]
        end_time = self.spectrogram.time[ending_time_index]

        max_velo_index = self.spectrogram.intensity.shape[0] - 1
        ending_velo_index = velocity_index + (velo_scale * self.span)

        assert (ending_velo_index < max_velo_index)
        start_velo = self.spectrogram.velocity[velocity_index]
        end_velo = self.spectrogram.velocity[ending_velo_index]

        zero_index = self.spectrogram._time_to_index(0)

        max_velo = self.spectrogram.velocity[max_velo_index]
        max_time = self.spectrogram.time[max_time_index]

        # indices, not actual time/velo values
        self.time_bounds = (time_index, ending_time_index)
        self.velo_bounds = (velocity_index, ending_velo_index)

    def crop_intensities(self, matrix):

        percentile_value = 98

        time_bounds = self.time_bounds
        velo_bounds = self.velo_bounds

        assert (velo_bounds[0] != velo_bounds[1])
        assert (time_bounds[0] != time_bounds[1])

        if velo_bounds[0] == 0:
            flipped_velo_bounds = (-1 * velo_bounds[1], -1)
        else:
            flipped_velo_bounds = (-1 * velo_bounds[1], -1 * velo_bounds[0])

        self.flipped_velo_bounds = flipped_velo_bounds

        # imsave("./original.png", cleaned_matrix[:])

        cleaned_matrix = np.flip(np.flip(matrix), axis=1)
        cleaned_matrix = cleaned_matrix - np.min(cleaned_matrix)

        sorted_matrix = sorted(cleaned_matrix.flatten(), reverse=True)
        threshold_percentile = np.percentile(sorted_matrix, percentile_value)

        cleaned_matrix = np.where(cleaned_matrix > threshold_percentile,
                                  cleaned_matrix + threshold_percentile, threshold_percentile)

        # imsave("./flipped_original.png", cleaned_matrix[:])

        spec = cleaned_matrix[flipped_velo_bounds[0]:flipped_velo_bounds[1], time_bounds[0]:time_bounds[1]]
        # imsave("./debug.png", spec[:])

        return spec

    def match(self):

        cropped_spectrogram = self.crop_intensities(self.matrixToMatch)

        imsave("./im_template.png", self.template[:])
        imsave("./im_cropped_bg.png", cropped_spectrogram[:])

        img = cv2.imread('./im_cropped_bg.png', 0)
        img2 = img.copy()

        template = cv2.imread('./im_template.png', 0)
        w, h = template.shape[::-1]

        methods = self.matching_methods
        num_methods = self.num_methods

        # # All 6 available comparison methods in a list
        # methods = ['cv2.TM_CCOEFF', 'cv2.TM_CCOEFF_NORMED', 'cv2.TM_CCORR',
        #             'cv2.TM_CCORR_NORMED', 'cv2.TM_SQDIFF', 'cv2.TM_SQDIFF_NORMED']

        # methods = ['cv2.TM_CCOEFF_NORMED', 'cv2.TM_SQDIFF', 'cv2.TM_SQDIFF_NORMED']

        # methods = ['cv2.TM_SQDIFF', 'cv2.TM_SQDIFF_NORMED']  # the 'best' method for matching

        xcoords = []
        ycoords = []
        scores = []
        methodUsed = []
        # print(methods)
        for method_index, method_name in enumerate(methods):
            img = img2.copy()
            method = eval(method_name)

            # Apply template Matching
            res = cv2.matchTemplate(img, template, method)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

            # get all the matches:
            result2 = np.reshape(res, res.shape[0] * res.shape[1])
            sort = np.argsort(result2)

            best_k = []

            for i in range(self.k):
                best_k.append(np.unravel_index(sort[i], res.shape)[::-1])

            for point in best_k:

                methodUsed.append(methods[method_index])

                # If the method is TM_SQDIFF or TM_SQDIFF_NORMED, take minimum
                if method in [cv2.TM_SQDIFF, cv2.TM_SQDIFF_NORMED]:
                    top_left = point
                    scores.append(min_val)
                else:
                    top_left = point
                    scores.append(max_val)


                # correct for template offset to get actual point
                bottom_right = (top_left[0] + w, top_left[1] + h)

                velo_offset_index = self.template_velo_offset_index
                time_offset_index = self.template_time_offset_index

                real_velo_index = abs(
                    self.flipped_velo_bounds[0] + bottom_right[1]) + velo_offset_index

                # there might be a bug here. Causing issues with jupyter notebook timing index offsets.
                time_match = self.spectrogram.time[top_left[0]] * 1e6
                template_offset_time = self.spectrogram.time[time_offset_index] * 1e6
                start_time = self.spectrogram.time[self.zero_time_index] * 1e6 * -1
                time_offset = abs(
                    self.spectrogram.time[self.time_bounds[0]] * 1e6)

                time_total = time_match + template_offset_time + start_time + time_offset

                true_velo = self.spectrogram.velocity[real_velo_index]

                xcoords.append(time_total)
                ycoords.append(true_velo)

        return xcoords, ycoords, scores, methodUsed

    def matchMultipleTemplates(self, methods=['cv2.TM_CCOEFF', 'cv2.TM_CCOEFF_NORMED', 'cv2.TM_CCORR', 'cv2.TM_CCORR_NORMED', 'cv2.TM_SQDIFF', 'cv2.TM_SQDIFF_NORMED'], templatesList: list = None):
        """
            Enable the use of multiple templates in testing.
        """
        if templatesList == None:
            return self.match(methods=methods)

        else:
            # Load all the templates once. Then call all the matches from there.

            cropped_spectrogram = self.crop_intensities(self.matrixToMatch)

            imsave("./im_cropped_bg.png", cropped_spectrogram[:])

            img = cv2.imread('./im_cropped_bg.png', 0)
            img2 = img.copy()

            outputValues = [[] for i in range(len(templatesList))]
            imageSaveDir = templateHelper.getImageDirectory()
            
            # If at least one file does not exist just make all of them.
            for tempInd, temp in enumerate(templatesList):
                if not os.path.exists(os.path.join(imageSaveDir, f"im_template_{temp}.png")):
                    templateHelper.saveAllTemplateImages()
                    break

            for tempInd, temp in enumerate(templatesList):
                template = cv2.imread(os.path.join(imageSaveDir, f"im_template_{temp}.png"), 0)

                self.template_time_offset_index, self.template_velo_offset_index = temp.value[
                    1:]

                w, h = template.shape[::-1]

                xcoords = []
                ycoords = []
                scores = []
                methodUsed = []

                for meth_i, meth in enumerate(methods):
                    img = img2.copy()
                    method = eval(meth)

                    # Apply template Matching
                    res = cv2.matchTemplate(img, template, method)
                    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

                    # get all the matches:
                    result2 = np.reshape(res, res.shape[0] * res.shape[1])
                    sort = np.argsort(result2)

                    best_k = []

                    for i in range(self.k):
                        best_k.append(np.unravel_index(
                            sort[i], res.shape)[::-1])

                    for point in best_k:

                        methodUsed.append(meth_i)

                        # If the method is TM_SQDIFF or TM_SQDIFF_NORMED, take minimum
                        if method in [cv2.TM_SQDIFF, cv2.TM_SQDIFF_NORMED]:
                            top_left = point
                            scores.append(min_val)
                        else:
                            top_left = point
                            scores.append(max_val)

                        bottom_right = (top_left[0] + w, top_left[1] + h)

                        velo_offset_index = self.template_velo_offset_index
                        time_offset_index = self.template_time_offset_index

                        real_velo_index = abs(
                            self.flipped_velo_bounds[0] + bottom_right[1]) + velo_offset_index

                        time_match = self.spectrogram.time[top_left[0]] * 1e6
                        template_offset_time = self.spectrogram.time[time_offset_index] * 1e6
                        start_time = self.spectrogram.time[self.zero_time_index] * 1e6 * -1
                        time_offset = abs(
                            self.spectrogram.time[self.time_bounds[0]] * 1e6)

                        time_total = time_match + template_offset_time + start_time + time_offset

                        true_velo = self.spectrogram.velocity[real_velo_index]

                        xcoords.append(time_total)
                        ycoords.append(true_velo)

                outputValues[tempInd] = tuple(
                    [xcoords, ycoords, scores, methodUsed])

        return outputValues

    def find_kmedoids(self, xcoords, ycoords, clusters=5, random_state=None):
        assert(len(xcoords) == len(ycoords))
        X = np.stack((xcoords, ycoords), axis = 1) # Give me an array of with columns xcoords and ycoords.

        kmedoids = KMedoids(n_clusters=clusters, random_state=random_state).fit(X)
        return kmedoids.cluster_centers_ # return a np array of shape (clusters, 2). The columns are xcoords and ycoords.

    def mask_baselines(self):
        peaks, _, _ = baselines_by_squash(self.spectrogram)
        minimum = np.min(self.spectrogram.intensity)
        for peak in peaks:
            velo_index = self.spectrogram._velocity_to_index(peak)
            velo_index = velo_index - 20
            for i in range(velo_index, velo_index + 40, 1):
                self.matrixToMatch[i][:] = minimum

    def add_to_plot(self, axes, times, velos, scores, methodsUsed,
                    show_points=True,
                    show_medoids=True, 
                    verbose=False, 
                    visualize_opacity=False,
                    show_bounds=True):

        if show_bounds:
            firstVel, dv = self.spectrogram.velocity[list(self.velo_bounds)]
            firstTime, dt = self.spectrogram.time[list(self.time_bounds)] * 1e6
            patch = Rectangle((firstTime, firstVel), dt, dv, fill=False, color='b', alpha=0.8)
            axes.add_patch(patch)

        method_color_dict = {}
        method_color_dict['cv2.TM_CCOEFF'] = ('ro', 'red')
        method_color_dict['cv2.TM_CCOEFF_NORMED'] = ('bo', 'blue')
        method_color_dict['cv2.TM_CCORR'] = ('go', 'green')
        method_color_dict['cv2.TM_CCORR_NORMED'] = ('mo', 'magenta')
        method_color_dict['cv2.TM_SQDIFF'] = ('ko', 'black')
        method_color_dict['cv2.TM_SQDIFF_NORMED'] = ('co', 'cyan')

        handles = []
        seen_handles = []
        for i in range(len(times)):

            if verbose:
                # added print statements to be read from the command line
                print("time: ", times[i])
                print("velocity: ", velos[i])
                print("score: ", scores[i])
                print("color: ", method_color_dict[methodsUsed[i]][1])
                print("method: ", methodsUsed[i], '\n')

            if visualize_opacity and show_points: #not quite working
                # plot the points in descending order, decreasing their opacity so the 'best' points 
                # can be visualized best. 
                rank = (i % self.k)
                maxscore = np.max(scores)
                opacity = (1 / (maxscore / scores[i]))
                point_method = methodsUsed[i]
                point, = axes.plot(
                    times[i], velos[i], method_color_dict[methodsUsed[i]][0], markersize=2.5, alpha=opacity)
            else:
                if show_points:
                    point_method = methodsUsed[i]
                    # plot the point found from template matching in order from 'best' to 'worst' match
                    point, = axes.plot(
                        times[i], velos[i], method_color_dict[methodsUsed[i]][0], markersize=2.5, alpha=.80)

            # add each method to the plot legend handle
            if show_points:
                if point_method not in seen_handles:
                    seen_handles.append(point_method)
                    point.set_label(point_method)
                    handles.append(point)

        # cluster coordinates received from template matching, find cluster centers and plot them
        if show_medoids:
            centers = self.find_kmedoids(times, velos, clusters = self.num_methods)
            for t,v in centers:
                center, = axes.plot(t, v, 'ro', markersize=4, alpha=.9)
            center.set_label("cluster center")
            handles.append(center)

        # #update the legend with the current plotting handles
        axes.legend(handles=handles, loc='upper right')

        # display plot
        # print(plt.rcParams)

        plt.show()


if __name__ == "__main__":
    """
    example files 

    WHITE_CH1_SHOT/seg00.dig -- opencv_long_start_pattern4 span=200
    WHITE_CH2_SHOT/seg00.dig -- opencv_long_start_pattern4 span=200
    WHITE_CH3_SHOT/seg00.dig -- opencv_long_start_pattern4 span=200
    WHITE_CH4_SHOT/seg00.dig -- ??? opencv_long_start_pattern4 span=200

    BLUE_CH1_SHOT/seg00.dig -- opencv_long_start_pattern4 span=150
    BLUE_CH2_SHOT/seg00.dig -- ??? opencv_long_start_pattern3 span=200
    BLUE_CH3_SHOT/seg00.dig -- opencv_long_start_pattern4 span=200

    CH_1_009/seg00.dig -- opencv_long_start_pattern2 span=200
    CH_3_009/seg00.dig -- opencv_long_start_pattern2 span=200
    CH_4_009/seg01.dig -- opencv_long_start_pattern2 span=200
    CH_4_009/seg02.dig -- opencv_long_start_pattern4 span=200
    """
    from ProcessingAlgorithms.preprocess.digfile import DigFile

    path = "../dig/BLUE_CH1_SHOT/seg00.dig"
    df = DigFile(path)
    spec = Spectrogram(df, 0.0, 60.0e-6, overlap_shift_factor= 1/8, form='db')
    spec.availableData = ['intensity']

    # print(spec.time[200])

    # gives user the option to click, by default it searches from (0,0)
    template_matcher = TemplateMatcher(spec,template=Templates.opencv_long_start_pattern5.value,
                                            span=200,
                                            k=20,
                                            methods=['cv2.TM_CCOEFF_NORMED', 'cv2.TM_SQDIFF', 'cv2.TM_SQDIFF_NORMED'])


    # masks the baselines to try and avoid matching with baselines or echoed signals
    template_matcher.mask_baselines()

    # get the times and velocities from matching
    times, velos, scores, methodsUsed = template_matcher.match()

    pcms, axes = template_matcher.spectrogram.plot(min_time=0, min_vel=0, max_vel=10000, cmap='3w_gby')
    pcm = pcms['intensity raw']
    pcm.set_clim(-30, -65)

    template_matcher.add_to_plot(axes, times, velos, scores, methodsUsed, 
                                show_points=True, 
                                show_medoids=True, 
                                verbose=False, 
                                visualize_opacity=False, 
                                show_bounds=True)
