#!/usr/bin/env python3
import datetime
import glob
import os

from pcot.subcommands import subcommand, argument
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class FlatFileData:
    """Data class to hold various common parameters as we chuck them down the stack."""

    camera_name: str  # camera name
    directory: str  # directory to find the files
    extension: str  # png/bin typically
    key: str  # either "name" or "position" - used to look up which filter we are adding data for
    preset: str  # if loading raw binary files, the multifile loader preset to use
    bitdepth: int  # how many bits are used; we scale the data according to this
    filters: dict  # a dictionary of filtername -> Filter object.


@subcommand([
    argument('params', type=str, metavar='YAML_FILENAME', help="Input YAML file with parameters"),
    argument('output', type=str, metavar='PARC_FILENAME', help="Output PARC filename"),
    argument("--nocalib",
             help="Do not store extra calibration data (flats, darks etc.) and add '_NOCALIB' to the camera name",
             action="store_true")
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
        fs = createFilters(d["filters"], d.get("filter_positions"))
        # create a new Params object and pass in the filter.
        p = camdata.CameraParams(fs)
        # Now fill in the rest of the data from the YAML file
        p.params.name = d["name"]
        if args.nocalib:
            logger.info("Adding _NOCALIB to camera name")
            p.params.name += "_NOCALIB"
        # this is the date that the author writes in the YAML file
        p.params.date = d["date"].strftime("%Y-%m-%d")
        # record the time that the file was compiled
        p.params.compilation_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        p.params.author = d["author"]
        p.params.description = d["description"]
        p.params.short = d["short"]
        p.params.source_filename = args.params

        # Sometimes the reflectance data refers to filters by other names. We deal with that here
        # by providing a dictionary of aliases to filter names.
        filter_aliases = {}
        if "filter_aliases" in d:
            logger.info("Filter aliases found")
            for alias, filtername in d["filter_aliases"].items():
                filter_aliases[alias] = filtername

        # there may be a section on reflectances - this will be a dictionary of calibration
        # target names to filenames holding the reflectances for that target.
        p.reflectances = {}
        if "reflectance" in d:
            logger.info("reflectance section found")
            p.params.has_reflectances = True
            for target, filename in d["reflectance"].items():
                logger.info(f"Processing reflectance data for {target}")
                # we pass in the filters so we can check they exist when referred to in the reflectance data.
                # We store the resulting dict in the CameraParams object.
                p.reflectances[target] = process_reflectance(filename, fs, filter_aliases)
                logger.info(f"Reflectance data for {target} is {p.reflectances[target]}")

        # get information about any flats from the YAML. We can have the data in the YAML but disabled,
        # so flats aren't generated, but setting the "disabled" key. We can also do this by using the
        # --nocalib option, which won't save calib data AND will add "_NOCALIB" to the camera name.

        p.params.has_flats = False
        if not args.nocalib:
            if "flats" in d:
                logger.info("Flats section found")
                if "disabled" in d["flats"] and d["flats"]["disabled"]:
                    logger.info("Flats processing disabled by 'disabled' option in YAML file")
                else:
                    p.params.has_flats = True
        else:
            logger.info("Flats processing disabled by --nocalib option")

        # Write the parameter data to the output file.
        store = camdata.CameraData.openStoreAndWrite(args.output, p)
        logger.info(f"camera data written to {args.output}")

        # Now we can process the flats, if they are enabled and present. We have to do this after opening
        # the store and writing the initial data.

        if p.params.has_flats:
            logger.info("Processing flats")
            flatd = d["flats"]
            data = FlatFileData(p.params.name,
                                flatd["directory"],
                                flatd["extension"],
                                flatd["key"],       # "name" or "position"
                                flatd.get("preset", None),
                                flatd.get("bitdepth", None),
                                fs)
            process_flats(store, data)
            logger.info("Flats processing complete")
        else:
            logger.info("Flats processing disabled by --nocalib option")


def createFilters(filter_dict, position_dict=None):
    """
    Given the filter data in the YAML file, create a dictionary of Filter objects keyed by the filter name.
    Position data can be specified either by a "position: name" in an optional "filter_positions" dict, or
    directly in the filter (for legacy). If the position dict is present, the filter dict must not contain
    position entries. If there are position entries, there must be no position dict.
    """
    from pcot.cameras import filters

    # we need to reverse the position dictionary from position:name to name:position
    if position_dict is not None:
        # check that the filter_dict does not contain position entries
        for k, d in filter_dict.items():
            if "position" in d:
                raise ValueError(f"Filter {k} has a position entry but position_dict is also provided")
        # reverse the position dict
        position_dict = {v: k for k, v in position_dict.items()}
    fs = {}  # the output dictionary of Filter objects
    for k, d in filter_dict.items():
        if position_dict:
            # if we have a position dict, use that to get the position
            if k not in position_dict:
                raise ValueError(f"Filter {k} not found in position dictionary")
            pos = position_dict[k]
        elif "position" in d:
            pos = d["position"]
        else:
            raise ValueError(f"Filter {k} does not have a position, and no position dictionary was provided")
        f = filters.Filter(
            d["cwl"],
            d["fwhm"],
            transmission=d.get("transmission", 1.0),
            name=k,
            position=pos,
            description=d.get("description", "No description given"))
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
        try:
            preset.applyPreset(presetModel.presets[data.preset])
            rawloader = preset.rawloader
        except KeyError:
            raise ValueError(
                f"Preset {data.preset} not found - use multifile input to make one, or get one from another user")
    else:
        rawloader = None

    # process the filter directories, providing a callback to save the images
    def save_image(img, camera_name, filt):
        from pcot.datum import Datum
        dat = Datum(Datum.IMG, img)
        name = f"flat_{filt.name}"
        desc = f"Flatfield for {filt.name} filter, position {filt.position} in camera {camera_name}"
        store.writeDatum(name, dat, desc)

    process_filters_for_flats(save_image, rawloader, data)


def get_files_for_filter(filt, rawloader, data):
    """Load the files for a particular filter we need to process"""
    from pcot.datum import Datum
    from pcot.dataformats import load

    camname = data.camera_name
    # files should be in a directory named for some attribute in Filter, pretty much
    # always "name" or "position"
    filter_dir_name = getattr(filt, data.key)
    # build the full directory path
    dirpath = str(os.path.join(os.path.expanduser(data.directory), filter_dir_name))
    globpath = os.path.join(dirpath, f"*.{data.extension}")
    logger.debug(f"Camera {camname}, filter {filt.name}/{filt.position}")
    logger.debug(f"Looking for files in {globpath}")
    files = glob.glob(globpath)
    list_of_files = [os.path.basename(x) for x in files]
    logger.debug(f"Found {len(list_of_files)} files")

    # load all the files. We're not concerned about filter here, so set that to a "don't care"
    # value.

    cube = load.multifile(dirpath, list_of_files, bitdepth=data.bitdepth, filterpat=".*",
                          camera=None, really_no_camera=True,
                          rawloader=rawloader).get(Datum.IMG)
    if cube is None:
        raise ValueError(f"Failed to load files from {dirpath}: {list_of_files}")
    return cube


def process_filters_for_flats(callback, rawloader, data: FlatFileData):
    """Process each filter in the camera, given the name of the camera and
    the top level directory (as passed to collate_flats). Then call
    the callback function with the created image and filter."""

    import numpy as np
    from pcot import dq
    from pcot.imagecube import ImageCube

    for k, filt in data.filters.items():
        debug_name = f"{k} (position {filt.position})"
        logger.info(f"Loading files for {debug_name}")

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
        logger.info(f"{filt.position} has {np.count_nonzero(dqs & dq.SAT)} pixels saturated in all images")

        # Divide by the mean of the flatfield image
        if False:
            # Note - we're NOT doing this - it should be combined with the darkfield image;
            # in any case we can do it downstream in a node.
            mm = np.mean(mean)
            logger.info(f"Flatfield mean is {mm}")
            if mm > 0:
                mean /= mm
            else:
                logger.warning(f"Filter {debug_name} has no non-saturated or non-zero pixels")
        else:
            mm = 1.0

        logger.info(f"Flatfield for {debug_name} range is {np.min(mean)}-{np.max(mean)}")
        # now we have to process uncertainty. There is no uncertainty in each input channel,
        # so we just need to calculate the SD across the input pixels for the masked
        # data. If all the bands were saturated we set this to zero.
        sd = masked.std(axis=2).filled(0).astype(np.float32)
        # and we'll need to divide the SD by the mean too.
        sd /= mm

        # build the resulting image
        res = ImageCube(mean, uncertainty=sd, dq=dqs)

        callback(res, data.camera_name, filt)


def process_reflectance(filename, filters: dict, filter_aliases: dict):
    """Process the reflectance data for a particular calibration target, given the filename of the data."""

    with open(filename) as f:
        # this is a CSV file with four fields: patch, filter, reflectance, uncertainty.
        # We'll read this in and create a dictionary of filter -> reflectance data.
        import csv
        reader = csv.DictReader(f)
        data = {}
        for row in reader:
            patch = row["ROI"]
            filt = row["filter"]
            if filt not in filters:
                # if the filter isn't in the filters dictionary, we may have an alias for it
                if filt in filter_aliases:
                    filt = filter_aliases[filt]
                else:
                    raise ValueError(f"In reflectance file {filename}: '{filt}' not found in filter list and no alias found")
            refl = float(row["n"])
            unc = float(row["u"])
            if patch not in data:
                data[patch] = {}
            data[patch][filt] = (refl, unc)

    return data
