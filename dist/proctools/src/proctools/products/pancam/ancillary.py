from ..adapters import KeyTable, MultiData
from ..dataproduct import DataProduct
from ..mixins import ApplicableCameraMixin
from . import PANCAM_META_MAP


class Ancillary(ApplicableCameraMixin, DataProduct, abstract=True):
    _META_MAP = PANCAM_META_MAP


class RadFlatPrm(Ancillary, type_name="rad-flat-prm"):
    """PAN-CAL-126"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.sl is not None:
            if self.meta.camera == "HRC":
                self.data = self.sl["DATA"].data
            else:
                self.data = MultiData(self.sl, "DATA_{:02d}")
        else:
            self.data = None  # TODO: data blank from Template def


class RadSsrPrm(Ancillary, type_name="rad-ssr-prm"):
    """PAN-CAL-127"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.sl is not None:
            self.data = KeyTable(self.sl["TABLE"], key_field="filter")
        else:
            self.data = None  # TODO: data blank from Template def


class RadColPrm(Ancillary, type_name="rad-col-prm"):
    """PAN-CAL-129"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # FIXME: change adapter once product has been properly defined...
        if self.sl is not None:
            self.wb = KeyTable(self.sl["TABLE_WHITE_BALANCE"], key_field="filter")
        else:
            self.wb = None  # TODO: data blank from Template def
