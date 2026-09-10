import numpy as np

# https://en.wikipedia.org/wiki/Standard_illuminant#D65_values
# This is the default destination illuminant
cie_illuminant_RGB_D65_chromacity = [0.31272, 0.32903]

# https://en.wikipedia.org/wiki/Standard_illuminant#Illuminant_A - a
# tungsten filament light.
# Not used by default - kept in case we need to switch back.
cie_illuminant_a_chromacity = np.array([0.44758, 0.40745])

# xy chromaticity of a 2700K blackbody (colour.temperature.CCT_to_xy(2700) in the
# Colour Science library), matching the MSSL Tungsten Halogen lamp's rated CCT.
# This is the source illuminant used in the HRC colour correction recipe, chosen
# deliberately over the canonical Illuminant A chromacity above.
# This is the default source illuminant
cie_illuminant_th_2700k_chromacity = np.array([0.45381618, 0.40960506])

# XYZ to LMS (cones) model. colour_science uses the CIECAM02 matrix, so
# we'll also use it for consistency.
# https://en.wikipedia.org/wiki/LMS_color_space#Later_CIECAMs
XYZ_to_LMS_transform = np.array([
    [0.7328, 0.4296, -0.1624],
    [-0.7036, 1.6975, 0.0061],
    [0.0030, 0.0136, 0.9834],
])

# XYZ to RGB model, https://en.wikipedia.org/wiki/SRGB#Primaries
XYZ_to_RGB_transform = np.array([
    [3.2406255, -1.5372080, -0.4986286],
    [-0.9689307, 1.8757561, 0.0415175],
    [0.0557101, -0.2040211, 1.0569959]
])


def vecmul(m, v):
    """ Each row of m is a vector. v is an X*Y matrix of vectors, each of
        which is m.shape[1] long. The returned matrix will be an X*Y matrix
        of vectors, each of which is m.shape[0] long. The component at
        position N of each vector is the dot product of m[N,:] and v[X,Y]

        In the case where m only has one row, the vectors in the
        resulting matrix get collapsed to scalars.

        In imaging terms, for pixels with three components, I guess it
        makes sense for m to have either 1 or 3 rows. For 1 row, you're
        effectively doing a greyscale conversion. For 3 rows, you're
        doing a colourspace conversion (e.g. between RGB and YUV).

        It's taken a lot for me to gain confidence in my understanding
        of what this is doing, since it's using deep numpy magic to let
        it be done quickly.

        This implementation is taken more or less verbatim from colour_science.
        I may well change it at some point, because I *really* don't like the magic.
    """
    return np.matmul(m, v[..., None]).squeeze(-1)


def chromacityXY_to_tristimulusXYZ(x, y):
    """ Convert from chromacity (x, y) to (x, y, z) tristimulus values,
        where we normalise such that the Y tristimulus value is 1.
        https://en.wikipedia.org/wiki/CIE_1931_color_space#CIE_xyY_color_space
    """
    if y == 0:
        # Have to play nicely when y is 0.
        return np.array([0, 0, 0])

    return np.array([
        x / y,
        1,
        (1 - x - y) / y
    ])


def von_kries(XYZ, src_tristimulus, dst_tristimulus):
    """ The Von Kries chromatic adaptation method.
        https://en.wikipedia.org/wiki/Chromatic_adaptation#Von_Kries_transform
    """

    # Transform both tristimulus values into LMS space.
    LMS1 = vecmul(XYZ_to_LMS_transform, src_tristimulus)
    LMS2 = vecmul(XYZ_to_LMS_transform, dst_tristimulus)

    # Construct the diagonal matrix.
    D = np.zeros((3, 3))
    if LMS1[0] != 0:
        D[0, 0] = LMS2[0] / LMS1[0]
    if LMS1[1] != 0:
        D[1, 1] = LMS2[1] / LMS1[1]
    if LMS1[2] != 0:
        D[2, 2] = LMS2[2] / LMS1[2]

    # Construct the transformation matrix - into LMS space,
    # Von Kries scaling and back out to XYZ space. See e.g.
    # https://ics.uci.edu/~majumder/vispercep/paper08/colorappearance.pdf
    transform = np.matmul(np.linalg.inv(XYZ_to_LMS_transform), D)
    transform = np.matmul(transform, XYZ_to_LMS_transform)

    # And finally apply the transform to the XYZ image.
    return vecmul(transform, XYZ)


def chromatic_adaptation(XYZimage, src_illuminant=None, dst_illuminant=None):
    """Perform chromatic adaptation of XYZimage from the specified chromacity to RGB. """

    if src_illuminant is None:
        src_illuminant = cie_illuminant_th_2700k_chromacity
    if dst_illuminant is None:
        dst_illuminant = cie_illuminant_RGB_D65_chromacity

    # Convert our two illuminant chromacities to tristimulus values.
    src_tristimulus = chromacityXY_to_tristimulusXYZ(*src_illuminant)
    dst_tristimulus = chromacityXY_to_tristimulusXYZ(*dst_illuminant)

    # Do the Von Kries transform to convert between illuminants.
    return von_kries(XYZimage, src_tristimulus, dst_tristimulus)


def XYZ_to_RGB(XYZimage):
    """ CIE XYZ to RGB, https://en.wikipedia.org/wiki/SRGB#Primaries """
    return vecmul(XYZ_to_RGB_transform, XYZimage)


def RGB_to_sRGB(RGBimage):
    """ Apply the RGB to sRGB formula - https://en.wikipedia.org/wiki/SRGB """

    # Since np.where will evaluate np.power(RGBimage) over the whole matrix,
    # it will raise warnings for values below zero. The warnings are
    # harmless, since they result in nan in the result, only for entries
    # not selected by np.where. So we *could* just suppress the warning. But
    # I don't much like that approach. Instead, we'll clip before
    # evaluating - we'd want the result to be in the [0, 1] range anyway,
    # so if we don't clip before, we'd need to clip afterwards, somewhere.
    RGBimage = np.clip(RGBimage, 0, 1)
    return np.where(RGBimage <= 0.0031308, RGBimage * 12.92, 1.055 * np.power(RGBimage, 1 / 2.4) - 0.055)

