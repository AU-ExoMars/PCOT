import numpy as np

from ..dataproduct import DataProduct
from ..mixins import ApplicableCameraMixin, SortByStartTimeMixin
from . import PANCAM_META_MAP


class Observational(
    ApplicableCameraMixin, SortByStartTimeMixin, DataProduct, abstract=True
):
    _META_MAP = PANCAM_META_MAP


class Observation(Observational, type_name="observation"):
    """PAN-PP-200"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.sl is not None:
            self.data = self.sl["SCIENCE_IMAGE_DATA"].data
        else:
            self.data = None  # TODO: data blanks from Template def


class SpecRad(Observational, type_name="spec-rad"):
    """PAN-PP-220"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.sl is not None:
            self.data: np.ndarray = self.sl["DATA"].data
            self.dq: np.ndarray = self.sl["QUALITY"].data
            self.err: np.ndarray = self.sl["UNCERTAINTY"].data
        else:
            self.data: np.ndarray = None  # TODO: data blanks from Template defs


class AppCol(Observational, type_name="app-col"):
    """PAN-PP-221"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.sl is not None:
            self.data: np.ndarray = self.sl["DATA"].data
            self.dq: np.ndarray = self.sl["QUALITY"].data
            self.err: np.ndarray = self.sl["UNCERTAINTY"].data
        else:
            self.data: np.ndarray = None  # TODO: data blanks from Template defs