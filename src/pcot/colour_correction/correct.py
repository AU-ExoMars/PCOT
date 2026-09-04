import numpy as np
from  pcot.colour_correction import colour_transforms
from scipy.interpolate import BSpline
from pcot.assets import getAssetPath


class ColourCorrection:
    def __init__(self):
        cali_dir = getAssetPath('data/colour_correction/')
        # Load the calibrated non-linearity correction B-spline, fit to the
        # sensor's opto-electronic response curve.
        spl_o_coeffs = np.load(cali_dir / 'pc_th_spl_o.npz')
        self.spline = BSpline(spl_o_coeffs['t'], spl_o_coeffs['c'], int(spl_o_coeffs['k'][0]))
        # Load the calibrated colour correction matrix (camera RGB -> CIE XYZ).
        th_ccm_path = cali_dir / 'pc_th_ccm.csv'
        self.th_ccm = np.loadtxt(th_ccm_path, delimiter=',')

    def _non_linearity_correction(self, image:np.ndarray) -> np.ndarray:
        # apply the non-linearity correction (subtract the spline-modelled
        # deviation from linear response) and clip back to a valid [0, 1] range.
        image = image - self.spline(image)
        return np.clip(image, 0, 1)

    def _to_XYZ(self, RGB:np.ndarray) -> np.ndarray:
        # white-balance by normalising to the brightest green pixel, then
        # apply the CCM to map camera-native RGB into CIE XYZ tristimulus values.
        brightest_green = np.max(RGB[..., 1])
        RGB = RGB / brightest_green
        RGB_e = np.reshape(RGB, (-1, 3))
        return np.reshape(np.transpose(np.dot(self.th_ccm, np.transpose(RGB_e))), RGB.shape)

    def _correct(self, XYZ:np.ndarray) -> np.ndarray:
        # adapt from the calibration illuminant (default illuminant A) to the sRGB
        # reference illuminant (default D65), convert to linear RGB, then gamma-encode to
        # sRGB. Commented out code to cross-check each result against colour-science's equivalent
        # conversion to catch regressions in colour_transforms.py.
        XYZcorrected = colour_transforms.chromatic_adaptation(XYZ)
        RGBimage = colour_transforms.XYZ_to_RGB(XYZcorrected)
        sRGBimage = colour_transforms.RGB_to_sRGB(RGBimage)
        return sRGBimage

    def process(self, RGB:np.ndarray) -> np.ndarray:
        """
        Colour correct a demosaiced RGB image from a source illuminant to a destination illuminant
        by correcting non-linearity, whitebalancing and converting to XYZ, applying chromatic adaptation
        and converting to sRGB.
        """
        RGB = self._non_linearity_correction(RGB)
        XYZ = self._to_XYZ(RGB)
        return self._correct(XYZ).astype(np.float32)
