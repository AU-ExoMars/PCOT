from ..dataproduct import DataProduct

PANCAM_META_MAP = {
    **DataProduct._META_MAP,
    "acq_desc": ".//emrsp_rm_pan:Acquisition_Identification/emrsp_rm_pan:acquisition_type_description",
    "acq_id": (
        ".//emrsp_rm_pan:Acquisition_Identification/emrsp_rm_pan:acquisition_type_id"
    ),
    "acq_name": (
        ".//emrsp_rm_pan:Acquisition_Identification/emrsp_rm_pan:acquisition_type_name"
    ),
    "camera": ".//psa:Sub-Instrument/psa:identifier",  # convenience alias
    "exposure_duration": ".//img:Exposure/img:exposure_duration",
    "filter": ".//img:Optical_Filter/img:filter_number",  # convenience alias
    "filter_num": ".//img:Optical_Filter/img:filter_number",
    "filter_bw": ".//img:Optical_Filter/img:bandwidth",
    "filter_cwl": ".//img:Optical_Filter/img:center_filter_wavelength",
    "filter_id": ".//img:Optical_Filter/img:filter_id",
    "filter_name": ".//img:Optical_Filter/img:filter_name",
    "model": (
        ".//img_surface:Instrument_Information/img_surface:instrument_version_number"
    ),
    "rmc_ptu": (
        ".//geom:Motion_Counter_Index[geom:index_id='MAST/PTU']/geom:index_value_number"
    ),
    "seq_img_num": ".//emrsp_rm_pan:Acquisition_Identification/emrsp_rm_pan:acquisition_sequence_image_number",
    "seq_num": ".//emrsp_rm_pan:Acquisition_Identification/emrsp_rm_pan:acquisition_sequence_number",
    "sol_id": ".//emrsp_rm_pan:Acquisition_Identification/emrsp_rm_pan:sol_id",
    "sub_instrument": ".//psa:Sub-Instrument/psa:identifier",
    "subframe_y": ".//img:Subframe/img:first_line",
    "subframe_x": ".//img:Subframe/img:first_sample",
}

from .ancillary import RadFlatPrm, RadColPrm, RadSsrPrm
from .observational import Observation, SpecRad, AppCol