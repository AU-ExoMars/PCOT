try:
    import typer as _
except ImportError:
    import logging

    log = logging.getLogger(__name__)
    log.warning(
        "Optional dependency 'typer' not installed; some functionality will be"
        " unavailable. Install proctools with the 'cli' extras group to enable."
    )
    CONTEXT_SETTINGS, run, version_callback_for = None, None, None
else:
    from ._common import CONTEXT_SETTINGS, run, version_callback_for

from . import logger
from . import status
