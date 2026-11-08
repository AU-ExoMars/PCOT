from typing import Optional

from pcot.cameras.filters import Filter
from pcot.datum import Datum
from pcot.sources import nullSourceSet, MultiBandSource, Source
from pcot.utils import Result
from pcot.value import Value


def _markAsCalibrationSource(source: Source):
    """Mark a source from the calibration data as secondary, keeping any existing purpose
    (e.g. "reflectance target") so we know where it came from."""
    if source.secondary_name:
        source.setSecondaryName(f"calibration data ({source.secondary_name})")
    else:
        source.setSecondaryName("calibration data")


def apply(calibd: Optional[Datum], imgd: Optional[Datum]) -> Result[Datum]:
    """
    Apply a CalibrationData to an image, returning a new image with appropriate sources:
    each band has the image's sources for that band plus the calibration data's sources
    for that filter, marked as secondary.

    Bands are matched to the calibration by filter name, so the image can have fewer bands than the
    calibration data, or have them in a different order. Unlike most operations, the whole image is
    calibrated even if it has ROIs - otherwise only the ROIs would be. The ROIs are kept in the result.

    Returns a Result which is either an error (with a message) or success with an image Datum.
    """
    from pcot.calib.fit import CalibrationData
    from pcot.imagecube import ImageCube

    if imgd is None or imgd.isNone():
        return Result.error("No image provided")
    img: ImageCube = imgd.get(Datum.IMG)

    if calibd is None or calibd.isNone():
        return Result.error("No calibration data provided")
    calib: CalibrationData = calibd.get(Datum.CALIBRATION)

    if not calib.filters or not calib.fits:
        return Result.error("Calibration data has no fits")
    missing = calib.missingFits()
    if missing:
        return Result.error(f"Calibration data has no fit for filters {', '.join(missing)}")

    # The calibration data's sources should have one set per filter, in the same order as calib.filters
    # (they are the sources of the bands in the image the calibration was made from).

    if not isinstance(calibd.sources, MultiBandSource):
        return Result.error(f"Calibration data has no multi-band source data ({type(calibd.sources)})")
    if len(calibd.sources.sourceSets) != len(calib.filters):
        return Result.error(f"Calibration data has {len(calib.filters)} filters but "
                            f"{len(calibd.sources.sourceSets)} source sets")

    # copy and mark calibration data sources as secondary.
    csources = calibd.sources.copy().visit(
        lambda sourceSet: sourceSet.visit(_markAsCalibrationSource))

    # we need to create a pair of vectors m,c from the calibration data which match the
    # order of bands in the input. We also combine the image and calibration source data
    # as we go.

    m = []
    sdm = []
    c = []
    sdc = []
    sources = []
    for i in range(img.channels):
        f: Filter = img.filter(i)
        if f is None:
            return Result.error(f"Band {i} in image does not have a filter (or has more than one)")
        if f.name not in calib.filters:
            return Result.error(f"Band {i} (filter {f.name}) is not in the calibration data")
        fit = calib.fits[f.name]
        m.append(fit.m)
        sdm.append(fit.sdm)
        c.append(fit.c)
        sdc.append(fit.sdc)

        imsrcset = img.sources.sourceSets[i]
        # get index of filter in calibration filter list
        cidx = calib.filters.index(f.name)
        combined = imsrcset.copy().add(csources.sourceSets[cidx])
        sources.append(combined)

    # we're going to overwrite the image sources anyway, so this is OK.
    mval = Datum(Datum.NUMBER, Value(m, sdm), sources=nullSourceSet)
    cval = Datum(Datum.NUMBER, Value(c, sdc), sources=nullSourceSet)

    # Image arithmetic only operates inside an image's ROIs (if it has any), but we want to calibrate
    # the whole image. So do the maths on a shallow copy with no ROIs (sharing the pixel data, which the
    # arithmetic doesn't change), then put the ROIs back on the result.
    noroi = img.shallowCopy()
    noroi.rois = []
    res = (Datum(Datum.IMG, noroi) - cval) / mval  # do the actual op. with datum maths
    cube = res.get(Datum.IMG)
    cube.rois = img.rois.copy()

    # The arithmetic gives us a new ImageCube, so we can replace its sources directly.
    # Note that we set them on the cube, not the Datum - an image Datum doesn't own its sources, and
    # setting them there raises ImageDatumSourcesException.
    cube.sources = MultiBandSource(sources)

    return Result.success(res)
