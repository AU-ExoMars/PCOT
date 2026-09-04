#!/usr/bin/env python3
import datetime
import glob
import os

import click

from pcot.cameras import filtresponse
from pcot.cameras.filtresponse import FilterResponse
from pcot.imagecube import CannotLoadImageBadFormatException
from pcot.subcommands.subcommands import cli
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
    leftjustified: bool  # is the data left-justified if the bitdepth is not full?
    filters: dict  # a dictionary of filtername -> Filter object.

    # Each filter has a directory, which is usually named after the filter name or position.
    # This optional directory maps each filter onto the name of its directory, from either
    # the filter name or position depending on the key.
    directory_map: dict
    rawloader: object   # it's a RawLoader or None


def get_raw_loader(d):
    """This gets a RawLoader, or None. It can either build a raw loader from a preset
    or from values in the dict"""
    from pcot.dataformats.raw import RawLoader

    # all raw loader data is in 'rawloader' - this can be either 'preset' or
    # all the individual preset data elements.
    if 'rawloader' not in d:
        return None

    d = d['rawloader']

    if 'preset' in d:
        from pcot.inputs.multifile import presetModel
        preset_name = d['preset']
        try:
            preset_data = presetModel.loadPresetByName(preset_name)
            rawloader = RawLoader().deserialise(preset_data['rawloader'])
            logger.info("Using rawloader preset '%s'", preset_name)
        except KeyError:
            raise ValueError(
                f"Preset {preset_name} not found - use multifile input to make one, get one from another user, or set the rawloader directly")
    else:
        # otherwise we're using the individual elements
        rawloader = RawLoader().deserialise(d)
        logger.info("Using rawloader with parameters: %s", rawloader.dump())

    return rawloader


@cli.command(short_help="Process a YAML camera file into a PARC file")
@click.argument('yaml_filename')
@click.argument('parc_filename', required=False, default=None)
@click.option("--nocalib", is_flag=True,
              help="Do not store extra calibration data (flats, darks etc.) and add '_NOCALIB' to the camera name")
