#!/usr/bin/env python3
import glob
import os

from pcot.subcommands import subcommand, argument
from dataclasses import dataclass
import logging
logger = logging.getLogger(__name__)

@dataclass
class FlatFileData:
    """Data class to hold various common parameters as we chuck them down the stack."""

    params: 'CameraParams'
    directory: str
    extension: str
    preset: str
    bitdepth: int


@subcommand([
    argument('params', type=str, metavar='YAML_FILENAME', help="Input YAML file with parameters"),
    argument('output', type=str, metavar='PARC_FILENAME', help="Output PARC filename"),
],
    shortdesc="Process a YAML camera file into a PARC file")
def gencam(args):
    """
    Given camera data in the current directory, create a .parc file from that data for use as camera parameter data.
    The file format is documented in the PCOT documentation, but is essentially a YAML file with a specific structure.
    """
    import pcot
    from pcot.cameras import camdata
    import yaml

    pcot.setup()
    with open(args.params) as f:
        # load the YAML file and process the filter information in the "filters" key
        d = yaml.safe_load(f)
        fs = createFilters(d["filters"])
        # create a new Params object and pass in the filter.
        p = camdata.CameraParams(fs)
        # Now fill in the rest of the data from the YAML file
        p.params.name = d["name"]
        p.params.date = d["date"].strftime("%Y-%m-%d")
        p.params.author = d["author"]
        p.params.description = d["description"]
        p.params.short = d["short"]
        # Write the parameter data to the output file.
        store = camdata.CameraData.openStoreAndWrite(args.output, p)

        # get information about any flats from the YAML
        if "flats" in d:
            flatd = d["flats"]
            data = FlatFileData(p, flatd["directory"], flatd["extension"],
                                flatd.get("preset", None), flatd.get("bitdepth", None))
            process_flats(store, data)


def createFilters(filter_dicts):
    """
    Given the filter data in the YAML file, create a dictionary of Filter objects keyed by the filter name.
    """
    from pcot.cameras import filters
    fs = {}
    for k, d in filter_dicts.items():
        f = filters.Filter(
            d["cwl"],
            d["fwhm"],
            transmission=d.get("transmission", 1.0),
            name=k,
            position=d.get("position", k))
        fs[k] = f
    return fs


def process_flats(store, data: FlatFileData):
    """
    Given the flatfield data in the YAML file, process the flatfield images and store the results in the store.

    """

    # first, if there is a flat preset, load it
    if data.preset is not None:
        from pcot.inputs.multifile import presetModel
        from pcot.ui.presetmgr import PresetOwner
        from pcot.dataformats.raw import RawLoader

        class Preset(PresetOwner):
            """Minimal preset owner class to hold the rawloader preset"""
            def applyPreset(self, preset):
                self.rawloader = RawLoader()
                self.rawloader.deserialise(preset['rawloader'])
        # create the minimal preset owner, the thing which has presets applied to it
        preset = Preset()
        # pull the preset from the model and apply it to the preset owner
        preset.applyPreset(presetModel.presets[data.preset])
    else:
        preset = None

    # process the filter directories, providing a callback to save the images
    def save_image(img, camera_name, filt):
        from pcot.datum import Datum
        dat = Datum(Datum.IMG, img)
        name = f"flat_{filt.name}"
        desc = f"Flatfield for {filt.name} filter, position {filt.position} in camera {camera_name}"
        store.writeDatum(name, dat, desc)

    process_filters_for_flats(save_image, preset.rawloader, data)


def get_files_for_filter(filt, rawloader, data):
    """Load the files for a particular filter we need to process"""
    from pcot.datum import Datum
    from pcot.dataformats import load

    camname = data.params.params.name
    dirpath = os.path.join(os.path.expanduser(data.directory), filt.position)
    globpath = os.path.join(dirpath, f"*.{data.extension}")
    logger.debug(f"Camera {camname}, filter {filt.name}/{filt.position}")
    logger.debug(f"Looking for files in {globpath}")
    files = glob.glob(globpath)
    list_of_files = [os.path.basename(x) for x in files]
    logger.debug(f"Found {len(list_of_files)} files")

    # load all the files. We're not concerned about filter here, so set that to a "don't care"
    # value.

    cube = load.multifile(dirpath, list_of_files, bitdepth=data.bitdepth, filterpat=".*",
                          camera=camname,
                          rawloader=rawloader).get(Datum.IMG)
    if cube is None:
        raise ValueError(f"Failed to load files from {dirpath}: {list_of_files}")
    return cube


def process_filters_for_flats(callback, rawloader, data: FlatFileData):
    """Process each filter in the camera, given the name of the camera and
    the top level directory (as passed to collate_flats). Then call
    the callback function with the created image and filter."""

    import numpy as np
    import pcot
    from pcot import dq
    from pcot.imagecube import ImageCube

    camera_name = data.params.params.name
    camera = pcot.cameras.getCamera(camera_name)
    for k, filt in camera.params.filters.items():
        logger.info(f"Loading files for {k}/{filt.position}")

        # load the files into a single big ImageCube
        cube = get_files_for_filter(filt, rawloader, data)

        # clear all the NOUNCERTAINTY bits
        cube.dq &= ~dq.NOUNCERTAINTY

        # find the saturated pixels
        satPixels = cube.img == 1.0
        min = np.min(cube.img)
        max = np.max(cube.img)
        logger.debug(f"{np.count_nonzero(satPixels)} saturated pixels, range {min}-{max}")

        # create a masked array, without the saturated pixels
        masked = np.ma.masked_array(cube.img, satPixels)
        min = np.min(masked)
        max = np.max(masked)
        logger.debug(f"masked range {min}-{max}")

        # find the mean across the different images, disregarding saturated pixels.
        # When the pixels were saturated across all input images there's absolutely
        # nothing we can do. In this case set them to zero and set SAT in the result DQ.

        mean = masked.mean(axis=2).filled(np.nan)

        # combine all the band DQ together - will likely result in zero because there
        # should be no DQ bits set yet.
        dqs = np.bitwise_or.reduce(cube.dq, axis=2, dtype=np.uint16)

        # OR in a SAT bit for each saturated pixel
        dqs |= np.where(np.isnan(mean), dq.SAT, 0).astype(np.uint16)

        # reset that saturated pixel to zero.
        mean = np.nan_to_num(mean, nan=0).astype(np.float32)
        print(f"{filt.position} has {np.count_nonzero(dqs & dq.SAT)} pixels saturated in all images")

        # now we have to process uncertainty. There is no uncertainty in each input channel,
        # so we just need to calculate the SD across the input pixels for the masked
        # data. If all the bands were saturated we set this to zero.
        sd = masked.std(axis=2).filled(0).astype(np.float32)

        # build the resulting image
        res = ImageCube(mean, uncertainty=sd, dq=dqs)

        callback(res, camera_name, filt)
