"""
PDS4 test data is large, and so is kept in an optional directory. This function
gets that directory.

The test data should currently be rcp_output (which can
be found on the AU_ExoMars sharepoint). You should set this in your .pcot.ini file in your
home directory.
"""

import os
import pytest
import pcot.config

get_attempted = False          # have we at least tried to find this directory
testdatadir = None      # the directory itself
error = None            # error string if there was an error 


def get_pds4_test_data_dir():
    """
    Called from a test.
    Attempt to get the PDS4 test data directory from the config if that hasn't been done.
    Then return it. If there was an error, fail the test that calls this.
    """



    global get_attempted, testdatadir, error
    
    if not get_attempted:
        try:
            testdatadir = os.path.expanduser(pcot.config.getDefaultDir("testpds4data"))
            if not os.path.isdir(testdatadir):
                error = f"PDS4 test data directory {testdatadir} does not exist"
        except KeyError:
            error = "No PDS4 test data directory specified in the configuration file"

    get_attempted = True       # well, we've tried to load it, anyway.

    if error:
        pytest.fail(error)

    return testdatadir