def gencam(yaml_filename, parc_filename, nocalib):
    """
    Given camera data in the current directory, create a .parc file from that data for use as camera parameter data.
    The file format is documented in the PCOT documentation, but is essentially a YAML file with a specific structure.

    YAML_FILENAME is the input YAML parameter file. PARC_FILENAME is the output PARC file; if omitted, it
    defaults to YAML_FILENAME's basename with the extension changed to .parc.
    """
    import pcot
    from pcot.cameras import camdata
    import yaml

    if parc_filename is None:
        parc_filename = os.path.splitext(os.path.basename(yaml_filename))[0] + ".parc"

    print(f"PCOT gencam generating {parc_filename} from {yaml_filename}")

    pcot.setup()
    with open(yaml_filename) as f:
        # load the YAML file and process the filter information in the "filters" key
        d = yaml.safe_load(f)
        fs = createFilters(d["filters"], d.get("filter_positions"))
        # create a new Params object and pass in the filter.
        p = camdata.CameraParams(fs)
        # Now fill in the rest of the data from the YAML file
        p.params.name = d["name"]
        if nocalib:
            logger.info("Adding _NOCALIB to camera name")
            p.params.name += "_NOCALIB"
        # this is the date that the author writes in the YAML file
        p.params.date = d["date"].strftime("%Y-%m-%d")
        # record the time that the file was compiled
        p.params.compilation_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        p.params.author = d["author"]
        p.params.description = d["description"]
        p.params.short = d["short"]
        p.params.source_filename = yaml_filename

        if "filter_aliases" in d:
            logger.error("Filter aliases are provided, but these are no longer supported (it's part of the old reflectance system")
        if "reflectance" in d:
            logger.error("Reflectance data is provided, but reflectances are now handled separately")

        # get information about any flats from the YAML. We can have the data in the YAML but disabled,
        # so flats aren't generated, but setting the "disabled" key. We can also do this by using the
        # --nocalib option, which won't save calib data AND will add "_NOCALIB" to the camera name.

        p.params.has_flats = False
        if not nocalib:
            if "flats" in d:
                logger.info("Flats section found")
                if "disabled" in d["flats"] and d["flats"]["disabled"]:
                    logger.info("Flats processing disabled by 'disabled' option in YAML file")
                else:
                    p.params.has_flats = True
        else:
            logger.info("Flats processing disabled by --nocalib option")

        # Write the parameter data to the output file.
        store = camdata.CameraData.openStoreAndWrite(parc_filename, p)
        logger.info(f"camera data written to {parc_filename}")

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
                                flatd.get("leftjustified", None),
                                fs,
                                flatd.get("directory_map", None),
                                get_raw_loader(flatd))
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

    # there's a "special" filter called "defaults" that contains default information. First we need to set
    # up defaults for this default!
    defaults_dict = {
        "transmission": 1.0,
        "order" : 1.0
    }
    # and then override it with any values in that defaults section.
    if "defaults" in filter_dict:
        defaults_dict.update(filter_dict.get("defaults", {}))
        # remove the defaults entry from the dict, so we don't consider it to be a filter
        del filter_dict["defaults"]


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
        # merge in default items
        d = dict(defaults_dict, **d)
        if position_dict:
            # if we have a position dict, use that to get the position
            if k not in position_dict:
                raise ValueError(f"Filter {k} not found in position dictionary")
            pos = position_dict[k]
        elif "position" in d:
            pos = d["position"]
        else:
            raise ValueError(f"Filter {k} does not have a position, and no position dictionary was provided")

        # do we have any response data?
        if "response" in d:
            # responses are usually percentage, but could be 0-1 if you specify false
            # here.
            response_percentage = d.get("response_percentage", True)
            # Sometimes filters have spurious high readings (e.g. G12 in the training model geology filters)
            # due to problems with the sensor switchover on certain spectrometers. To deal with this,
            # we can specify a clip value. You'll get a warning when you clip if you provide this. If you
            # don't, you'll get an error.
            response_clip_percentage = d.get("response_clip_percentage", None)
            # load the filter response from a CSV file; that will determine what kind of filter response
            # (potentially could be more complex than just wavelength,response).
            response = FilterResponse.load_from_csv(d["response"], response_percentage, response_clip_percentage)
        else:
            response = None

        f = filters.Filter(
            d["cwl"],
            d["fwhm"],
            transmission=d["transmission"],
            name=k,
            response=response,
            position=pos,
            description=d.get("description", "No description given"),
            order=d["order"])
        fs[k] = f
    return fs


def process_flats(store, data: FlatFileData):
    """
    Given the flatfield data in the YAML file, process the flatfield images and store the results in the store.
    """

    # process the filter directories, providing a callback to save the images
    def save_image(img, camera_name, filt):
        from pcot.datum import Datum
        dat = Datum(Datum.IMG, img)
        name = f"flat_{filt.name}"
        desc = f"Flatfield for {filt.name} filter, position {filt.position} in camera {camera_name}"
        store.writeDatum(name, dat, desc)

    process_filters_for_flats(save_image, data)


def get_files_for_filter(filt, data):
    """Load the files for a particular filter we need to process"""
    from pcot.datum import Datum
    from pcot.dataformats import load

    camname = data.camera_name
    # files should be in a directory named for some attribute in Filter, pretty much
    # always "name" or "position"; for example if we are using the position key, you
    # might have directories called "01", "02", "03" etc. for each filter in the camera.

    # It could be that this directory is remapped by the filter_remap dictionary, so we'll sort
    # that out first.

    filter_dir_name = getattr(filt, data.key)   # get the position/name of the filter
    if data.directory_map is not None:
        # if the filter is remapped, use the remapped name as the directory name
        if filter_dir_name not in data.directory_map:
            raise ValueError(f"Filter {filter_dir_name} not found in filter_remap dictionary")
        filter_dir_name = data.directory_map[filter_dir_name]

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

    try:
        cube = load.multifile(dirpath, list_of_files, bitdepth=data.bitdepth, filterpat=".*",
                              camera=None, really_no_camera=True,leftjustified=data.leftjustified,
                              rawloader=data.rawloader).get(Datum.IMG)
    except CannotLoadImageBadFormatException as e:
        raise Exception(f"Cannot load an image due to a bad format extension - should you be using a rawloader?")

    if cube is None:
        raise ValueError(f"Failed to load files from {dirpath}: {list_of_files}")
    return cube


def process_filters_for_flats(callback, data: FlatFileData):
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
        cube = get_files_for_filter(filt, data)

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
