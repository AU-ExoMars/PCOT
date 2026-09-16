import numpy as np

ILLUMINANTS = {
    # https://en.wikipedia.org/wiki/Standard_illuminant#D65_values
    # This is the default destination illuminant
    "D65 (daylight)":  np.array([0.31272, 0.32903]),
    # https://en.wikipedia.org/wiki/Standard_illuminant#Illuminant_A - a
    # tungsten filament light.
    "Illuminant A (tungsten)": np.array([0.44758, 0.40745]),
    "2700K black body": np.array([0.45381618, 0.40960506])
}

DEFAULT_SRC_ILLUMINANT = "D65 (daylight)"
DEFAULT_DEST_ILLUMINANT = "D65 (daylight)"

# these are the names of the non-linearity correction splines and offsets for cameras/illuminants for
# different values taken by XFormColourCorrect
NON_LINEARITY_SPLINES = {
    "AUPE/Daylight" : None,  # AUPE is linear
    "HRC/Tungsten" : "pc_th_spl_o.npz"      # PC,TH = Pancam,Tungsten Halogen
}

# Similar for CCMs
COLOUR_CORRECTION_MATRICES = {
    "AUPE/Daylight": "ae_dl_ccm.csv",       # AE,DL = AUPE,Daylight
    "HRC/Tungsten": "pc_th_ccm.csv"
}

DEFAULT_SRC_CAMERA_SCENE = "AUPE/Daylight"

