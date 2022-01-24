from .adapters import KeyTable, MultiData
from .dataproduct import DataProduct
from .mixins import ApplicableCameraMixin, SortByStartTimeMixin
from .loader import ProductLoader as _Loader
from .util import BayerSlice, get_md5sum

# register subclasses automatically for now
# can revisit if we ever need to support other instruments
from . import pancam

loader = _Loader()
