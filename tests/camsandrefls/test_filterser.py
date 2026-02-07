"""
Tests of filter serialisation and deserialisation (in sources)
"""
from pcot import config, cameras
from pcot.sources import Source


def test_filterser():
    config.loadCameras()
    cam = cameras.getCamera("TRAINING_GEOLOGY")

    s = Source().setBand(cam.getFilter("G01"))
    print(s.serialise())
