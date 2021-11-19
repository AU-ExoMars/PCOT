import os
from pds4_tools.reader.label_objects import Label

from dataclasses import dataclass

@dataclass(frozen=true)
class LabelData:
    """Abbreviated PDS4 label data with link to original file"""
    path: str       # path of original label
    inst: str       # instrument (camera)
    typeId: str     # acq type id
    sol: int        # sol
    seq: int        # sequence number

@dataclass(frozen=true)
class LabelDataImage:
    ivn: float      # index value number for motion counter
    cwl: float      # filter CWL
    fid: str        # filter ID


def getLabelsFromDirectory(d):
    """Read all labels (XML files) in a directory recursively"""
    for root, subdirs, files in os.walk(d):
        for file in files:
            _, ext = os.path.splitext(file)
            if ext == '.xml':
                f = os.path.join(root, file)
                lab = Label.from_file(f)
                comp = lab.find(".//Observing_System/name")
                if comp is not None and "PanCam" in comp.text:
                    typeId = lab.find(".//emrsp_rm_pan:acquisition_type_id").text
                    inst = lab.find(".//psa:Sub-Instrument/psa:identifier").text
                    sol = lab.find(".//emrsp_rm_pan:sol_id").text
                    seq = lab.find(".//emrsp_rm_pan:acquisition_sequence_number").text
                    ivn = lab.find(".//geom:Motion_Counter_Index[geom:index_id='MAST/PTU']/geom:index_value_number").text
                    filt = lab.find(".//img:center_filter_wavelength").text
                    filtId = lab.find(".//img:filter_id").text

                    d = LabelDataImage(f, cam, typeId, sol, seq, ivn, filt, filtId)