"""
Check that certain conditions are correct before running any tests at all.
This only runs once per test session, so it's not too heavy.
"""

import pytest

@pytest.fixture(scope='session', autouse=True)
def check_config():
    import pcot
    from pcot.config import data
    pcot.setup()    # we have to load the config first!
    if data.sigfigs != 5:
        pytest.exit("Significant figures should be 5 in the configuration to run tests correctly")
    # Tests expect the default layout for spectra tables (and the CSV files made from them), so
    # replace any settings from the config file. This isn't saved, so the user's settings are kept.
    from pcot.utils.spectrumdata import SpectrumSet
    SpectrumSet.Provider.config = SpectrumSet.Provider.PROVIDER_PARAMS.create()

