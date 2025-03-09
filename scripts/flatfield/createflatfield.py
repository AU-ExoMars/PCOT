"""
New version of flatfield generator
"""

import argparse
import glob
import os
import numpy as np
import logging

import pcot
from pcot.dataformats import load
from pcot.dataformats.raw import RawLoader
from pcot.datum import Datum
from pcot.imagecube import ImageCube
from pcot import dq

logger = logging.getLogger(__name__)

parser = argparse.ArgumentParser(description="Create flatfields from collated data directories")

parser.add_argument("input",metavar="INPUT_DIRECTORY",type=str,help="Directory output by collate_flats")
parser.add_argument("camera",metavar="CAMERA",type=str,help="Name of camera")

args = parser.parse_args()



format=".bin"

# set up a raw loader
loader = RawLoader(format=RawLoader.UINT16,width=1024,height=1024,bigendian=True,
    rot=90,offset=48)




# Do this first so we can load the camera
pcot.setup()


def get_files_for_filter(camera_name, filter, directory):
    """Load the files for a particular filter we need to process"""
    images = []
    dirpath = os.path.join(directory,filter.position)
    files = glob.glob(os.path.join(dirpath,f"*{format}"))
    list_of_files = [os.path.basename(x) for x in files]

    # load all the files. We're not concerned about filter here, so set that to a "don't care"
    # value.
    
    cube = load.multifile(dirpath,list_of_files,bitdepth=10,filterpat=".*",
        camera=camera_name,
        rawloader=loader).get(Datum.IMG)
    return cube
        
        
def process_filters(camera_name, directory, callback):
    """Process each filter in the camera, given the name of the camera and 
    the top level directory (as passed to collate_flats). Then call
    the callback function with the created image and filter."""
    
    camera = pcot.cameras.getCamera(camera_name)
    for k,filt in camera.params.filters.items():
        logger.info(f"Loading files for {k}/{filt.position}")

        # load the files into a single big ImageCube
        cube = get_files_for_filter(camera_name,filt,directory)

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
        nans = np.count_nonzero(np.isnan(mean))
        
        # combine all the band DQ together - will likely result in zero because there
        # should be no DQ bits set yet.
        dqs = np.bitwise_or.reduce(cube.dq,axis=2,dtype=np.uint16)
        
        # OR in a SAT bit for each saturated pixel
        dqs |= np.where(np.isnan(mean),dq.SAT,0).astype(np.uint16)
        
        # reset that saturated pixel to zero.
        mean = np.nan_to_num(mean,nan=0).astype(np.float32)
        print(f"{filt.position} has {np.count_nonzero(dqs&dq.SAT)} pixels saturated in all images")
        
        # now we have to process uncertainty. There is no uncertainty in each input channel,
        # so we just need to calculate the SD across the input pixels for the masked
        # data. If all the bands were saturated we set this to zero.
        sd = masked.std(axis=2).filled(0).astype(np.float32)
        
        # build the resulting image
        res = ImageCube(mean, uncertainty=sd, dq=dqs)
        
        callback(res,camera_name,filt)
        
        

def save_image_to_parc(img, camera_name, filt):
    name = f"{camera_name}_{filt.position}_flat.parc"
    img.save(name,name="main")
    logger.info(f"Image saved to {name}")

    

process_filters(args.camera,args.input,save_image_to_parc)
    



